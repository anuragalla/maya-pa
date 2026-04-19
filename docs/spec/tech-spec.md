# Live150 Agent Service — Build Specification

**Audience:** Claude Code, building this from scratch.
**Owner:** Anurag.
**Goal:** A single Python service that runs one personalized health-companion agent for up to 10,000 users, deployed via docker-compose on a single GCP Compute Engine VM. Users chat through the existing Live150 mobile/web apps; the agent has tools over the existing Live150 health APIs and sends proactive reminders through an existing notify API.

---

## 1. Scope

### 1.1 What this service does

- Accepts chat messages from the Live150 mobile and web apps, runs them through a Gemini-powered agent, streams responses back.
- Gives the agent tools that call the existing Live150 REST APIs (sleep, activity, diet, etc. — exact list supplied later).
- Persists per-user conversation history and long-term semantic memory.
- Lets users (and the agent itself) create time-based reminders. Fires them on schedule and sends output to users via the existing notify API.
- Manages third-party OAuth connections (Google Calendar, Gmail, Google Fit, etc.) as an extensible list. Stores refresh tokens encrypted in Postgres.
- Enforces auth (JWT passthrough from the existing Live150 backend), rate limits, and a write-confirmation tier for risky tool calls.

### 1.2 What this service does NOT do

- No messaging-platform integrations (Telegram, WhatsApp, etc.). The Live150 apps are the only channel.
- No red-flag / safety-routing logic (handled separately, outside this service).
- No PII/PHI scrubbing before the model (Vertex's built-in controls are sufficient for MVP).
- No built-in notification transport. Everything goes through the existing notify API.
- No multi-agent orchestration (teams, delegation, handoff). One agent archetype serves all users.

### 1.3 Non-goals for MVP

- HA / multi-VM deployment (single VM is fine for 2k→10k users).
- Managed Postgres (docker-compose Postgres is fine — backups handled later).
- Advanced observability (logs-only for MVP; OpenTelemetry can be added later).

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Matches existing Anurag stack |
| Agent framework | Google ADK (`google-adk`) | Already chosen; handles tool-calling, sessions, callbacks |
| Model | Vertex AI — Gemini 3 Flash (default), Gemini 3.1 Flash-Lite (cheap turns) | Flash for advisory turns; Flash-Lite for simple data fetches |
| Web framework | FastAPI + Uvicorn | Async, streams well with SSE |
| Database | Postgres 18 + pgvector extension | Sessions, memory, reminders, tokens, audit |
| Scheduler | APScheduler with SQLAlchemyJobStore on Postgres | In-process, persistent, survives restarts |
| Migrations | Alembic | Standard SQLAlchemy migrations |
| ORM / query | SQLAlchemy 2.x async + asyncpg | Async all the way through |
| Encryption | `cryptography` library, AES-256-GCM | For refresh tokens + per-user API credentials |
| Deployment | docker-compose on GCE VM | Single-node, simplest path |
| Secrets | `.env` on the VM + GCP Secret Manager for master keys | KMS key for encrypting the encryption key |
| Logs | stdout → Cloud Logging agent on VM | No extra infra |

### 2.1 Python dependencies (`requirements.txt`)

```
google-adk>=1.0.0
google-cloud-aiplatform>=1.70.0
google-auth>=2.35.0
google-auth-oauthlib>=1.2.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
sqlalchemy[asyncio]>=2.0.36
asyncpg>=0.30.0
alembic>=1.14.0
pgvector>=0.3.6
apscheduler>=3.10.4
pyjwt[crypto]>=2.10.0
cryptography>=44.0.0
httpx>=0.28.0
pydantic>=2.10.0
pydantic-settings>=2.6.0
tenacity>=9.0.0
python-json-logger>=3.2.0
croniter>=5.0.0
pytest>=8.3.0
pytest-asyncio>=0.24.0
pytest-httpx>=0.34.0
deepeval>=2.0.0
```

---

## 3. Architecture

### 3.1 High-level diagram

```
┌──────────────────────────────────────────────────┐
│  Live150 mobile app / web app                    │
└────────────────────┬─────────────────────────────┘
                     │ HTTPS + Live150 JWT
                     ▼
┌──────────────────────────────────────────────────┐
│  GCE VM — docker-compose                         │
│  ┌────────────────────────────────────────────┐  │
│  │  live150-agent (FastAPI + ADK + APScheduler)│ │
│  │  - /chat    (SSE stream)                   │  │
│  │  - /oauth/* (third-party OAuth flows)      │  │
│  │  - /reminders/* (CRUD)                     │  │
│  │  - /health                                 │  │
│  │  - Internal: scheduler tick → agent run    │  │
│  └────────────┬───────────────────────────────┘  │
│               │                                  │
│  ┌────────────▼────────────┐                    │
│  │  postgres:18 + pgvector │                    │
│  │  - sessions, messages   │                    │
│  │  - memory (vectorized)  │                    │
│  │  - reminders (APS jobs) │                    │
│  │  - oauth_tokens         │                    │
│  │  - audit_log            │                    │
│  └─────────────────────────┘                    │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  External services                               │
│  - Vertex AI (Gemini)                            │
│  - Live150 Health APIs (REST + user bearer)      │
│  - Live150 Notify API                            │
│  - Google OAuth (Calendar/Gmail/Fit)             │
└──────────────────────────────────────────────────┘
```

### 3.2 Request flow — `/chat`

1. Mobile/web app sends `POST /chat` with the Live150 JWT in `Authorization: Bearer <jwt>` and the user's Live150 health-API bearer token in a separate header `X-Live150-Api-Token`. Body includes `session_id` (nullable — create if missing) and `message`.
2. FastAPI middleware verifies the JWT (see §5), extracts `user_id`.
3. Handler loads or creates an ADK session in Postgres for `(user_id, session_id)`.
4. Handler injects into `session.state`:
   - `user_id`
   - `api_token` (the X-Live150-Api-Token value)
   - `user_profile_summary` (fetched from Live150 or cached)
   - `turn_context` (e.g., `"interactive"` vs `"reminder"`)
5. Handler calls `runner.run_async(...)`. Response is streamed back as SSE.
6. On every tool call, the tool function reads `tool_context.state["api_token"]` and calls the relevant Live150 API with that bearer.
7. After the turn, ADK persists the updated session; an `after_agent_callback` writes an audit row.

### 3.3 Request flow — reminder firing

1. APScheduler wakes up at the scheduled time (jobs live in the `apscheduler_jobs` table).
2. Job payload contains `user_id`, `reminder_id`, `prompt_template`.
3. Worker resolves the user's current `api_token`. For reminders, the app does NOT hold a live user token — so either:
   - **(Preferred)** The Live150 notify API accepts a service-to-service token and we pass the rendered agent output + `user_id` to it. The agent's reminder-time tools use a **service account token** scoped to read-only "digest" endpoints on Live150's side (you'll define which endpoints are reachable this way).
   - **(Fallback)** If a reminder needs user-scoped writes, the reminder instead generates a prompt and queues an in-app notification saying "tap to continue" — the next `/chat` call from the app carries the user token.
4. Agent runs as if it were a normal turn but with `turn_context = "reminder"`. The SOUL prompt (later) will include rules for reminder tone ("proactive, not pushy; always say why you're reaching out").
5. Final text is POSTed to the Live150 notify API with `user_id` and payload.
6. Scheduler computes next fire time (for recurring reminders) and updates the job.

### 3.4 Directory layout

```
live150-agent/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .dockerignore
├── pyproject.toml
├── requirements.txt
├── alembic.ini
├── migrations/
│   ├── env.py
│   └── versions/
├── src/
│   └── live150/
│       ├── __init__.py
│       ├── main.py                  # FastAPI app entry
│       ├── config.py                # Pydantic settings from env
│       ├── logging.py               # JSON logger setup
│       ├── auth/
│       │   ├── __init__.py
│       │   ├── jwt.py               # Verify Live150 JWT
│       │   └── middleware.py        # FastAPI dependency
│       ├── db/
│       │   ├── __init__.py
│       │   ├── session.py           # Async engine + session factory
│       │   ├── base.py              # Declarative base
│       │   └── models/
│       │       ├── __init__.py
│       │       ├── user_profile.py
│       │       ├── chat_session.py
│       │       ├── chat_message.py
│       │       ├── memory.py
│       │       ├── reminder.py
│       │       ├── oauth_token.py
│       │       ├── audit_log.py
│       │       └── pending_confirmation.py
│       ├── crypto/
│       │   ├── __init__.py
│       │   └── vault.py             # AES-256-GCM encrypt/decrypt
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── builder.py           # Constructs the ADK LlmAgent
│       │   ├── soul.md              # Placeholder — real SOUL added later
│       │   ├── callbacks.py         # before_model / before_tool / after_agent
│       │   ├── runner.py            # Thin wrapper around ADK Runner
│       │   └── model_router.py      # Flash vs Flash-Lite decision
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── base.py              # Shared helpers (http client, auth)
│       │   ├── registry.py          # Assembles all FunctionTools
│       │   ├── health_api.py        # Placeholder category tools (filled in later)
│       │   ├── memory_tools.py      # search_memory, save_memory
│       │   ├── reminder_tools.py    # create_reminder, list_reminders, cancel_reminder
│       │   └── oauth_tools.py       # list_my_calendar_events etc.
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── embeddings.py        # Vertex text-embedding-005 client
│       │   ├── store.py             # pgvector upsert / hybrid search
│       │   └── service.py           # High-level save/recall API
│       ├── reminders/
│       │   ├── __init__.py
│       │   ├── scheduler.py         # APScheduler setup
│       │   ├── jobs.py              # Job payload + execution function
│       │   ├── parser.py            # "every Monday 9am IST" → cron expr
│       │   └── notify.py            # Client for Live150 notify API
│       ├── oauth/
│       │   ├── __init__.py
│       │   ├── providers.py         # Registry of OAuth providers
│       │   ├── flow.py              # Start / callback handlers
│       │   └── google.py            # Google-specific OAuth helpers
│       ├── api/
│       │   ├── __init__.py
│       │   ├── chat.py              # /chat endpoint (SSE)
│       │   ├── oauth.py             # /oauth/* endpoints
│       │   ├── reminders.py         # /reminders/* CRUD
│       │   ├── confirmations.py     # /confirmations/{id}/approve|reject
│       │   └── health.py            # /health, /ready
│       ├── audit/
│       │   ├── __init__.py
│       │   └── logger.py
│       └── safety/
│           ├── __init__.py
│           └── write_gate.py        # "risky write" confirmation logic
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_crypto_vault.py
│   │   ├── test_jwt.py
│   │   ├── test_memory_store.py
│   │   ├── test_reminder_parser.py
│   │   ├── test_model_router.py
│   │   └── test_write_gate.py
│   ├── integration/
│   │   ├── test_chat_flow.py        # Full /chat end-to-end with mocked Vertex
│   │   ├── test_oauth_flow.py
│   │   ├── test_reminder_firing.py
│   │   └── test_tool_calls.py
│   └── eval/
│       ├── README.md
│       ├── golden_dataset.jsonl
│       ├── judges.py                # LLM-as-judge graders
│       └── run_eval.py              # CLI: python -m tests.eval.run_eval
└── scripts/
    ├── seed_dev_user.py
    ├── rotate_encryption_key.py
    └── backfill_embeddings.py
```

---

## 4. Database Schema

All tables in schema `live150`. All primary keys are UUIDs (generated app-side with `uuid7` for time-sortable IDs; use `uuid-ossp` or Python `uuid6` lib).

### 4.1 Migrations

- Use Alembic.
- First migration: `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; CREATE EXTENSION IF NOT EXISTS vector;`
- One migration per table group for reviewability.

### 4.2 Tables

#### `user_profile`

Cached snapshot of the user's Live150 profile for fast context injection. Refreshed lazily.

```sql
CREATE TABLE user_profile (
  user_id         TEXT PRIMARY KEY,              -- matches Live150 user ID from JWT
  timezone        TEXT NOT NULL DEFAULT 'UTC',
  locale          TEXT NOT NULL DEFAULT 'en-US',
  profile_json    JSONB NOT NULL DEFAULT '{}',   -- age, goals, dietary flags, conditions summary
  last_synced_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_user_profile_last_synced ON user_profile(last_synced_at);
```

Profile is refreshed from Live150 APIs when older than `PROFILE_TTL_MINUTES` (default 60). The actual health data (sleep, activity logs) is NOT cached here — tools fetch it live.

#### `chat_session`

One row per conversation. Multiple sessions per user allowed.

```sql
CREATE TABLE chat_session (
  session_id    UUID PRIMARY KEY,
  user_id       TEXT NOT NULL,
  title         TEXT,                             -- auto-generated from first message
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at   TIMESTAMPTZ
);
CREATE INDEX ix_chat_session_user ON chat_session(user_id, updated_at DESC);
```

#### `chat_message`

```sql
CREATE TABLE chat_message (
  message_id    UUID PRIMARY KEY,
  session_id    UUID NOT NULL REFERENCES chat_session(session_id) ON DELETE CASCADE,
  user_id       TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('user','model','tool','system')),
  content       JSONB NOT NULL,                   -- ADK parts structure
  tokens_in     INTEGER,
  tokens_out    INTEGER,
  model         TEXT,
  turn_context  TEXT,                             -- 'interactive' | 'reminder'
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_chat_message_session_created ON chat_message(session_id, created_at);
CREATE INDEX ix_chat_message_user_created ON chat_message(user_id, created_at DESC);
```

Claude Code: ADK's `DatabaseSessionService` can manage this for you — if so, expose these as read-only views for audit/reminder queries and use ADK's schema directly for session state. Evaluate and pick whichever path has less glue code. Document the choice at the top of `src/live150/agent/runner.py`.

#### `memory_entry`

Long-term semantic memory. Distinct from session messages.

```sql
CREATE TABLE memory_entry (
  memory_id     UUID PRIMARY KEY,
  user_id       TEXT NOT NULL,
  kind          TEXT NOT NULL,                    -- 'fact' | 'preference' | 'event' | 'note'
  content       TEXT NOT NULL,
  source        TEXT,                             -- 'user' | 'agent' | 'system'
  source_ref    TEXT,                             -- optional session/message id
  embedding     VECTOR(768),                      -- Vertex text-embedding-005 dim
  metadata      JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at    TIMESTAMPTZ
);
CREATE INDEX ix_memory_user ON memory_entry(user_id, created_at DESC);
CREATE INDEX ix_memory_embedding ON memory_entry USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_memory_content_fts ON memory_entry USING gin (to_tsvector('english', content));
```

Hybrid search: combine pgvector cosine similarity with BM25-style `ts_rank` using weighted linear combination (start with `0.7 * vector + 0.3 * bm25`).

#### `reminder`

User-visible reminder metadata. The actual scheduling entries live in APScheduler's `apscheduler_jobs` table; `reminder.job_id` links the two.

```sql
CREATE TABLE reminder (
  reminder_id     UUID PRIMARY KEY,
  user_id         TEXT NOT NULL,
  created_by      TEXT NOT NULL CHECK (created_by IN ('user','agent')),
  title           TEXT NOT NULL,
  prompt_template TEXT NOT NULL,                  -- what we send to the agent when it fires
  schedule_kind   TEXT NOT NULL CHECK (schedule_kind IN ('once','cron','interval')),
  schedule_expr   TEXT NOT NULL,                  -- ISO datetime or cron expression
  timezone        TEXT NOT NULL,
  job_id          TEXT NOT NULL UNIQUE,           -- APScheduler job id
  status          TEXT NOT NULL DEFAULT 'active'  -- 'active' | 'paused' | 'cancelled'
                    CHECK (status IN ('active','paused','cancelled')),
  last_fired_at   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_reminder_user_status ON reminder(user_id, status);
```

#### `oauth_token`

Per-user, per-provider OAuth credentials. Refresh token is encrypted; access token is also encrypted for defense in depth.

```sql
CREATE TABLE oauth_token (
  oauth_token_id      UUID PRIMARY KEY,
  user_id             TEXT NOT NULL,
  provider            TEXT NOT NULL,              -- 'google', extensible
  provider_account_id TEXT,                       -- e.g. Google 'sub'
  scopes              TEXT[] NOT NULL DEFAULT '{}',
  access_token_ct     BYTEA NOT NULL,             -- AES-256-GCM ciphertext
  access_token_nonce  BYTEA NOT NULL,
  refresh_token_ct    BYTEA,                      -- nullable (some providers omit)
  refresh_token_nonce BYTEA,
  access_expires_at   TIMESTAMPTZ,
  key_version         INTEGER NOT NULL DEFAULT 1, -- for key rotation
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, provider, provider_account_id)
);
CREATE INDEX ix_oauth_token_user ON oauth_token(user_id, provider);
```

#### `audit_log`

Append-only log of every agent turn and every tool call.

```sql
CREATE TABLE audit_log (
  audit_id        BIGSERIAL PRIMARY KEY,
  user_id         TEXT NOT NULL,
  session_id      UUID,
  event_type      TEXT NOT NULL,                   -- 'turn_start','turn_end','tool_call','tool_result','model_error','oauth_connect','reminder_fired','confirmation_requested','confirmation_resolved'
  event_payload   JSONB NOT NULL,
  model           TEXT,
  latency_ms      INTEGER,
  tokens_in       INTEGER,
  tokens_out      INTEGER,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_user_created ON audit_log(user_id, created_at DESC);
CREATE INDEX ix_audit_event_created ON audit_log(event_type, created_at DESC);
```

#### `pending_confirmation`

Risky writes go here instead of executing. The app surfaces them to the user, who approves/rejects via `/confirmations/{id}/approve|reject`.

```sql
CREATE TABLE pending_confirmation (
  confirmation_id  UUID PRIMARY KEY,
  user_id          TEXT NOT NULL,
  session_id       UUID,
  tool_name        TEXT NOT NULL,
  tool_args        JSONB NOT NULL,
  summary          TEXT NOT NULL,                  -- human-readable "I'm about to X"
  status           TEXT NOT NULL DEFAULT 'pending' -- 'pending'|'approved'|'rejected'|'expired'
                     CHECK (status IN ('pending','approved','rejected','expired')),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at      TIMESTAMPTZ,
  expires_at       TIMESTAMPTZ NOT NULL            -- default now() + 15m
);
CREATE INDEX ix_pending_conf_user ON pending_confirmation(user_id, status);
```

#### `apscheduler_jobs`

Managed by APScheduler's SQLAlchemyJobStore. Don't hand-manage this table.

---

## 5. Auth

### 5.1 Live150 JWT verification

The existing Live150 backend issues JWTs. Claude Code: implement JWT verification as a reusable FastAPI dependency.

Env vars:

- `LIVE150_JWT_ISSUER`
- `LIVE150_JWT_AUDIENCE`
- `LIVE150_JWT_ALGORITHM` (default `RS256`)
- `LIVE150_JWT_JWKS_URL` (preferred) **or** `LIVE150_JWT_PUBLIC_KEY_PEM`

Behavior:

- Cache JWKS responses for `JWT_JWKS_CACHE_SECONDS` (default 600).
- Verify `iss`, `aud`, `exp`, `nbf`.
- Extract `sub` as `user_id`.
- On failure: 401 with opaque body.

Dependency signature:

```python
from fastapi import Depends
from live150.auth.middleware import require_user

@router.post("/chat")
async def chat(..., user: AuthedUser = Depends(require_user)):
    ...
```

`AuthedUser` is a Pydantic model: `user_id: str`, `claims: dict`.

### 5.2 Per-user Live150 API bearer

The app also sends the user's Live150 health-API bearer in header `X-Live150-Api-Token`. The agent service never stores this — it's only held in request-scoped state and passed to tools during that turn.

For **reminder-time runs** (no active user session), use a service-to-service token (`LIVE150_SERVICE_API_TOKEN`) scoped to read-only digest endpoints. Tools check `tool_context.state["turn_context"]`; if `"reminder"` and the tool is not in the reminder-allowlist (`REMINDER_SAFE_TOOLS`), the tool returns an error that says "this tool requires an active user session" — the agent should then recover by producing a nudge like "tap to continue" which the notify API delivers as a deep link.

### 5.3 Rate limiting

In-process token bucket per user. Defaults:

- 60 messages per 5 minutes per user on `/chat`
- 10 reminders per minute per user on `/reminders`
- 100 requests per second globally on everything (safety valve)

Exceeded → 429 with `Retry-After`.

Implementation: use a simple in-memory `TokenBucket` keyed by `user_id` in a dict with an async lock. At 10k users / single VM this is fine. When scaling out, move to Redis — flag this in code with a `# TODO(scale-out)` comment.

---

## 6. Encryption — `crypto/vault.py`

AES-256-GCM with envelope encryption.

- Master key: 32-byte key loaded from `LIVE150_MASTER_KEY` env (base64). In production, the env var is populated at container start from GCP Secret Manager.
- Each ciphertext has a fresh 12-byte nonce.
- Stored as `{ciphertext: BYTEA, nonce: BYTEA, key_version: INTEGER}`.

API:

```python
class Vault:
    def __init__(self, master_key: bytes, key_version: int = 1): ...

    def encrypt(self, plaintext: str | bytes, aad: bytes | None = None) -> EncryptedBlob: ...
    def decrypt(self, blob: EncryptedBlob, aad: bytes | None = None) -> bytes: ...

@dataclass
class EncryptedBlob:
    ciphertext: bytes
    nonce: bytes
    key_version: int
```

For OAuth tokens, pass `aad = f"oauth:{user_id}:{provider}".encode()` to bind the ciphertext to its row. Any attempt to move a row across users fails decryption.

Key rotation: `scripts/rotate_encryption_key.py` reads old key + new key, re-encrypts all rows with `key_version` mismatch. Idempotent.

---

## 7. Agent Construction

### 7.1 `agent/builder.py`

Builds one `LlmAgent` per process (singleton). Loads SOUL from `agent/soul.md` (placeholder for now — Anurag will provide content later; the file must exist and be loaded at startup). Registers all tools from `tools/registry.py`. Installs callbacks from `agent/callbacks.py`.

```python
from google.adk.agents import LlmAgent

def build_agent() -> LlmAgent:
    soul = _load_soul_md()
    return LlmAgent(
        name="live150",
        model=settings.default_model,       # e.g. "gemini-3-flash"
        instruction=soul,
        tools=build_tool_registry(),
        before_model_callback=before_model_cb,
        before_tool_callback=before_tool_cb,
        after_agent_callback=after_agent_cb,
    )
```

### 7.2 `agent/model_router.py`

Decides per-turn whether to route to Flash or Flash-Lite.

```python
def choose_model(user_message: str, session_state: dict) -> str:
    # Heuristic v1: Flash-Lite if message is short, no obvious planning verbs,
    # no prior tool calls in last 3 turns; Flash otherwise.
    # Turn context == 'reminder' always uses Flash.
    ...
```

Return values: `"gemini-3-flash"` or `"gemini-3-1-flash-lite"` (exact model IDs from env — these are placeholders). The selected model is applied by overriding `LlmAgent.model` via `before_model_callback` (ADK supports this).

### 7.3 Callbacks — `agent/callbacks.py`

**`before_model_cb(callback_context, llm_request)`**

- Stamp `turn_start` row in `audit_log`.
- Apply model routing: mutate `llm_request.model` if router says so.
- Inject the cached `user_profile_summary` as the first user turn's system note if not already present.

**`before_tool_cb(tool, args, tool_context)`**

- Enforce reminder-mode tool allowlist (§5.2).
- For tools flagged as `risky` (see §8.3), intercept: write a `pending_confirmation` row, return a synthetic tool-result that says "awaiting user confirmation — the user will approve via the app." The agent's next step should be to inform the user.
- Write `tool_call` audit row.

**`after_agent_cb(callback_context)`**

- Write `turn_end` audit row with total tokens + latency.
- If the turn produced new stable facts (heuristic: model explicitly wrote `remember:` directives in its output — we parse them out) save them to `memory_entry`.

### 7.4 `agent/runner.py`

Thin wrapper:

```python
class Live150Runner:
    def __init__(self, agent: LlmAgent, session_service, memory_service): ...

    async def run_turn(
        self,
        user_id: str,
        session_id: UUID,
        api_token: str,
        message: str,
        turn_context: Literal["interactive", "reminder"] = "interactive",
    ) -> AsyncIterator[Event]: ...
```

Yields ADK events so the HTTP layer can transform them into SSE frames.

---

## 8. Tools

### 8.1 Structure

One file per tool category. Each file exports a list of `FunctionTool` instances. `tools/registry.py` concatenates them.

```python
# tools/base.py
import httpx
from google.adk.tools import ToolContext

async def live150_get(tool_context: ToolContext, path: str, params: dict | None = None):
    token = tool_context.state["api_token"]
    async with httpx.AsyncClient(base_url=settings.live150_api_base) as client:
        r = await client.get(path, params=params, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()
```

Keep category names aligned with Anurag's API domains. **The exact tools are TBD** — Anurag will supply the API list later. For now, create placeholder categories with one dummy tool each so the registry is wired end-to-end:

- `health_sleep` — `get_sleep_summary(days: int = 7)`
- `health_activity` — `get_activity_summary(days: int = 7)`
- `health_nutrition` — `get_meal_log(days: int = 3)`, `log_water(ml: int)` *(safe write, auto)*
- `health_plans` — `get_current_plan()`, `cancel_workout_plan(plan_id: str)` *(risky write, requires confirmation)*
- `memory` — `search_memory(query: str, limit: int = 5)`, `save_memory(kind: str, content: str)`
- `reminders` — `create_reminder(title, when, recurrence, prompt)`, `list_reminders()`, `cancel_reminder(reminder_id)`
- `google` — `list_calendar_events(timeframe: str)`, `create_calendar_event(...)` *(risky write)*

Anurag will replace the dummies with real API calls.

### 8.2 Safe vs risky writes

Each tool declares at registration:

```python
FunctionTool(
    func=log_water,
    metadata={"write": "safe"},   # or "read" or "risky"
)
```

- `read` — no restrictions.
- `safe` write — executes immediately, written to `audit_log`.
- `risky` write — intercepted by `before_tool_cb` (see §7.3), creates `pending_confirmation`, returns "awaiting confirmation" result.

The risky/safe taxonomy is a config list in `tools/registry.py`:

```python
RISKY_TOOLS = {"cancel_workout_plan", "create_calendar_event", "send_calendar_invite", ...}
SAFE_WRITES = {"log_water", "log_mood", "save_memory", ...}
```

### 8.3 Reminder-mode allowlist

```python
REMINDER_SAFE_TOOLS = {"get_sleep_summary", "get_activity_summary", "get_meal_log", "search_memory", "list_reminders"}
```

Only these can run with the service token during reminder firing. Any other tool returns a structured error.

---

## 9. Memory

### 9.1 Embeddings — `memory/embeddings.py`

Use Vertex AI `text-embedding-005` (768-dim). Batch up to 100 items per call.

```python
class Embedder:
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

### 9.2 Store — `memory/store.py`

```python
class MemoryStore:
    async def upsert(self, user_id: str, entry: MemoryEntry) -> UUID: ...
    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        kinds: list[str] | None = None,
    ) -> list[MemoryHit]: ...
```

Hybrid search SQL:

```sql
WITH q AS (SELECT $query_embedding::vector AS v, to_tsquery('english', $tsquery) AS t),
     scored AS (
       SELECT m.*,
              1 - (m.embedding <=> q.v) AS vec_score,
              ts_rank(to_tsvector('english', m.content), q.t) AS text_score
         FROM memory_entry m, q
        WHERE m.user_id = $user_id
          AND ($kinds IS NULL OR m.kind = ANY($kinds))
          AND (m.expires_at IS NULL OR m.expires_at > now())
     )
SELECT *, (0.7 * vec_score + 0.3 * text_score) AS score
  FROM scored
 ORDER BY score DESC
 LIMIT $limit;
```

### 9.3 Service — `memory/service.py`

Wraps store + embedder, owns chunking policy (chunks ≤ 400 tokens).

---

## 10. Reminders

### 10.1 Scheduler — `reminders/scheduler.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

def build_scheduler(db_url_sync: str) -> AsyncIOScheduler:
    jobstores = {"default": SQLAlchemyJobStore(url=db_url_sync, tablename="apscheduler_jobs")}
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone="UTC",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
    )
    return scheduler
