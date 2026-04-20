# Maya PA — Feature Spec (Architecture-Aligned)

**Goal.** Deliver the capabilities described in the original Maya PA feature sheet (reminders, scheduling, research, nutrition, data aggregation, mood, routines, documents, integrations) on the architecture this repo actually has.

**Non-goal.** Building an "Agent Roster." The original spec listed nine named sub-agents (ReminderAgent, SchedulerAgent, ResearchAgent, etc.). We do **not** implement those as separate ADK agents. This repo is a single-agent architecture; those roles are expressed as **tools, skills, scheduler jobs, and LLM prompts**, not as runtime processes.

---

## 1. Architecture Primer

One ADK `LlmAgent` built in `server/src/live150/agent/builder.py`, driven by:

- **Prompt stack** — `SOUL.md` + `AGENTS.md` as static instructions; dynamic per-turn context (timezone, profile, calendar status) injected via `builder.py::_dynamic_instruction()`.
- **Model routing** (`agent/model_router.py`) — Flash-Lite for simple turns, Flash for planning/advice.
- **Tool registry** (`tools/registry.py`) — `FunctionTool`-wrapped async functions; auth/user state flows via `tool_context.state`.
- **Skills** (`agent/skills/<name>/SKILL.md`) — markdown runbooks the agent searches (`skill_search`) and loads (`skill_load`) on demand.
- **Scheduler** (`reminders/scheduler.py`) — APScheduler + Postgres job store. Jobs run in a dedicated `scheduler` container; the agent container runs APScheduler in paused mode.
- **Memory** (`memory/service.py`) — pgvector (768-dim, Vertex `text-embedding-005`) + BM25 hybrid; reflection captures facts post-turn (`agent/reflection.py`); system-generated daily/weekly/monthly summaries.
- **Calendar** (`calendar/service.py`) — provider protocol, Google wired; a private Live150 sub-calendar holds agent-created events; 7-day snapshots in Postgres.
- **Live150 client** (`live150_client/client.py`) — wraps the 5 health endpoints we call today.
- **Delivery** — SSE (`api/chat.py`) for legacy chat, Vercel AI data-stream (`api/stream.py`) for the current web UI; proactive output goes through the Live150 Notify API and a short-TTL in-memory poll queue (`api/notifications.py`).
- **Auth** (`auth/middleware.py`) — `X-Phone-Number` header → impersonation → access token cached per request.
- **Safety** (`safety/write_gate.py`) — `PendingConfirmation` table + approve/reject routes; not yet bound to any tool.
- **Audit** (`audit/logger.py`) — `AuditLog` table; ready for instrumentation.

### 1.1 How original "agents" map onto this architecture

| Original agent | Mapped onto |
|---|---|
| Maya (Orchestrator) | The single ADK agent + `AGENTS.md` routing prompt. No event bus. |
| ReminderAgent | `reminder_tools.py` + `reminders/scheduler.py` + `reminders/jobs.py`. Already built. |
| SchedulerAgent | New `appointment_tools.py` + calendar mirror + `scheduler-prep` / `scheduler-followup` skills + cron jobs. Reuses existing calendar stack. |
| ResearchAgent | New `research_tools.py` (PubMed/feeds) + `weekly-digest` skill + weekly cron summary job. |
| NutritionAgent | Existing `get_meal_plan` tool + new `grocery_tools.py` + `meal-plan-weekly` skill + weekly cron. |
| DataAgent | Existing Live150 health tools + new `HealthMetric` ingest + anomaly cron + new `wearable_tools.py`. |
| RoutineAgent | Existing `daily-morning-brief` + `evening-wind-down` skills + morning cron that fires them. No new code. |
| MoodAgent | New `mood_tools.py` (log + query) + daily check-in cron + `mood-escalation` skill. |
| DocAgent | New `documents` model + OCR worker + `document_tools.py` + pre-appointment surface logic. |

The agent does not "route events" to sub-agents. It **loads a skill** when the user's intent matches, or **a cron job fires it with a prompt** that references a skill.

---

## 2. Event Model (replacement for the "event bus" in the original spec)

The original spec described typed events (`MEDICATION_DUE`, `ANOMALY_DETECTED`) flowing through Maya. In this architecture there is no bus. Instead, each "event" becomes an **APScheduler job** that does one of two things:

