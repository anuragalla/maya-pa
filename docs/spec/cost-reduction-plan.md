# Maya PA — Cost Reduction Plan

**Date:** 2026-04-19
**Source:** `docs/spec/pricing-analysis.md` §7 recommendations, with scope decisions from the 2026-04-19 review.

---

## Decisions (from review)

| Question | Decision |
|---|---|
| Model | Stay on Flash-Lite only. Do not introduce Flash or Pro. |
| Thinking budget on interactive | **Flat `thinking_budget=512`** across all interactive turns |
| Per-skill thinking override | Not yet. Keep globally flat. Revisit if specific skills demonstrably degrade. |
| Thinking budget on reminders | Leave at `0` (already correct) |
| History cap | **5 turns inline**; rely on `search_memory` for older context |
| Summarize dropped turns into memory? | Not in v1. Reflection already extracts durable facts per turn; that's enough. |

Everything else (Pro routing, tool-set pruning, per-user caches) is out of scope for this plan.

---

## Ordered Steps

Each step is independent and reversible. Ship in order; measure between steps.

### Step 1 — Telemetry (do first; zero-risk)

**Why first:** every downstream optimization needs cache-hit and thinking-token observability. Without it we're guessing.

**Files:**

- `server/src/live150/db/models/audit_log.py` — add two nullable columns + one Alembic migration.
  ```python
  cached_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
  thoughts_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
  ```

- `server/src/live150/audit/logger.py` — extend `write_audit()` signature with `cached_tokens` and `thoughts_tokens` kwargs and persist them.

- `server/src/live150/agent/callbacks.py` — add an `after_model_cb` that reads `llm_response.usage_metadata` and writes a `turn_metrics` audit row:
  ```python
  def after_model_cb(callback_context, llm_response):
      usage = getattr(llm_response, "usage_metadata", None)
      if usage is None:
          return
      state = getattr(callback_context, "state", {})
      # fire-and-forget; do not block the stream
      asyncio.create_task(_write_turn_audit(
          user_id=state.get("user_id"),
          session_id=state.get("session_id"),
          model=llm_request.model,
          tokens_in=usage.prompt_token_count,
          tokens_out=usage.candidates_token_count,
          cached_tokens=getattr(usage, "cached_content_token_count", 0),
          thoughts_tokens=getattr(usage, "thoughts_token_count", 0),
      ))
  ```
  Wire `after_model_callback=after_model_cb` into `LlmAgent(...)` in `builder.py:63`.

**Verification:**
- After shipping, run an interactive session, query `SELECT cached_tokens, thoughts_tokens FROM audit_log WHERE event_type='turn_metrics' ORDER BY created_at DESC LIMIT 20;`.
- Expected today: `cached_tokens` mostly 0 (no caching yet), `thoughts_tokens` averaging ~1,500 on interactive, ~0 on reminders.
- If `cached_tokens > 0` on some rows, Vertex is already doing implicit caching for us — good news, lowers the urgency of Step 3.

**Estimated $ impact:** 0. This is instrumentation.

---

### Step 2 — Flat `thinking_budget=512` on interactive

**Why second:** one-line change, immediate measurable output-token reduction in Step 1's telemetry.

**File:** `server/src/live150/agent/callbacks.py:56`

**Diff:**
```python
# before
thinking_budget = 0 if state.get("turn_context") == "reminder" else 8192

# after
thinking_budget = 0 if state.get("turn_context") == "reminder" else 512
```

That's it. Reminder branch unchanged.

**Verification:**
- After one day, query audit log: `SELECT AVG(thoughts_tokens) FROM audit_log WHERE event_type='turn_metrics' AND model LIKE '%flash-lite%' AND created_at > NOW() - INTERVAL '24 hours';`
- Expected: average drops from ~1,500 → ~300–500 (model usually uses less than the cap).
- Spot-check 10 interactive responses for quality regression. If responses feel notably dumber on planning turns, consider raising to 1024 or revisiting the tiered approach.

**Estimated $ impact (10k users):** ~**−$4.4k / month**. Medium user drops from $2.02 → ~$1.62.

**Risk:** weaker reasoning on hard planning turns. Mitigation: telemetry in Step 1 lets us A/B against the pre-change week.

