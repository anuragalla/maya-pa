# Maya PA — Pricing & Prompt-Caching Analysis

**Date:** 2026-04-19
**Scope:** What LLM inference costs per user per month on the current architecture, whether we are optimized for prompt caching, and what the optimization ceiling looks like. Supersedes two earlier drafts that (a) assumed a Flash/Flash-Lite blend and (b) assumed per-turn recomputation of the user profile summary. Both were wrong — see §0 below.

---

## 0. Corrections Since the Prior Draft

Two code re-reads change the baseline. Capturing them here so future readers don't inherit the old mistakes.

1. **We are already Flash-Lite-only.** `server/src/live150/agent/model_router.py:4-5` hardcodes both `DEFAULT_MODEL` and `LITE_MODEL` to `gemini-3.1-flash-lite-preview`. The "planning verbs route to Flash" logic is dead code for pricing purposes — it returns Flash-Lite either way. Earlier drafts modeled a 50/50 Flash/Flash-Lite split, which overstated the bill. `choose_model()` is still worth keeping as a signal for *thinking-budget tuning* (see §7.5), just not for model selection today.

2. **User profile summary is per-session, not per-turn.** `runner.py:75-92` only calls `_fetch_user_context` inside `if session is None:`. On subsequent turns the profile is reused from `session.state["user_profile_summary"]`. The only per-turn work is a local-time string format (trivial, no LLM, no API). A separate concern — but not a Vertex cost concern — is whether the web app creates fresh sessions for every message, which would repay the Live150 `get_initial_context` call. Worth checking, but it doesn't show up in the Vertex bill.

Both corrections lower the baseline ~20%.

---

## 1. TL;DR

- **Caching status: not enabled.** The prompt layout is accidentally well-shaped for implicit caching (stable 13K-token prefix first, dynamic context appended last), but no explicit `CachedContent` resource is created and we do not log whether Vertex's implicit cache actually hits.
- **Thinking is set to HIGH on every interactive turn** (`thinking_budget=8192` in `agent/callbacks.py:56`). Thinking tokens are billed as output, so this silently inflates output cost ~8× versus the answer alone. One-line change to scale down.
- **Cost today (all Flash-Lite, no caching, thinking HIGH):**
  - Light user: **~$0.99 / month**
  - Medium user: **~$2.02 / month**
  - Heavy user: **~$3.05 / month**