1. **Enqueue a proactive turn** — runs the agent with `turn_context="reminder"` and a machine-generated user-facing prompt (e.g. *"Time for your Omega-3"*). Flow exists today in `reminders/jobs.py::fire_reminder`.
2. **Write a record and flag Maya for the next interactive turn** — e.g. anomaly detection writes a `SystemSignal` row; the agent's dynamic instruction picks it up on the next user turn.

Everything that the original spec called "an event" resolves to one of these two patterns. We do not introduce a generic event bus.

---

## 3. Feature 1 — Reminders (partially built)

**Status.** Core flow exists: parser, scheduler, fire, notify, mirror-to-calendar. Needs domain typing, ack flow, and wearable-aware smart triggers.

### 3.1 Gaps vs. the original spec

| Feature | Required change |
|---|---|
| Reminder `type` (medication / supplement / hydration / lab / screening / movement / sleep) | Add `reminder_type` column + enum on `Reminder` model. Used for filtering, skill selection, and escalation rules. |
| `ack_required` + streak | Add `ack_required: bool`, `streak: int`, `last_ack_at: datetime`. New endpoint `PATCH /api/v1/reminders/{id}/ack`. Follow-up job scheduled 30 min out at fire time, cancelled on ack. |
| Sleep-aware delay | `jobs.py::fire_reminder` checks latest sleep sample (see Feature 5). If asleep now or <30 min ago, re-queue +30 min. |
| HRV-drop smart trigger | Background job `anomaly_scan` (hourly) emits a one-off reminder with `prompt_template="stress-relief check-in"` when HRV < baseline − 2 SD. |
| Escalation on 3 misses | Counter in `Reminder.consecutive_misses`. On 3, enqueue a one-off interactive reminder with `skill=red-flag-routing` hint in prompt template. |

### 3.2 New / changed code

- `db/models/reminder.py` — new columns above + Alembic migration.
- `reminders/jobs.py::fire_reminder` — consult wearable snapshot before sending, schedule follow-up job if `ack_required`.
- `reminders/ack.py` *(new)* — ack service + streak update.
- `api/reminders.py` — add `PATCH .../ack`.
- No new ADK tools; existing `create_reminder` / `list_reminders` / `cancel_reminder` gain the new fields via their schemas.

---

## 4. Feature 2 — Appointment Scheduling (new)

**Status.** Not started. Reuses calendar stack.

### 4.1 Data model

`db/models/appointment.py` (new)

| Field | Notes |
|---|---|
| `appointment_id` (uuid PK) | |
| `user_id` | |
| `provider_name`, `location`, `notes` | |
| `appointment_type` enum | checkup / specialist / lab / telehealth / dental / therapy |
| `status` enum | scheduled / confirmed / completed / cancelled / missed |
| `start_at`, `end_at`, `timezone` | |
| `calendar_event_id` (nullable FK) | If mirrored to user's calendar via `CalendarService` |
| `prep_checklist` (JSONB) | Generated by `appointment_prep` skill |
| `questions_for_doctor` (JSONB) | Generated from recent biomarkers |
| `followup_notes` (text) | Captured after the visit |
| `source` enum | user / agent / deeplink / partner_api |
| `external_booking_id` (nullable) | For ZocDoc/LabCorp partner APIs later |

### 4.2 Tools (`tools/appointment_tools.py`)

- `create_appointment(provider, type, start_at, ...)`
- `list_appointments(status=?, from=?, to=?)`
- `update_appointment(id, ...)`
- `cancel_appointment(id)`
- `generate_doctor_questions(appointment_id)` — internal tool that pulls `get_holistic_analysis` + recent lab docs and writes `questions_for_doctor`.

### 4.3 Skills

- `appointment-prep` (new) — 24h-before prep checklist. Reads appointment type, adds fasting/ID/insurance items.
- `appointment-questions` (new) — 2h-before. Pulls latest biomarkers, produces 3–5 targeted questions.
- `appointment-followup` (new) — 4h-after. Captures what happened, extracts reminders (via `create_reminder`) and adds followup items.

### 4.4 Scheduler jobs

At `create_appointment` time, we register three APScheduler one-off jobs using the existing scheduler and reminder-safe-tool gate:

- `appointment_prep_{id}` — fires 24h before, loads `appointment-prep` skill.
- `appointment_questions_{id}` — fires 2h before, loads `appointment-questions`.
- `appointment_followup_{id}` — fires 4h after, loads `appointment-followup`.

Registered via a thin `appointments/jobs.py` that mirrors `reminders/jobs.py`. Cancellation/updates re-key the jobs; mirror to Live150 sub-calendar is through the same `CalendarService.create_live150_event()` used for reminders.

### 4.5 API

```
GET    /api/v1/appointments
POST   /api/v1/appointments
PATCH  /api/v1/appointments/{id}
DELETE /api/v1/appointments/{id}
POST   /api/v1/appointments/{id}/prep          # kicks the prep skill early
POST   /api/v1/appointments/{id}/followup      # kicks the followup skill early
```

### 4.6 Integrations (later)

ZocDoc / LabCorp / Quest deep-links stored as `external_booking_id` with `source=deeplink`. Native partner APIs slot in as new methods on an `AppointmentProvider` protocol analogous to `CalendarProvider`.

---

## 5. Feature 3 — Health Research Briefings (new)

**Status.** Not started. Weekly job + a new tool + existing memory stack.

### 5.1 Tools (`tools/research_tools.py`)

- `search_pubmed(query, limit=5)` — async HTTP to PubMed E-utilities.
- `search_health_feeds(query, limit=5)` — curated RSS (Huberman, Attia, Peter etc. — config list).
- `explain_lab_values(document_id)` — given a `Document` row with parsed lab JSON, produce a per-marker explainer (range, meaning, actions).

### 5.2 Skill

`weekly-health-digest` (new). Fetches top goals + flagged biomarkers from `get_initial_context` + `get_holistic_analysis`, calls `search_pubmed` / `search_health_feeds` with derived queries, summarises top 3 in 2–3 plain sentences each, scores relevance, saves a `MemoryEntry(kind=event, source=system, metadata={'kind':'digest'})`.

### 5.3 Scheduler

One cron job per user, Sunday 9am local (stored in `UserProfile.timezone`). The existing `summary_jobs.py` pattern is the template — add `generate_weekly_digest()` alongside the existing weekly summary.

### 5.4 Delivery

Push via Notify API with a short teaser; full digest readable in-app (agent re-renders from memory on request).

---

## 6. Feature 4 — Nutrition & Grocery (mostly new)

**Status.** `get_meal_plan` tool exists for the paid Live150 meal-plan endpoint. Grocery list and deficiency logic is new.

### 6.1 Data model

`db/models/meal_plan.py` — local cache of weekly plan JSON (protocol, meals dict, generated_at, week_of).
`db/models/grocery_list.py` — `{items: [{item, qty, category, checked}]}`, status (`active` / `ordered` / `archived`).

### 6.2 Tools (`tools/nutrition_tools.py`)

- `get_this_weeks_meal_plan()` — reads local cache or falls through to Live150 `get_meal_plan`.
- `generate_grocery_list(meal_plan_id)` — LLM ingredient extraction + category grouping. Flash-Lite sufficient.
- `get_grocery_list(status='active')`, `update_grocery_item(list_id, item_idx, checked=true)`.
- `flag_daily_targets()` — at 6pm local, checks today's logged NAMS (`log_nams` exists) against protein/fiber targets from `get_initial_context`; returns a shortfall list.

### 6.3 Skill

`meal-plan-weekly` (new) — Sunday evening job. If Live150 has a plan, cache it; otherwise LLM-generate from dietary restrictions + `deficiency_flags` derived from recent lab docs. Then call `generate_grocery_list`.

### 6.4 Scheduler

- Weekly: `meal_plan_refresh` (Sunday 6pm local).
- Daily: `nutrition_checkin_6pm` — if `flag_daily_targets()` is non-empty, push a gentle nudge through Notify.

### 6.5 Integrations (later)

Instacart Connect and chain APIs plug in as `GroceryProvider` implementations analogous to `CalendarProvider`. One-tap order adds a new `integration_tools.request_integration_connect("instacart")` target and a `submit_grocery_order(list_id)` tool.

---

## 7. Feature 5 — Health Data Aggregation (new, large)

**Status.** Live150 already serves aggregated analyses via `get_holistic_analysis` and `get_progress_by_date`. We do not re-ingest that data. What we add is **wearable-source metrics** that we own locally, so scheduler jobs can reason about them (sleep-aware reminder delay, HRV anomaly, etc.).