**Rollback:** flip 512 back to 8192. Zero downstream changes.

---

### Step 3 — Explicit `CachedContent` for the static prefix

**Why third:** biggest single $ lever but needs real code. Telemetry from Step 1 tells us whether we need this or whether implicit caching is already firing.

**Decision gate:** after Step 1 is live for a week, check average `cached_tokens` on interactive turns.
- If `cached_tokens / prompt_tokens` > 0.6 across most users → implicit caching is working. Ship only §7.1 minor cleanup. Defer explicit caching.
- If < 0.3 → implicit caching isn't catching. Proceed with explicit caching below.

**Files:**

- `server/src/live150/agent/caching.py` *(new)* — wraps `Client.caches.create(...)` from `google.genai`. Cache contains: SOUL.md + AGENTS.md + IDENTITY.md text + an ADK-serialized tool list. TTL 1h, refreshed lazily on miss.

- `server/src/live150/agent/builder.py` — at startup, call `get_or_create_static_cache()` and stash the cache resource name. In `_dynamic_instruction`, when building the system instruction, reference the cache in `GenerateContentConfig(cached_content=<name>)` via a new `before_model_cb` branch instead of inlining SOUL+AGENTS text.

- `server/src/live150/agent/callbacks.py` — in `before_model_cb`, set `llm_request.config.cached_content = STATIC_CACHE_NAME`. Strip the static prefix from `llm_request.contents` to avoid double-billing (ADK injects it via `instruction`, so we need to swap instruction source rather than append).

- One APScheduler job that refreshes the cache TTL every 50 minutes (so it never expires under normal load).

**Gotcha:** ADK's `LlmAgent(instruction=...)` vs. explicit Vertex `cached_content` don't naturally compose. We may need to bypass ADK's instruction pathway for the static block and use `cached_content` directly, keeping only dynamic context in the `instruction` callback. Prototype on a branch first; this is the riskiest change in the plan.

**Verification:**
- After rollout, `SELECT AVG(cached_tokens * 1.0 / tokens_in) FROM audit_log WHERE event_type='turn_metrics' AND created_at > NOW() - INTERVAL '1 hour';`
- Expected: >0.8 (80%+ of input tokens served from cache).
- Watch `tokens_in` — it should NOT drop; we're still sending the same prefix, just billing 90% less for it.

**Estimated $ impact (10k users):** ~**−$7.5k / month** on top of Step 2. Medium user: $1.62 → ~$0.85.

**Risk:** ADK/Vertex cache integration is preview-era APIs; semantics could shift. Keep a feature flag (`LIVE150_USE_EXPLICIT_CACHE=1`) to toggle off fast if anything breaks.

---

### Step 4 — Cap conversation history at 5 turns

**Why fourth:** small $ savings on its own, but keeps prompt size bounded as long sessions grow.

**Files:**

- `server/src/live150/agent/callbacks.py::before_model_cb` — add a trim step:
  ```python
  MAX_HISTORY_TURNS = 5  # = 10 Content entries (user + agent per turn)
  if hasattr(llm_request, "contents") and len(llm_request.contents) > MAX_HISTORY_TURNS * 2 + 1:
      # keep: last (MAX_HISTORY_TURNS * 2) prior entries + current user message
      new_message = llm_request.contents[-1]
      history = llm_request.contents[-(MAX_HISTORY_TURNS * 2 + 1):-1]
      llm_request.contents = history + [new_message]
  ```

- No changes to `session_service` / `InMemorySessionService` — we keep full history in the session for persistence and UI display, and only trim what we send to the model.

**What about older turns?** Reflection (`agent/reflection.py`) already extracts durable facts from every turn and writes them to pgvector. When the agent needs older context, it calls `search_memory`. No additional summarization step needed for v1.

**Verification:**
- Trigger a 12-turn conversation. Inspect `llm_request.contents` via a temporary debug log in `before_model_cb`. Expected length: 11 (10 history entries + 1 new message).
- Spot-check quality: does the agent still reference something the user said 8 turns ago? If yes, `search_memory` is doing its job via reflection facts. If no and it matters, consider adding a turn-summarizer later.

**Estimated $ impact (10k users):** ~**−$400 / month**. Modest, because 5-turn cap only activates on sessions that reach turn 6+ — most won't.

