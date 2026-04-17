# Live150 Agent Service

Health-companion agent service: Python 3.12 + FastAPI + Google ADK + Postgres/pgvector. Single VM deployment via docker-compose.

## Build & Run

```bash
make install          # Create venv + install deps
make db.up            # Start Postgres only
make migrate          # Run Alembic migrations
make up               # Full stack (agent + postgres + scheduler)
make down             # Stop everything
make build            # Rebuild Docker images
```

## Test

```bash
make test             # Unit tests (no external deps)
make test-int         # Integration tests (uses testcontainers, needs Docker)
make eval             # LLM eval harness (costs tokens, not in CI)
pytest tests/unit/test_foo.py -q          # Single test file
pytest tests/unit/test_foo.py::test_bar   # Single test
```

## Lint & Format

```bash
make lint             # ruff check + mypy
make fmt              # ruff format
```

## Code Style

- Async everywhere: all DB access via SQLAlchemy async + asyncpg
- Pydantic models for all API request/response schemas
- Type annotations on all public functions
- Imports: stdlib, third-party, local (separated by blank lines)
- Use `httpx.AsyncClient` (not requests) for HTTP calls
- All env vars prefixed `LIVE150_` and loaded via `src/live150/config.py`
- Encryption: AES-256-GCM via `src/live150/crypto/vault.py` — always use AAD binding

## Architecture

- `src/live150/` — all application code
- `src/live150/agent/` — ADK agent builder, callbacks, model router
- `src/live150/tools/` — one file per tool category, registry assembles all
- `src/live150/api/` — FastAPI route handlers (chat, oauth, reminders, confirmations, health)
- `src/live150/db/models/` — SQLAlchemy models, one file per table
- `src/live150/memory/` — embeddings + pgvector hybrid search
- `src/live150/reminders/` — APScheduler + notify client
- `src/live150/oauth/` — provider registry + OAuth flows
- `migrations/` — Alembic migrations

## Key Patterns

- Auth: JWT from Live150 backend verified via JWKS. `require_user` FastAPI dependency.
- Per-request API token in `X-Live150-Api-Token` header — never stored, only in request scope.
- Reminder-time runs use service token, restricted to `REMINDER_SAFE_TOOLS`.
- Risky tool calls intercepted by `before_tool_cb` → `pending_confirmation` table.
- SSE streaming for `/chat` responses.
- APScheduler runs in dedicated `scheduler` container, not in Uvicorn workers.

## Database

- Postgres 18 + pgvector in `live150` schema
- Migrations via Alembic — `make migrate` or `make migration m="description"`
- UUIDs (uuid7) for all PKs except audit_log (BIGSERIAL)

## Gotchas

- APScheduler jobstore needs SYNC db url (`LIVE150_DB_URL_SYNC`), everything else uses async
- `soul.md` in `src/live150/agent/` is placeholder — will be replaced with real persona later
- Tool categories in `src/live150/tools/` are placeholders — real Live150 API endpoints TBD
- Docker compose has 3 services: `agent` (HTTP), `scheduler` (APScheduler), `postgres`
- The `migrator` service runs once on deploy then exits