### 7.1 Data model

`db/models/health_metric.py`:

| Field | Notes |
|---|---|
| `metric_id` (uuid) | |
| `user_id` | |
| `source` enum | apple_health / google_fit / oura / whoop / manual |
| `metric_type` enum | steps / hrv / sleep_minutes / resting_hr / spo2 / weight / bp_sys / bp_dia / glucose / mood / energy |
| `value` (float), `unit`, `recorded_at` | |
| `raw_payload` (JSONB) | For later re-parse |

Index on `(user_id, metric_type, recorded_at desc)`.

### 7.2 Ingest paths

- **Push ingest** — `POST /api/v1/health-metrics/batch` accepts normalized samples from the mobile app's HealthKit / GoogleFit bridge.
- **Provider pull** — for Oura / Whoop, use the existing `OAuthToken` encryption + new `integrations/registry.py` entries; a 15-min APScheduler cron syncs per connected provider.

Normalization is a small dispatcher in `health/normalize.py` (new).

### 7.3 Tools (`tools/health_metric_tools.py`)

- `get_recent_metrics(metric_type, lookback='7d')`
- `get_metric_baseline(metric_type, window='30d')`

Used by `fire_reminder` (for sleep-aware delay) and by the anomaly cron.

### 7.4 Scheduler

- `wearable_sync` — every 15 min per provider.
- `anomaly_scan` — hourly. For each user, compute 30d baseline per metric; flag if latest < baseline − 2SD (or > +2SD). Writes a `SystemSignal` row and, if severity is high, enqueues a one-off proactive reminder.

### 7.5 `SystemSignal` table (new)

Lightweight: `{signal_id, user_id, kind, payload, created_at, consumed_at}`. The agent's dynamic instruction reads pending signals for this user and appends them to the prompt on the next interactive turn.

### 7.6 Pre-appointment PDF (later)

`POST /api/v1/appointments/{id}/export_pdf` — renders recent metrics into a one-page summary for the doctor. Uses ReportLab or WeasyPrint.

---

## 8. Feature 6 — Mood + Routines (mostly prompts)

**Status.** The skill infrastructure already covers the routine half.

### 8.1 MoodAgent equivalent

`db/models/mood_log.py` — `{log_id, user_id, mood_score (1-5), stress (1-5), note, recorded_at}`.

Tools (`tools/mood_tools.py`):
- `log_mood(score, stress, note=?)`
- `get_recent_moods(days=14)`

Skill `mood-escalation` (new):
- On 3 days of `mood ≤ 2` → soft prompt (breathing, journaling).
- On `mood ≤ 1 AND stress ≥ 4` → hard escalation; defers to existing `red-flag-routing` skill (which already exists in `agent/skills/`).

Scheduler:
- Daily `mood_checkin` at 8am local. Fires a proactive turn whose prompt says "run the mood-checkin skill". If no user reply within 6h, mark skipped (still eligible for the 3-day streak check).

### 8.2 RoutineAgent equivalent

No new code. The existing skills `daily-morning-brief` and `evening-wind-down` are the RoutineAgent. We add two scheduler jobs:

- `morning_brief` — 7am local, loads `daily-morning-brief` with inputs: `get_holistic_analysis`, last night's `sleep_minutes` + `hrv`, today's calendar load from `CalendarService.list_upcoming_user_events`, latest `mood_log`. The skill already specifies the output shape.
- `evening_winddown` — 9pm local, loads `evening-wind-down`.

The HRV-low / poor-sleep swap ("HIIT → Zone 2") is expressed inside the skill prompt, not in Python.

---

## 9. Feature 7 — Documents (new)

**Status.** Not started.

### 9.1 Data model

`db/models/document.py`:

| Field | Notes |
|---|---|
| `document_id` (uuid) | |
| `user_id` | |
| `doc_type` enum | lab_result / prescription / insurance / imaging / visit_note / vaccine / other |
| `storage_uri` (text) | GCS path |
| `original_filename`, `mime_type`, `size_bytes` | |
| `extracted_text` (text) | OCR output |
| `summary` (text) | LLM 2-sentence |
| `tags` (text[]) | |
| `structured` (JSONB) | For lab_result: `{markers: [{name, value, unit, range_low, range_high}]}` |
| `expiry_alert_date` (date, nullable) | For prescriptions |
| `uploaded_at`, `processed_at` | |