- **With explicit caching + batch for background + history cap + thinking tuning:** ~74% reduction. Medium user drops to **~$0.52 / month**.
- **All-on-Pro is not viable**: switching interactive to Gemini 3.1 Pro at MEDIUM thinking costs **~$12.76 / medium user / month** (+530% vs. today's $2.02). A hybrid where Pro handles only the ~10% hardest planning turns costs **~$3.02 / medium user / month** (+49%) and is the right target if we need Pro-level reasoning anywhere.
- **10k-user platform today:** roughly **$22.3k / month** in Vertex spend at a 15/50/35 light/medium/heavy mix. With all recommended optimizations, **~$5.7k / month**.

---

## 2. Current Gemini Pricing (Vertex AI, April 2026)

Verified against `cloud.google.com/vertex-ai/generative-ai/pricing` and the model-specific docs pages.

| Model | Input (≤200K) | Input (>200K) | Cached input | Output (≤200K) | Output (>200K) | Batch input | Batch output |
|---|---|---|---|---|---|---|---|
| **Gemini 3.1 Pro** | $2.00 / 1M | $4.00 / 1M | $0.50 / 1M (−75%) | $12.00 / 1M | $18.00 / 1M | $1.00 / 1M | $6.00 / 1M |
| **Gemini 3 Flash** | $0.50 / 1M | $0.50 / 1M | $0.05 / 1M (−90%) | $3.00 / 1M | $3.00 / 1M | $0.25 / 1M | $1.50 / 1M |
| **Gemini 3.1 Flash-Lite** ← *what we use* | $0.25 / 1M | $0.25 / 1M | $0.03 / 1M (−90%) | $1.50 / 1M | $1.50 / 1M | $0.13 / 1M | $0.75 / 1M |

Notes:
- **Cached input**: tokens read from a context cache (explicit or implicit). Flash / Flash-Lite get 90% off; Pro gets 75% off. **Flash-Lite has the best caching economics of the three.**
- **Batch pricing**: flat 50% discount, results returned within 24h. Usable for summaries/reflection; not for interactive or reminders.
- **Long-context surcharge**: Pro doubles both input and output prices above 200K tokens. Flash and Flash-Lite do not have this step. We stay well under 200K, so this doesn't bite today.
- **Explicit cache storage** for Pro is billed at $4.50 / 1M tokens / hour. Not a line item for Flash or Flash-Lite.
- Errors (4xx/5xx) are not billed.

### 2.1 Thinking levels and how they affect cost

All Gemini 3 models support "extended thinking" — a pre-response reasoning phase whose output is **billed as output tokens at the standard output rate**. There is no price multiplier on thinking tokens themselves; the cost pressure is the **volume** of additional output tokens produced.

| Model | Levels supported | Default | Typical thinking-token range (our workload) |
|---|---|---|---|
| **Gemini 3.1 Pro** | LOW / MEDIUM / HIGH | HIGH | 500 / 1,500 / 4,000+ |
| **Gemini 3 Flash** | MINIMAL / LOW / MEDIUM / HIGH | HIGH | 0–50 / 300 / 1,000 / 2,500+ |
| **Gemini 3.1 Flash-Lite** | MINIMAL / LOW / MEDIUM / HIGH | MINIMAL | 0–50 / 200 / 600 / 1,500+ |

**What we ship today** (from `agent/callbacks.py:56`):
- Interactive turns: `thinking_budget=8192` (HIGH / top-of-range for Flash-Lite).
- Reminder turns: `thinking_budget=0` (effectively MINIMAL — reasoning off).
- Reflection + summaries: default, which is MINIMAL on Flash-Lite (~0 thinking tokens in practice).

**The thinking-budget cost multiplier on outputs is significant.** A Flash-Lite interactive turn that returns a 200-token answer with HIGH thinking enabled actually bills around 1,700 output tokens (200 answer + ~1,500 thinking avg). At Flash-Lite's $1.50/M output rate, that's **8.5× the cost of the answer portion alone**. Over a medium user's 240 interactive turns/month, thinking alone costs ~$0.54 of the $2.02 bill — 27% of spend for pre-response tokens no user ever sees.

See `docs/cloud.google.com/vertex-ai/generative-ai/docs/thinking` for the raw API surface.

### 2.2 Models actually used in this codebase

| Use case | Model | Rationale (from code) |
|---|---|---|
| Interactive turn | Flash-Lite (`gemini-3.1-flash-lite-preview`) | `choose_model()` returns this unconditionally; `DEFAULT_MODEL == LITE_MODEL` in `model_router.py:4-5` |
| Reminder fire (background) | Flash-Lite | Same router; `turn_context="reminder"` adds `thinking_budget=0` |
| Reflection (post-turn) | Flash-Lite | `agent/reflection.py` |
| Daily/weekly/monthly summary | Flash-Lite | `reminders/summary_jobs.py` |
| Schedule parser (regex fallback) | Flash-Lite | `reminders/parser.py::_llm_parse` |

All Flash-Lite. Pricing therefore reduces to a single-model computation.

---

## 3. Prompt-Caching Posture

### 3.1 What Vertex needs to cache

Vertex AI supports two caching paths:

- **Implicit caching** — automatic. Fires when a request starts with ≥2,048 identical prefix tokens that Vertex has seen recently. 90% discount on cached tokens for Flash and Flash-Lite. Zero app changes required — you just need a stable prefix. Cache hits surface in `response.usage_metadata.cached_content_token_count`.
- **Explicit caching** — you create a `CachedContent` resource via the SDK, reference it by name in subsequent requests. More deterministic; for Pro it adds storage fees, for Flash-Lite there is no documented storage charge.

### 3.2 Current prompt layout (per turn)

From `server/src/live150/agent/builder.py::_dynamic_instruction` + `runner.py::run_turn`:

```
┌──────────────────────────────────────────────────────────── CACHEABLE
│ SOUL.md                              ~2,000 tokens
│ AGENTS.md                            ~5,500 tokens
│ IDENTITY.md                          ~350 tokens
│ (static base instruction)            ─────────
│                                      ~7,850 tokens
│                                      
│ Tool schemas (19 FunctionTools,      ~5,200 tokens
│   injected by ADK from registry.py)
│                                      ─────────
│                                      ~13,050 token stable prefix
├──────────────────────────────────────────────────────────── CACHE BREAKS HERE
│ ## Current context
│   - Local time: "Saturday, April 19 2026, 01:30 PM"
│   - Timezone, calendar status, pending signals   ~100 tokens
│   - User profile summary (fetched once/session, 
│     reused from session.state on every turn)     ~200–300 tokens
│                                      ~300–500 tokens per turn (dynamic)
├────────────────────────────────────────────────────────────
│ Conversation history (ADK replays full thread)
│                                      0 (fresh) to ~3,000 tokens (turn 5)
├────────────────────────────────────────────────────────────
│ User message                         ~100–300 tokens
└────────────────────────────────────────────────────────────
```

**Verdict:**
- ✅ Stable prefix is ~13,050 tokens — **6× the 2,048-token floor** needed for implicit caching.
- ✅ Static content is first, dynamic context second. That's the right order for caching.
- ✅ The profile summary does *not* break the cache more than it has to — it's fetched once per session in `runner.py::_fetch_user_context` and reused from `session.state` on every subsequent turn. Only the global static block + tool schemas sit in front of the cache boundary, so the profile appearing in the dynamic block is fine.
- ❌ No `cachedContent` references anywhere in the codebase. No logging of `cached_content_token_count`. We do not know whether implicit caching is firing in practice.
- ❌ Local time is rendered at minute granularity — every new minute creates a unique prompt, but this happens *after* the cacheable block, so that part doesn't hurt caching.

### 3.3 What we lose by not actively caching

On a medium user's 240 interactive turns/month, the 13,050-token stable prefix is sent 240 times = **3.13M input tokens of pure repetition**. At Flash-Lite's $0.25/1M input rate, that's **$0.78 / user / month** that could be 90% cheaper. Over 10k users that's roughly **$4.5–6.5k / month of recoverable spend** just from static-prefix caching. Smaller absolute number than the old Flash estimate, but it's the largest single lever on the bill.

---

## 4. Per-User Token Consumption (Current State, No Caching)

From the code audit — see `agent/builder.py`, `reminders/jobs.py`, `reminders/summary_jobs.py`, `agent/reflection.py`.

### 4.1 Cost per turn type

Output includes **thinking tokens where enabled**. See §2.1 for the thinking-budget settings currently in code.

| Turn type | Input tokens | Answer tokens | Thinking tokens | Total output | Model | Notes |
|---|---|---|---|---|---|---|
| Interactive, fresh session | 13,550 | 200 | ~1,500 | **1,700** | Flash-Lite | `thinking_budget=8192`; actual avg well below cap |
| Interactive, turn 5 (replayed history) | 16,650 | 200 | ~1,500 | **1,700** | Flash-Lite | +3,000 tokens of history; thinking same |
| Reminder fire | 11,350 | 100 | 0 | **100** | Flash-Lite | `thinking_budget=0`; reasoning off |
| Reflection (post-turn) | 2,500 | 50 | ~10 | **60** | Flash-Lite (MINIMAL default) | Fire-and-forget fact extraction |
| Daily summary | 4,000 | 100 | ~20 | **120** | Flash-Lite (MINIMAL) | |
| Weekly summary | 4,500 | 120 | ~20 | **140** | Flash-Lite (MINIMAL) | |
| Monthly summary | 5,000 | 150 | ~30 | **180** | Flash-Lite (MINIMAL) | |

### 4.2 Usage profiles

| Event | Light (15% DAU) | Medium (50% DAU) | Heavy (85% DAU) |
|---|---|---|---|
| Interactive turns | 120 / mo | 240 / mo | 360 / mo |
| Reminders fired | 30 / mo | 90 / mo | 150 / mo |
| Reflection runs | 120 / mo | 240 / mo | 360 / mo |
| Daily summary | 30 / mo | 30 / mo | 30 / mo |
| Weekly summary | 4 / mo | 4 / mo | 4 / mo |
| Monthly summary | 1 / mo | 1 / mo | 1 / mo |

### 4.3 Monthly tokens per user (thinking tokens included)

| | Light | Medium | Heavy |
|---|---|---|---|
| Input | 2,626,500 | 5,450,500 | 8,274,500 |
| Answer output | 21,150 | 33,150 | 45,150 |
| Thinking output (interactive only) | 180,000 | 360,000 | 540,000 |
| **Total output** | **~201,000** | **~393,000** | **~585,000** |
| **Total tokens** | **~2.83 M** | **~5.84 M** | **~8.86 M** |

Thinking tokens dominate output — ~92% of all output for a medium user.

### 4.4 Monthly $ cost per user (current defaults: all Flash-Lite, no caching, thinking HIGH)

| Cost bucket | Light | Medium | Heavy |
|---|---|---|---|
| Interactive input ($0.25/M) | $0.46 | $0.92 | $1.38 |
| Interactive output (answer + thinking, $1.50/M) | $0.31 | $0.61 | $0.92 |
| Reminders (input + tiny output) | $0.09 | $0.27 | $0.45 |
| Reflection | $0.09 | $0.17 | $0.26 |
| Summaries | $0.04 | $0.04 | $0.04 |
| **Total / user / month** | **$0.99** | **$2.02** | **$3.05** |

Prior draft said $1.18 / $2.51 / $3.83 — that was under a bad Flash/Flash-Lite blend assumption. Real figures above are ~20% lower.

### 4.5 Background / scheduler-driven LLM calls — what's counted

Reconciliation table so nothing scheduler-triggered gets missed.

| Job | Counted in §4.2? | Where it lives | Notes |
|---|---|---|---|
| `fire_reminder` (APScheduler → full agent turn) | ✅ yes | `reminders/jobs.py:147` | Uses `REMINDER_SAFE_TOOLS`, `thinking_budget=0` |
| Reflection (post-turn fact extraction) | ✅ yes | `agent/reflection.py` | Flash-Lite, MINIMAL thinking |
| Daily summary | ✅ yes | `reminders/summary_jobs.py::generate_daily_summary` | Flash-Lite |
| Weekly summary | ✅ yes | `reminders/summary_jobs.py::generate_weekly_summary` | Flash-Lite |
| Monthly summary | ✅ yes | `reminders/summary_jobs.py::generate_monthly_summary` | Flash-Lite |
| Schedule parser (NL → cron) | ❌ **missed**, but trivial | `reminders/parser.py::_llm_parse` | Flash-Lite, only fires when regex fast-path misses. ~2–10 calls/user/mo at ~2K input + 50 output. **~$0.003/user/mo.** Rounds to zero. |
| User profile fetch | n/a — no LLM | `runner.py::_fetch_user_context` | Live150 REST call; once per session. Check web client to confirm it reuses session IDs. |
| Calendar snapshot refresh | n/a — no LLM | `calendar/service.py::sync_snapshot` | Pure Google Calendar API |
| APScheduler itself | n/a — no LLM | `reminders/scheduler.py` | CPU/DB only |

**Verdict:** the baseline in §4.3 / §4.4 covers every LLM-spending scheduler job in code today, modulo $0.003/user/mo of parser calls.

### 4.6 Roadmap scheduler jobs — not yet built, not yet billed

`docs/spec/feature-spec.md` adds a set of proactive cron jobs. None are wired yet, so they don't appear in §4.4. Projected cost per medium user once they ship, at Flash-Lite:

| Future job | Cadence | Thinking | Per-fire input/output | $/user/mo |
|---|---|---|---|---|
| Morning brief (`daily-morning-brief` skill) | daily | HIGH | ~19K in + 1.7K out | **$0.22** |
| Evening wind-down (`evening-wind-down`) | daily | HIGH | ~19K in + 1.7K out | **$0.22** |
| Mood check-in | daily | LOW | ~11K in + 0.5K out | **$0.10** |
| Weekly health digest (PubMed + summarise) | weekly | MEDIUM | ~22K in + 1.5K out | **$0.03** |
| Meal plan + grocery list | weekly | LOW | ~15K in + 3K out | **$0.03** |
| Nutrition 6pm check-in (conditional) | daily | MINIMAL | ~3K in + 0.2K out | **$0.02** |
| Anomaly scan | hourly stats; LLM on flag (~5/mo) | MINIMAL | ~2K in + 0.1K out on flag | **$0.005** |
| Appointment prep / questions / follow-up | per appointment (~1/mo) | LOW | 3 fires × ~$0.005 | **$0.02** |
| Document OCR + classify | per upload (~2/mo) | MINIMAL | ~5K in + 0.5K out | **~$0** |
| **Roadmap subtotal** | | | | **~$0.65 / medium user / mo** |

That's a **~32% increase** on top of the $2.02 medium-user baseline, driven almost entirely by the two HIGH-thinking daily proactive agent turns (morning brief + evening wind-down). These are the most cost-sensitive new jobs on the roadmap; everything else rounds to noise. If we apply the same thinking-budget discipline from §7.5 to these (drop HIGH to LOW on the default brief, reserve HIGH for manual "deep dive" asks), the roadmap subtotal falls to ~$0.30/medium user/mo.

**Important design note on anomaly scan:** if we naively run a Flash-Lite LLM call hourly per user for baseline comparison, that alone is ~$0.24/user/mo — 50× more than the plan above. The cheaper path is to compute rolling mean/SD in Python and only invoke an LLM when a metric trips the 2-SD gate. Budget this as a stats job, not an agent job.

### 4.7 Post-roadmap cost projection (10k users, with all planned jobs)

Same 15/50/35 split from §5, adding the roadmap delta as a flat per-user cost (cron jobs fire regardless of DAU tier):

| Config | Current features | + Roadmap |
|---|---|---|
| No caching, thinking HIGH (today's defaults) | ~$22.3k / mo | **~$28.8k / mo** |
| + Explicit caching | ~$12.6k / mo | **~$17k / mo** |
| + All optimizations (thinking tuning + batch + history cap) | ~$5.7k / mo | **~$8k / mo** |

The roadmap adds ~$6.5k/mo at current defaults, ~$2.5k/mo after optimizations. Caching is a bigger lever after the roadmap lands than before, because every new proactive turn is another 13K-token prefix repetition.

### 4.8 What if we moved interactive to Gemini 3.1 Pro?

Sometimes proposed for accuracy on complex planning. Cost impact per medium user, off the Flash-Lite baseline:

| Config | Monthly cost | Δ vs. current ($2.02) |
|---|---|---|
| **Current: all Flash-Lite, thinking HIGH** | $2.02 | baseline |
| **All interactive on Pro, thinking MEDIUM** (~1,500 thinking tokens/turn) | ~$12.76 | **+530%** |
| **All interactive on Pro, thinking HIGH** (~4,000 thinking tokens/turn) | ~$19.96 | **+888%** |
| **Hybrid: Flash-Lite default, Pro only for ~10% planning turns, HIGH** | ~$3.02 | **+49%** |

Pro is **8× the input price and 8× the output price** of Flash-Lite — the gap is wider than against Flash. Routing to Pro for a minority of hard planning turns is defensible; routing wholesale is not, given that our current workload is overwhelmingly lookups + short advisory turns that Flash-Lite handles fine.

---

## 5. Cost Scenarios at 10k Users

Assumed distribution: 15% light (1,500 users), 50% medium (5,000), 35% heavy (3,500).

| Scenario | Light | Medium | Heavy | **Total / month** |
|---|---|---|---|---|
| **A. Current (all Flash-Lite, no caching, thinking HIGH on interactive)** | $1,485 | $10,100 | $10,675 | **~$22.3k** |
| **B. + Implicit caching** (70% of interactive+reminder turns cache-hit the 13K prefix) | $1,020 | $6,710 | $7,010 | **~$14.7k** |
| **C. + Explicit caching** (90% of those turns cache-hit) | $890 | $5,740 | $5,960 | **~$12.6k** |
| **D. + Batch for background jobs** (reflection + summaries, −50%) | $795 | $5,205 | $5,430 | **~$11.4k** |
| **E. + Conversation history cap** (2 turns inline; older via `search_memory`) | $730 | $4,765 | $4,975 | **~$10.5k** |
| **F. + Thinking-budget tuning** (HIGH → LOW on default interactive; ~80% thinking-token reduction) | $405 | $2,605 | $2,705 | **~$5.7k** |

**Potential savings vs. today: 74% (~$16.6k / month).**

Caveats:
- Cache-hit rates are estimates. Implicit caching on Vertex typically holds for a few minutes; within a session you'll hit it reliably, across sessions less so. Explicit caching is deterministic.
- Batch sacrifices latency (≤24h). Fine for summaries, borderline for reflection — we'd want to verify user-perceived memory recall isn't degraded if reflection lags a day.
- History cap (E) requires a product decision: how much history should the agent "remember inline" vs. retrieve from memory. Current code replays everything, which is expensive and unnecessary given we already have pgvector-backed memory.
- Thinking tuning (F) is where the biggest single remaining lever sits. At $1.50/M output on Flash-Lite, each 1K thinking tokens we save across a medium user's 240 interactive turns saves $0.36/mo; dropping the average from 1,500 → 300 tokens saves ~$0.43/user/mo.

---

## 6. Where the Money Actually Goes (Medium User)

Breaking down the $2.02 / month medium-user bill:

| Bucket | % of bill | $ |
|---|---|---|
| Interactive input (13K static prefix × 240 turns + history) | ~46% | $0.92 |
| Interactive thinking output (360K tokens @ $1.50/M) | ~27% | $0.54 |
| Reminders (input-dominated) | ~13% | $0.27 |
| Reflection | ~8% | $0.17 |
| Interactive answer output (48K tokens) | ~4% | $0.07 |
| Summaries | ~2% | $0.04 |

**Two cost centers account for 73% of the bill:** static-prefix repetition (46% — fixed by caching) and thinking-token inflation on interactive output (27% — fixed by tuning `thinking_budget`). Both are one-line config changes.

---

## 7. Recommendations, Ranked by $ Impact

### 7.1 Turn on explicit context caching for the static prefix (highest impact)

- One `CachedContent` resource per platform release, containing SOUL.md + AGENTS.md + IDENTITY.md + tool schemas.
- TTL = e.g. 1 hour, refreshed by a cron (or on-demand on cache miss).
- Change location: `agent/builder.py` — pass `cachedContent` reference in `GenerateContentConfig` instead of inlining the static text.
- **Estimated savings:** ~$10k / month at 10k users (scenario C − A).
- Flash-Lite gets 90% off cached input and has no documented storage fee, so this is cheap to run.

### 7.2 Instrument cache hit rate + thinking token usage

- Log `response.usage_metadata.cached_content_token_count` and `thoughts_token_count` on every call.
- Add both to the existing `AuditLog` table (`audit/logger.py`).
- Without this, we cannot tell if caching is working or whether thinking-budget changes actually reduce spend. **Free; should ship first.**

### 7.3 Tune `thinking_budget` per turn type (second-biggest lever)

- Today: interactive turns get `thinking_budget=8192` (HIGH). Actual use averages ~1,500 tokens, but that's still ~360K tokens/medium-user/mo.
- Proposal, simplest first cut: drop to a flat `thinking_budget=512` for all interactive turns. Expected saving: ~$0.43/medium user/mo (~$4k/mo at 10k users). Fully reversible.
- Stretch option: tiered by `choose_model()`'s planning signal — 0 for short lookups, 512 default, 2048 when planning verbs fire. Adds complexity; only worth it if (b) doesn't hold quality.
- Change location: `agent/callbacks.py::before_model_cb` lines 55–60.
- Reminder turns already set `thinking_budget=0`; leave alone.

### 7.4 Cap conversation history; lean on memory

- Today: `Runner` (via ADK) replays the full `ChatMessage` history each turn. Mid-session turns carry +3,000 tokens.
- Change: keep last 2 user+assistant turns inline, summarize older turns into a `MemoryEntry` on session close, retrieve via `search_memory` when relevant.
- **Estimated savings:** ~$900 / month at 10k users. Also shortens prompts → faster TTFB.

### 7.5 Move reflection + summaries to Batch API

- Reflection (`agent/reflection.py`) is already fire-and-forget async. It does not need real-time completion. Enqueue to Batch, process within 24h.
- Daily/weekly/monthly summaries (`reminders/summary_jobs.py`) have no latency requirement beyond "before the next summary window."
- **Estimated savings:** ~$1k / month at 10k users. Small, but free.

### 7.6 Reserve Pro for planning turns only (if we ever need it)

- Adding Pro to the router at 10–15% of interactive turns preserves quality on the hardest asks and costs ~$1.00/medium-user/month (see §4.8). Full Pro routing is not economic.
- Change location: add a `PRO_TRIGGERS` list (multi-step planning, cross-pillar diagnosis, weekly review) to `model_router.py` and route those to Pro at MEDIUM thinking.
- Order of operations: do this after caching is on. Pro's cached-input discount is 75% vs. 90% on Flash-Lite, so Pro gains less from caching.
- Skip entirely if Flash-Lite quality is acceptable — which the product team has signaled it is.

### 7.7 Prune tool schemas per turn context (later)

- Interactive turns don't need every tool every time. Reminder turns already get a filtered list via `REMINDER_SAFE_TOOLS`.
- If we classify intent early (e.g. Flash-Lite pre-routing) we could pass only the relevant ~5 tools for 80% of turns → drop ~3,500 tokens per interactive turn.
- **Estimated savings:** ~$1–2k / month but **breaks the single-cache-prefix approach** unless we maintain 3 pre-built `CachedContent` variants (full, reminders-safe, lookup-only).
- Only worth it after §7.1 is in place and measured.

### 7.8 Do not

- Don't swap Flash-Lite for Flash as default — we'd ~2× interactive input cost for no clear quality benefit in this workload.
- Don't move interactive to Pro wholesale — see §4.8.
- Don't introduce per-user explicit caches. Profile summaries change often enough that maintenance cost exceeds savings.
- Don't kill thinking entirely without A/B testing — the cost of a visibly-worse agent exceeds the ~$0.54/user/mo savings.

---

## 8. Sensitivity of These Numbers

What could blow this analysis up:

- **If interactive usage is 3× what we assumed** (power-user scenario), heavy-user cost goes to ~$9/mo — still fine per user, but at scale a 10k platform crosses $55k/mo without caching. Caching matters more, not less, at higher usage.
- **If we add RAG-style memory retrieval that dumps 2–4K tokens into the prompt** per turn, that bypasses the cache. Keep retrieved memory *after* the static prefix, same slot as the current dynamic context block.
- **If Vertex changes pricing** (they cut Gemini prices twice in 2025), these absolute numbers drop, but the relative ordering and caching ROI don't.
- **If the web app creates a fresh session per message** instead of reusing session IDs, we pay the Live150 `get_initial_context` call (non-LLM) every turn. Worth checking but doesn't affect the Vertex bill.
- **If we move off Vertex to the AI Studio Gemini API**, pricing is the same. Batch and caching are also identical.

---

## 9. Action Items (Ordered)

1. **Add cache-hit + thinking-token telemetry** to `AuditLog`. Log `cached_content_token_count` and `thoughts_token_count` on every call. Zero-risk. *Do first.*
2. **Verify implicit caching fires today** via the new telemetry. If hit rates are already 60%+, the first two savings scenarios compress.
3. **Tune `thinking_budget` down from 8192.** Start with a flat `512` on interactive. Second-biggest win; one-line config change.
4. **Ship explicit `CachedContent` for the static prefix.** Biggest single $ win at 10k+ users.
5. **Cap conversation history at 2 turns inline + summary into memory.** Product decision; test agent coherence before rollout.
6. **Move reflection and summary jobs to Batch API.** Small win, low risk.
7. **Evaluate Pro for planning turns only** if Flash-Lite quality gaps emerge.
8. **Revisit tool-set pruning with cached variants** after (4) is validated.

---

## Sources

- [Vertex AI Pricing — Google Cloud](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- [Gemini 3.1 Pro — Generative AI on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-1-pro)
- [Gemini 3 Flash — Generative AI on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash)
- [Gemini 3.1 Flash-Lite — Generative AI on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-1-flash-lite)
- [Thinking — Vertex AI docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/thinking)
- [Context caching overview — Vertex AI docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/context-cache/context-cache-overview)
- [Gemini 3.1 Pro Pricing 2026: Token Costs, Caching, Thinking Tokens — Verdent](https://www.verdent.ai/guides/gemini-3-1-pro-pricing)
- [Gemini 3.1 Flash Lite: Our most cost-effective AI model yet — Google blog](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-flash-lite/)
- [Gemini API Pricing 2026 — MetaCTO](https://www.metacto.com/blogs/the-true-cost-of-google-gemini-a-guide-to-api-pricing-and-integration)