```

Start on FastAPI startup; shutdown on shutdown. **APScheduler needs a sync DB URL for its jobstore** even though the rest of the app is async — document this clearly in code.

### 10.2 Parser — `reminders/parser.py`

Accepts natural-language input ("every Monday 9am IST", "tomorrow at 7pm", "in 2 hours") and returns:

```python
@dataclass
class ParsedSchedule:
    kind: Literal["once", "cron", "interval"]
    expr: str                  # ISO datetime or cron string
    timezone: str              # IANA tz name
```

Implementation: use the LLM itself via a tiny Flash-Lite call with a strict JSON schema output. Validate the result with `croniter` / `datetime.fromisoformat`. Reject if invalid.

### 10.3 Job — `reminders/jobs.py`

```python
async def fire_reminder(reminder_id: UUID):
    # 1. Load reminder + user from DB
    # 2. Build synthetic "turn" with turn_context="reminder"
    # 3. Run agent with reminder prompt_template
    # 4. POST final output to notify API
    # 5. Update reminder.last_fired_at
    # 6. Write audit_log row
```

APScheduler serializes function references by module path, so keep `fire_reminder` at module scope.

### 10.4 Notify client — `reminders/notify.py`

```python
class NotifyClient:
    async def send(self, user_id: str, payload: dict) -> None:
        # POST to settings.live150_notify_url with service auth header
        ...