Also `source` enum (`app_camera`, `file_upload`, `email_forward`).

### 9.2 Upload surfaces

- `POST /api/v1/documents` — multipart upload from the app.
- `POST /api/v1/documents/email-ingest` — webhook for `docs@live150.ai` (SendGrid inbound or equivalent). Stubbed for MVP; main surface is in-app upload.

### 9.3 Processing pipeline

APScheduler worker `documents.process_document(document_id)`:
1. OCR via Google Vision (already a GCP project; reuses `google-cloud-vision`).
2. LLM classifier (Flash-Lite, `response_schema` Pydantic) → doc_type, title, summary, tags, structured payload.
3. If `doc_type=lab_result` → write/update `HealthMetric` rows for each recognized marker.
4. If `doc_type=prescription` → set `expiry_alert_date = fill_date + days_supply - 7` and register a one-off APScheduler job that creates a renewal reminder.

### 9.4 Tools (`tools/document_tools.py`)

- `list_documents(doc_type=?, limit=?)`
- `get_document(id)` (returns summary + structured; raw text only on request)
- `explain_document(id)` — delegates to `research_tools.explain_lab_values` for labs.

### 9.5 Pre-appointment surface

`appointment_prep` skill includes a step: "call `list_documents(doc_type=lab_result, limit=3)` and surface the 3 most recent" — no new code beyond adding the step.

---

## 10. Feature 8 — External Integrations

### 10.1 Calendar

**Built.** Google via `oauth/google.py` + `calendar/providers/google.py`. Read user events, write into a Live150 sub-calendar. Outlook/Apple slot in as additional `CalendarProvider` implementations — no interface changes required.

### 10.2 Wearables

Normalize into `HealthMetric` (see §7). Provider table entries in `integrations/registry.py`:

- Oura — OAuth already supported in `oauth/providers.py` shape.
- Whoop — same.
- Apple Health / Google Fit — mobile-app-owned. Server exposes `POST /api/v1/health-metrics/batch`; app pushes deltas every 15 min when it has a foreground window.

### 10.3 Lab booking / Doctor booking

MVP: deep links stored on `Appointment.external_booking_id` with `source=deeplink`. No server-side integration. Upgrade path: `AppointmentProvider` protocol (mirrors `CalendarProvider`) with ZocDoc / LabCorp implementations after partner approval.

### 10.4 Grocery

Instacart Connect as universal fallback; native chain APIs behind a `GroceryProvider` protocol. First wire is read-only (pricing / availability); write (order placement) gated through `safety/write_gate.py` (see §12).

### 10.5 Gmail / Drive