**Risk:** agent forgets mid-session context on long sessions. Mitigate by keeping reflection quality high so durable facts land in memory.

---

### Step 5 — Batch API for reflection + summaries

**Why fifth:** low-risk, low-effort, "last 10%" savings.

**Files:**

- `server/src/live150/agent/reflection.py` — switch from `client.aio.models.generate_content(...)` to `client.aio.batches.create(...)` with `inline_requests=[...]`. Today it runs as `asyncio.create_task` (fire-and-forget); move to an APScheduler job that flushes a batch of queued reflections every 15 minutes.
  - Needs a new lightweight `reflection_queue` table (or reuse `PendingConfirmation`-style in-memory queue — but persistence is safer across restarts).

- `server/src/live150/reminders/summary_jobs.py` — same pattern. Daily/weekly/monthly summaries are already cron-triggered; enqueue them into the same batch pipeline.

- One APScheduler job `drain_batch_queue` that polls batch job status and writes results to `MemoryEntry` on completion.

**Trade-off:** 24h latency on reflection. That means durable facts from today's conversations might not surface in `search_memory` until tomorrow. Product call — acceptable for a memory system that's already eventually-consistent.

**Verification:**
- Count `MemoryEntry` rows written per day before/after. Volume should be the same.
- Verify no regressions in "agent remembers that I said X yesterday" flows.

**Estimated $ impact (10k users):** ~**−$1k / month**.

**Risk:** batch completion failures leave reflections unlogged. Add retry + dead-letter to the drain job.

---

## Cumulative Savings Waterfall

Per-user monthly, medium tier:

| After step | Medium user $/mo | Cumulative saving vs. today |
|---|---|---|
| Today | $2.02 | — |
| + Step 2 (flat thinking=512) | $1.62 | 20% |
| + Step 3 (explicit caching) | $0.85 | 58% |
| + Step 4 (history cap 5 turns) | $0.81 | 60% |
| + Step 5 (batch background) | $0.70 | 65% |

At 10k users (15/50/35 mix):

| After step | Monthly $ | Saving vs. today |
|---|---|---|
| Today | ~$22.3k | — |
| + Step 2 | ~$17.9k | −$4.4k |
| + Step 3 | ~$10.4k | −$11.9k |
| + Step 4 | ~$10.0k | −$12.3k |
| + Step 5 | ~$9.0k | −$13.3k |

**Bottom line: ~60% cost reduction by stacking all five steps. ~$13k/mo back at 10k users.**

The scenario F number in `pricing-analysis.md` (~$5.7k/mo) was more aggressive because it assumed deeper thinking cuts and a 2-turn history cap. This plan's numbers are more conservative — they reflect the actual decisions above.

---

## Rollout Order & Gates

1. Ship **Step 1** (telemetry). No gate — merge when tested.
2. Wait 24h; verify audit rows populate correctly.
3. Ship **Step 2** (thinking=512). No gate.
4. Wait 7 days; check thinking-token average dropped and no quality complaints.
5. Review Step 3 decision gate (implicit-cache-hit rate from telemetry). If proceeding, ship explicit caching on a feature flag first.
6. Ship **Step 4** (history cap). No gate.
7. Ship **Step 5** (batch) last. Has the most moving parts.

---

## Metrics to Watch

Add these to a simple dashboard/query, refreshed daily:

- `avg(thoughts_tokens)` on interactive turns — target <500 after Step 2.
- `avg(cached_tokens / tokens_in)` on interactive turns — target >0.7 after Step 3.
- `p95(len(llm_request.contents))` — target <11 after Step 4.
- Daily `MemoryEntry` insert count — should be flat across the Step 5 rollout.
- Vertex spend per user per day (from billing export, joined on `tokens_in + tokens_out`) — the end-to-end truth.

---

## Checklist