```

Retry with exponential backoff (tenacity): 3 attempts, 1s/2s/4s. On final failure, write `reminder_delivery_failed` audit row. Don't crash the scheduler.

---

## 11. OAuth — `oauth/`

### 11.1 Provider registry — `oauth/providers.py`

Extensible registry. Each provider declares: name, auth URL, token URL, default scopes, token-refresh behavior.

```python
@dataclass
class OAuthProvider:
    name: str
    auth_url: str
    token_url: str
    scopes: list[str]
    client_id_env: str
    client_secret_env: str

PROVIDERS = {
    "google": OAuthProvider(
        name="google",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["openid", "email", "https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/gmail.readonly"],
        client_id_env="GOOGLE_OAUTH_CLIENT_ID",
        client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
    ),
    # future: "apple_health", "fitbit", etc.
}
```

### 11.2 Endpoints — `api/oauth.py`

- `GET /oauth/{provider}/start` — verifies the Live150 JWT, generates a signed state token containing `user_id + provider + nonce + exp`, redirects to provider auth URL.
- `GET /oauth/{provider}/callback` — validates state, exchanges code for tokens, encrypts via Vault, upserts into `oauth_token`. Responds with an HTML page that deep-links back into the Live150 app.
- `DELETE /oauth/{provider}` — revokes (calls provider revoke endpoint if supported), deletes the row.
- `GET /oauth/connected` — returns list of providers the user is connected to.

### 11.3 Refresh — `oauth/google.py` (and similar per provider)

```python
async def get_fresh_credentials(user_id: str, provider: str) -> Credentials:
    # 1. Load row
    # 2. Decrypt access token, check expiry
    # 3. If expired: refresh via refresh_token, re-encrypt, update row
    # 4. Return Credentials