OAuth skeleton exists for these (`claude_ai_Gmail__authenticate` is unrelated — that's a Claude.ai MCP, not this product). For the Maya side, new `oauth/providers.py` entries + read-only tools `gmail_search(query)`, `drive_search(query)` when a real use case lands. Not MVP.

---

## 11. Delivery Channels

| Channel | Transport in this repo |
|---|---|
| In-app push | Notify API from `reminders/notify.py::NotifyClient`. Used by `fire_reminder`, mood check-in, anomaly flags, grocery nudges, appointment prep/questions/followup. |
| In-app card / WebSocket | We don't have a WebSocket today; the web UI reads the Vercel AI data-stream (`api/stream.py`) during active sessions and polls `GET /api/v1/notifications` when idle. For MVP, replace "WebSocket card" with either (a) a new banner UI fed by `GET /api/v1/notifications` or (b) an SSE channel on top of the existing FastAPI router. Preference: (a) — no new transport. |
| Maya chat bubble | Interactive turn through `POST /api/v1/stream/chat`. Same turn runs the skill and streams the reply. |

### 11.1 Standard message payload

Retain the original spec's JSON shape because it maps cleanly onto the Notify API:

```json
{
  "agent": "Maya",
  "type": "reminder | digest | appointment_prep | mood_checkin | anomaly | doc_expiry",
  "urgency": "CRITICAL | HIGH | MEDIUM | LOW | INFO",
  "channel": ["push", "in_app"],
  "title": "Supplement Reminder",
  "body": "Time for your Omega-3!",
  "actions": ["Done ✓", "Snooze 30min"],
  "meta": { "reminder_id": "uuid" }
}
```

`agent` is always `"Maya"` (single agent). `type` identifies which flow produced it.

---

## 12. Memory

No architectural change. The existing `MemoryService` (`memory/service.py`) is sufficient for:

- **User facts** — captured by `agent/reflection.py` post-turn.
- **System summaries** — daily / weekly / monthly (`summary_jobs.py`); extend with the weekly digest (§5).
- **Agent-saved notes** — `save_memory` tool.

For per-feature surfaces:

- Appointment followup notes → plain column, not memory.
- Document summaries → embed on processing completion (write a `MemoryEntry` with `kind=note, source=system, metadata={doc_id}`).
- Grocery items, mood scores, metrics → structured columns, never embedded.

Rule: if retrieval needs semantic search, embed. If retrieval is "last N by timestamp" or "by id", a plain column is correct.

---

## 13. Safety Gate (cross-cutting)

`safety/write_gate.py` + `PendingConfirmation` are built but unused. Bind them to these tool calls:

- `submit_grocery_order` (placing money)
- `create_appointment` when `source=partner_api` (external booking)
- `submit_lab_booking` (partner API)
- `cancel_appointment` (irreversible; partner-side)
- `delete_document` (if we add it)

Pattern: tool returns a `PendingConfirmation` dict instead of executing. The agent renders the confirmation UI; user hits `POST /api/v1/confirmations/{id}/approve`, and a small resolver actually executes the tool body.

`create_reminder`, `log_mood`, `log_nams`, `save_memory` do **not** gate — they're cheap and reversible.

---

## 14. Audit (cross-cutting)

Instrument `before_model_cb` and `before_tool_cb` (`agent/callbacks.py`) to write `AuditLog` rows. Include:

- `tool_call` events with args hash (not raw args — they can contain PHI).
- `confirmation_approved` / `confirmation_rejected`.
- `proactive_fire` for any scheduled job that runs the agent.

This lands as a small change in `callbacks.py`; no new tables.

---

## 15. Sprint Roadmap (adjusted)

| Week | Ship | Files touched |
|---|---|---|
| 1 | Reminder typing + ack + follow-up + sleep-aware delay. `HealthMetric` model + `/api/v1/health-metrics/batch` + mobile push contract. Audit instrumentation. | `db/models/reminder.py`, `db/models/health_metric.py`, `reminders/jobs.py`, `api/reminders.py`, `api/health_metrics.py` (new), `agent/callbacks.py` |
| 2 | Appointments (model, tools, routes, prep/questions/followup skills + jobs, calendar mirror). Wearable pull for Oura/Whoop + hourly anomaly scan. | `db/models/appointment.py`, `tools/appointment_tools.py`, `api/appointments.py`, `agent/skills/appointment-*`, `integrations/oura.py`, `integrations/whoop.py`, `health/anomaly.py` |
| 3 | Research tools + weekly digest. Nutrition/grocery model + tools + weekly meal-plan job + 6pm nutrition check-in. | `tools/research_tools.py`, `tools/nutrition_tools.py`, `db/models/meal_plan.py`, `db/models/grocery_list.py`, `agent/skills/weekly-health-digest`, `agent/skills/meal-plan-weekly` |
| 4 | Mood + routines wiring. Documents upload + OCR + classifier + expiry reminders. Safety gate binding for first write-risky tool. | `db/models/mood_log.py`, `db/models/document.py`, `tools/mood_tools.py`, `tools/document_tools.py`, `documents/processor.py`, `agent/skills/mood-*`, `safety/bindings.py` |

---

## 16. What we deliberately drop from the original spec

- **Agent Roster as runtime agents.** One ADK agent, period.
- **Custom event bus with typed events.** Replaced by APScheduler jobs and `SystemSignal` rows.
- **WebSocket in-app cards.** Replaced by the existing notifications-polling endpoint for MVP; can be upgraded to SSE on the same FastAPI process later if latency matters.
- **LangGraph alternative.** Not considered; ADK is already the chosen framework.
- **Claude Sonnet as LLM.** We're on Gemini via Vertex (Flash + Flash-Lite). Not negotiable for this service.
- **Celery + Redis task queue.** APScheduler on Postgres is what we have; it's enough for 10k users on a single VM.

These deletions are intentional — the capabilities survive, the architecture they're expressed in changes.