### Step 1 — Telemetry
- [x] Add `cached_tokens` + `thoughts_tokens` columns to `AuditLog` model (`db/models/audit_log.py`)
- [x] Alembic migration `b2c3d4e5f6a7_audit_turn_metrics.py`
- [x] Extend `write_audit()` signature in `audit/logger.py`
- [x] Add `after_model_cb` to `agent/callbacks.py` (fires `asyncio.create_task` to persist)
- [x] Stash `_last_model` in `state` from `before_model_cb` so `after_model_cb` can read it
- [x] Wire `after_model_callback=after_model_cb` in `agent/builder.py`
- [ ] Run `alembic upgrade head` against staging + prod DBs
- [ ] After 24h live, verify rows populate: `SELECT event_type, AVG(tokens_in), AVG(tokens_out), AVG(cached_tokens), AVG(thoughts_tokens) FROM audit_log WHERE event_type='llm_call' AND created_at > NOW() - INTERVAL '24 hours' GROUP BY event_type;`
- [ ] Check implicit-cache baseline: `SELECT AVG(cached_tokens * 1.0 / NULLIF(tokens_in, 0)) FROM audit_log WHERE event_type='llm_call' AND created_at > NOW() - INTERVAL '24 hours';` — informs Step 3 decision gate

### Step 2 — Flat `thinking_budget=512`
- [x] Change `8192` → `512` at `agent/callbacks.py:66`
- [x] Run unit tests (`PYTHONPATH=src .venv/bin/pytest tests/unit -q`) — all 59 passing
- [ ] Deploy and run one interactive session end-to-end (chat UI) to confirm no regressions
- [ ] After 7 days of telemetry: confirm `AVG(thoughts_tokens)` on interactive turns dropped from ~1,500 to <500
- [ ] Spot-check 10 planning-style responses for quality regression; if bad, raise to 1024 or revisit tiered approach

### Step 3 — Explicit `CachedContent` (gated on Step 1 data)
- [x] `agent/caching.py` module — create/refresh/stop, `build_dynamic_context`, feature-flag gate
- [x] `agent/builder.py` — `_dynamic_instruction` returns empty string when cache is active
- [x] `agent/callbacks.py::before_model_cb` — clear `system_instruction`, set `cached_content`, prepend dynamic context to user message
- [x] `main.py` lifespan — create cache on startup + asyncio background refresh loop (every 50 min)
- [x] Unit tests for `is_enabled` and `build_dynamic_context` (test_caching.py)
- [ ] **v1 scope note:** only SOUL + AGENTS + IDENTITY (~7,850 tokens) are cached. Tool schemas (~5,200 tokens) remain in the per-request payload — implicit caching may still catch them. Revisit tool caching in v2.
- [ ] Pull 7-day cache-hit ratio from Step 1 telemetry to decide whether to flip flag on in prod
- [ ] Flip `LIVE150_USE_EXPLICIT_CACHE=1` in staging; run a chat session end-to-end; grep logs for `Explicit cache ready`
- [ ] Verify after rollout: `SELECT AVG(cached_tokens * 1.0 / NULLIF(tokens_in, 0)) FROM audit_log WHERE event_type='llm_call' AND created_at > NOW() - INTERVAL '1 hour';` — target > 0.6
- [ ] Flip on in prod once staging holds for 48h with no regressions

### Step 4 — History cap at 5 turns
- [ ] Add `MAX_HISTORY_TURNS = 5` trim step to `before_model_cb`
- [ ] Verify via debug log that `llm_request.contents` length ≤ 11 on a 12-turn conversation
- [ ] Quality spot-check: does agent still reference mid-session facts via `search_memory`?

### Step 5 — Batch API for reflection + summaries
- [ ] Refactor `agent/reflection.py` to enqueue into a `reflection_queue` table
- [ ] Refactor `reminders/summary_jobs.py` to submit via batch
- [ ] APScheduler `drain_batch_queue` job with retry + DLQ
- [ ] Verify `MemoryEntry` insert volume unchanged

---

## Open Items (not in this plan)

- **Session reuse audit.** `runner.py:75-92` runs `_fetch_user_context` on first turn per session. If the web app creates a fresh session per message, we repay the Live150 `get_initial_context` call every time. Non-Vertex cost, but worth a check. *Not addressed here.*
- **Per-skill thinking override.** If Step 2 + quality review shows certain skills (e.g. `cross-pillar-diagnosis`) degrade at 512, add a per-skill budget lookup. Revisit after 4 weeks of Step 2 data.
- **Tool-set pruning with cached variants.** The `pricing-analysis.md` §7.7 idea — defer until Step 3 is stable and we have cache-hit numbers to reason about.