```

---

## 12. HTTP API

### 12.1 `POST /chat`

Headers:
- `Authorization: Bearer <live150_jwt>`
- `X-Live150-Api-Token: <live150_api_token>`
- `Accept: text/event-stream`

Body:
```json
{
  "session_id": "uuid or null",
  "message": "How did I sleep last night?"
}
```

Response: SSE stream with events:

- `event: session` data `{"session_id": "..."}` (sent once at start if new session)
- `event: delta` data `{"text": "..."}` (model text chunks)
- `event: tool_call` data `{"name": "...", "args": {...}}`
- `event: tool_result` data `{"name": "...", "ok": true}` (truncated, no sensitive data)
- `event: confirmation_required` data `{"confirmation_id": "...", "summary": "..."}`
- `event: done` data `{"tokens_in": n, "tokens_out": n, "model": "..."}`
- `event: error` data `{"code": "...", "message": "..."}`

### 12.2 `POST /chat/sessions`

Creates an empty session. Returns `{session_id}`.

### 12.3 `GET /chat/sessions`

Lists user's sessions (paginated: `?limit=20&before=<iso>`).

### 12.4 `GET /chat/sessions/{session_id}/messages`

Returns message history. Paginated.

### 12.5 `DELETE /chat/sessions/{session_id}`

Archives the session (soft delete — sets `archived_at`).

### 12.6 Reminders

- `GET /reminders` — list active reminders for user
- `POST /reminders` — body `{title, schedule_text, prompt}`; parser normalizes
- `PATCH /reminders/{id}` — title, schedule, status (pause/resume)
- `DELETE /reminders/{id}`

### 12.7 Confirmations

- `GET /confirmations` — pending for user
- `POST /confirmations/{id}/approve` — executes the tool, streams result back as SSE if the caller subscribes; otherwise writes result to the original session
- `POST /confirmations/{id}/reject` — marks rejected, agent is informed on next turn

### 12.8 OAuth

Per §11.2.

### 12.9 Health

- `GET /health` — liveness: `{status: "ok"}`
- `GET /ready` — readiness: DB reachable, scheduler running, Vertex reachable (cached for 30s)

---

## 13. Config — `config.py`

Pydantic `BaseSettings` loads from env. All env vars prefixed `LIVE150_`. Sample (see `.env.example`):

```
# --- Service ---
LIVE150_ENV=prod                         # dev|prod
LIVE150_LOG_LEVEL=INFO
LIVE150_HTTP_HOST=0.0.0.0
LIVE150_HTTP_PORT=8000

# --- Database ---
LIVE150_DB_URL_ASYNC=postgresql+asyncpg://live150:***@postgres:5432/live150
LIVE150_DB_URL_SYNC=postgresql://live150:***@postgres:5432/live150

# --- Auth ---
LIVE150_JWT_ISSUER=https://auth.live150.example
LIVE150_JWT_AUDIENCE=live150-agent
LIVE150_JWT_ALGORITHM=RS256
LIVE150_JWT_JWKS_URL=https://auth.live150.example/.well-known/jwks.json
LIVE150_JWT_JWKS_CACHE_SECONDS=600

# --- Vertex AI ---
LIVE150_GCP_PROJECT=live150-prod
LIVE150_GCP_REGION=us-central1
LIVE150_DEFAULT_MODEL=gemini-3-flash
LIVE150_LITE_MODEL=gemini-3-1-flash-lite
LIVE150_EMBEDDING_MODEL=text-embedding-005

# --- Live150 APIs ---
LIVE150_API_BASE=https://api.live150.example
LIVE150_NOTIFY_URL=https://notify.live150.example/send
LIVE150_SERVICE_API_TOKEN=***           # for reminder-time runs

# --- OAuth ---
GOOGLE_OAUTH_CLIENT_ID=***
GOOGLE_OAUTH_CLIENT_SECRET=***
LIVE150_OAUTH_REDIRECT_BASE=https://agent.live150.example

# --- Crypto ---
LIVE150_MASTER_KEY=base64:***           # 32 bytes

# --- Misc ---
LIVE150_PROFILE_TTL_MINUTES=60
LIVE150_RATE_LIMIT_CHAT_PER_5MIN=60
LIVE150_RATE_LIMIT_REMINDERS_PER_MIN=10
```

---

## 14. Deployment — docker-compose

### 14.1 `docker-compose.yml`

```yaml
services:
  agent:
    build: .
    image: live150-agent:latest
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
    command: ["uvicorn", "live150.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  postgres:
    image: pgvector/pgvector:pg18
    restart: unless-stopped
    environment:
      POSTGRES_DB: live150
      POSTGRES_USER: live150
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/01-extensions.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U live150 -d live150"]
      interval: 10s
      timeout: 5s
      retries: 10
    # Not exposed externally — agent talks to it on the docker network.

  migrator:
    build: .
    image: live150-agent:latest
    depends_on:
      postgres:
        condition: service_healthy
    env_file: .env
    command: ["alembic", "upgrade", "head"]
    restart: "no"

volumes:
  pgdata:
```

### 14.2 `Dockerfile`

Multi-stage, minimal. Python 3.12-slim base. Non-root user. Layer cache-friendly (copy `requirements.txt` first).

```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini .
RUN useradd -u 10001 -m app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "live150.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 14.3 `docker/postgres/init.sql`

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
```

### 14.4 VM sizing (guidance, not a directive)

- Start: `e2-standard-4` (4 vCPU, 16 GB RAM). Postgres + agent both fit comfortably.
- Disk: 100 GB pd-balanced for `pgdata`.
- At 10k users, revisit — likely need `e2-standard-8` or move Postgres to Cloud SQL. Code should not care.

### 14.5 Backups — deferred

Per decision: figure out later. **Scheduled for v1.1.** Meanwhile, add a commented-out `pg_dump` sidecar in `docker-compose.yml` so it's one-line to enable:

```yaml
# backup:
#   image: postgres:18
#   depends_on: [postgres]
#   env_file: .env
#   volumes: [./backups:/backups]
#   entrypoint: ["/bin/sh","-c","while true; do pg_dump -h postgres -U live150 live150 | gzip > /backups/live150-$(date +%F_%H%M).sql.gz; sleep 86400; done"]
```

### 14.6 Startup order

1. `postgres` → healthy (pgvector extension auto-created via init.sql).
2. `migrator` runs Alembic head migrations, exits 0.
3. `agent` starts, connects, starts APScheduler, starts Uvicorn.

### 14.7 Concurrency

- Uvicorn with 4 workers = 4 Python processes. **APScheduler must run in exactly one worker.**
- Solution: set `LIVE150_SCHEDULER_ENABLED=true` on only one worker via a separate service OR run APScheduler in a sidecar container that shares DB + code. **Recommended:** a second container `scheduler` that runs `python -m live150.reminders.run_scheduler` (a dedicated entry point). Agent workers handle HTTP only; scheduler container owns APScheduler.

Update compose:

```yaml
  scheduler:
    build: .
    image: live150-agent:latest
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      migrator:
        condition: service_completed_successfully
    env_file: .env
    command: ["python", "-m", "live150.reminders.run_scheduler"]
```

---

## 15. Logging

- JSON logs to stdout via `python-json-logger`.
- Every log line includes: `timestamp`, `level`, `logger`, `user_id` (when known), `session_id` (when known), `event`, `message`.
- Install the Cloud Logging agent on the VM — it picks up container stdout automatically and ships to Cloud Logging.
- No structured tracing for MVP. Add OpenTelemetry in v1.1 (pre-wire the middleware so it's a config toggle).

---

## 16. Testing

### 16.1 Unit tests — `tests/unit/`

Run with `pytest tests/unit -q`. No external services. Use `pytest-asyncio`. Examples to include (stubs are fine; Claude Code fills them in):

- `test_crypto_vault.py` — encrypt→decrypt round-trip, AAD binding rejects cross-user blobs, key rotation.
- `test_jwt.py` — valid, expired, wrong audience, invalid signature, JWKS cache.
- `test_memory_store.py` — upsert, search returns ordered hits, kind filter, expiry.
- `test_reminder_parser.py` — natural language → ParsedSchedule; invalid inputs rejected.
- `test_model_router.py` — short message → Flash-Lite; planning verbs → Flash; reminder turn → Flash always.
- `test_write_gate.py` — risky tool intercepted, pending_confirmation created; safe tool passes through.

### 16.2 Integration tests — `tests/integration/`

Require a running Postgres. Use `testcontainers-python` to spin one up per test session. Stub Vertex using `pytest-httpx` to intercept calls; use canned model responses. Examples:

- `test_chat_flow.py` — POST /chat with a fake user_id; mock model produces `tool_call → text`; verify SSE frames, audit_log rows, chat_message rows.
- `test_oauth_flow.py` — `/oauth/google/start` redirects; callback stores encrypted tokens; refresh path rotates access token.
- `test_reminder_firing.py` — create reminder scheduled 2s in future; wait; assert fire_reminder ran, notify API was called, audit row written.
- `test_tool_calls.py` — each category tool invokable with a mocked Live150 API; risky tools go to confirmation.

### 16.3 Eval harness — `tests/eval/`

Run with `python -m tests.eval.run_eval`. Not run in CI by default (costs tokens).

- `golden_dataset.jsonl` — 30–50 examples. Each row:
  ```json
  {"id":"...","user_state":{...},"message":"...","expected_tools":["get_sleep_summary"],"expected_properties":["mentions_hours_slept","no_medical_advice_disclaimer_needed"]}
  ```
- `judges.py` — LLM-as-judge graders using Gemini 3 Flash with structured output. Graders:
  - `tool_selection_judge` — did the agent call the expected tools?
  - `groundedness_judge` — does the response reference real data from tool results?
  - `tone_judge` — does the response match Live150 tone guidelines? (soft — SOUL is TBD)
  - `safety_judge` — no unprompted medical claims?
- `run_eval.py` — iterates, runs agent with mocked tools, scores each example, writes report JSON + Markdown summary.

Use DeepEval for the judge infra (already in requirements).

---

## 17. Makefile

```makefile
.PHONY: help venv install lint fmt test test-int eval run db.up db.down db.reset migrate migration build up down logs

help:
	@awk 'BEGIN{FS":.*?## "}/^[a-zA-Z_.-]+:.*?## /{printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

venv: ## Create local virtualenv
	python -m venv .venv
	.venv/bin/pip install -U pip wheel
	.venv/bin/pip install -r requirements.txt

install: venv ## Install dependencies

lint: ## Ruff + mypy
	ruff check src tests
	mypy src

fmt: ## Ruff format
	ruff format src tests

test: ## Unit tests
	pytest tests/unit -q

test-int: ## Integration tests (testcontainers)
	pytest tests/integration -q

eval: ## Run eval harness (costs tokens)
	python -m tests.eval.run_eval

db.up: ## Start only postgres
	docker compose up -d postgres

db.down: ## Stop postgres
	docker compose stop postgres

db.reset: ## Wipe Postgres volume and recreate
	docker compose down -v
	docker compose up -d postgres

migrate: ## Alembic upgrade head
	docker compose run --rm migrator

migration: ## Create new migration (usage: make migration m="add foo")
	alembic revision --autogenerate -m "$(m)"

build: ## Build images
	docker compose build

up: ## Start full stack
	docker compose up -d

down: ## Stop everything
	docker compose down

logs: ## Tail logs
	docker compose logs -f --tail=200
```

---

## 18. Milestones (build order)

Claude Code: build in this order. Each milestone should end in passing tests.

1. **Skeleton** — repo layout, config, JSON logging, docker-compose up cleanly, Postgres with extensions, `/health` and `/ready` pass.
2. **Auth** — JWT verification, `require_user` dependency, unit tests. `/chat` stub returns `{"user_id": user.user_id}`.
3. **DB + migrations** — all tables, first Alembic migration, unit tests for a couple of models.
4. **Crypto vault** — Vault implementation + unit tests.
5. **OAuth** — Google provider end-to-end, encrypted token storage, refresh path. Integration test with mocked Google endpoints.
6. **Agent wiring** — ADK `LlmAgent` built with a stub SOUL, one dummy tool (`echo`), callbacks installed, `/chat` streams a model response for a hello message. Integration test with pytest-httpx-mocked Vertex.
7. **Tool registry + placeholder categories** — sleep/activity/nutrition/plans/google placeholders hitting example URLs. Integration test validating bearer passthrough.
8. **Memory** — embeddings, store, hybrid search, `save_memory` / `search_memory` tools. Tests for both.
9. **Reminders** — scheduler container, APScheduler with Postgres jobstore, parser, `fire_reminder`, notify client. Integration test firing in < 5s.
10. **Risky-write confirmations** — `pending_confirmation` table, `before_tool_cb` interception, `/confirmations` endpoints. Integration test end-to-end.
11. **Model routing** — router + plumbing through `before_model_callback`. Unit tests.
12. **Audit log** — all write sites emit rows. Spot-check tests.
13. **Eval harness** — dataset, judges, runner. Not in CI.
14. **Polish** — rate limits, SSE heartbeat, graceful shutdown, README, runbook, sample curl commands.

---

## 19. Open items for Anurag

Fill these in before or during build:

- [ ] **Live150 API list** — exact endpoints per category (sleep, activity, nutrition, plans, …). Needed for §8.1.
- [ ] **Live150 notify API contract** — URL, auth header, payload shape. Needed for §10.4.
- [ ] **Live150 service-to-service token** — for reminder-time runs. Needed for §5.2.
- [ ] **OAuth redirect URI** — needs to be added to the Google Cloud project. Needed for §11.2.
- [ ] **SOUL.md** — the agent's persona and tone. Can start with a one-paragraph placeholder and iterate.
- [ ] **Exact Gemini model IDs** — confirm the production model strings for `LIVE150_DEFAULT_MODEL` and `LIVE150_LITE_MODEL` in Vertex (preview model IDs change; pin them in env, not in code).
- [ ] **VM size** — start at `e2-standard-4`, confirm or resize.

---

## 20. Trade-offs explicitly chosen for MVP

Document these in the README so reviewers see them up front:

- **Single VM, no HA.** At 2k→10k users this is acceptable. Failure mode is minutes of downtime on crash/reboot. Mitigation: systemd restart + docker `restart: unless-stopped`.
- **Postgres in compose on same VM.** Simpler. Moving to Cloud SQL later is a DSN change + data migration — no code changes.
- **APScheduler in one container.** Simpler than Cloud Scheduler + Pub/Sub. Moving to Cloud Scheduler later means replacing `reminders/scheduler.py` and `fire_reminder` dispatch — job metadata in our `reminder` table travels with us.
- **Logs-only observability.** Cloud Logging via the VM agent is enough for MVP debugging. Tracing wiring is stubbed so OpenTelemetry can be added without rewiring.
- **PII/PHI goes to the LLM as-is.** Relying on Vertex controls. Revisit when clinical liability or regulatory scope changes.
- **Safety routing (red-flags) is not in this service.** Anurag handles separately. The agent must never be the only line of defense — this is explicit.
- **One agent, one SOUL.** No archetypes, no multi-agent orchestration. If we need sub-agents later, ADK supports `SequentialAgent`/`ParallelAgent`/`AgentTool` — add them incrementally.

---

## End of spec
