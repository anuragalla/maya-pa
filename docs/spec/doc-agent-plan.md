# DocAgent — Implementation Plan

**Status.** Approved, implementation starting.

## Goal

Let users upload health PDFs and images (lab results, prescriptions, visit notes, insurance cards, imaging reports). Analyze them with Gemini 3.1 Pro, surface a personalized detailed summary to the main agent, persist the summary into the memory system for future recall, and store the raw file in GCS for re-analysis.

## Constraints

- **No service accounts** — this GCP project disallows creating new SAs. All GCS access flows through ADC (user creds in dev, VM default creds in prod).
- **No signed URLs** — signing V4 URLs requires `iam.signBlob`, which needs an SA. Uploads and downloads proxy through the server.
- The main agent continues running on `gemini-3.1-flash-lite-preview`. Only DocAgent uses Pro.

---

## Architecture

```
[web] ──POST /api/v1/documents (multipart)──▶ [server]
                                                 │ create `document` row (status=pending)
                                                 │ stream bytes → GCS via ADC (no buffer)
                                                 │ flip status=uploaded
                                                 │ enqueue APScheduler process_document(id)
                                                 ◀── { document_id, status: "processing" }

[APScheduler worker] ─invoke─▶ DocAgent (LlmAgent, model=gemini-3.1-pro)
                                  │ input: gs:// URI via Part.from_uri
                                  │ may call get_health_goals / get_holistic_analysis
                                  │ emits structured JSON (Pydantic response_schema)
                                  ▼
                     persist to `document` row
                     + MemoryService.save(kind="document", source_ref=doc_id, content=summary_detailed)

[main agent] — later turns — recalls via search_memory or invokes DocAgent sub-agent ad-hoc
```

---

## GCS

### Bucket setup (one-time, human-run with gcloud CLI)

```bash
for env in dev prod; do
  gcloud storage buckets create "gs://live150-docs-${env}" \
    --project="live150-${env}" --location=us-central1 \
    --uniform-bucket-level-access --public-access-prevention \
    --soft-delete-duration=7d
done
```

No IAM bindings required — ADC on each environment already has bucket access.

### Object layout

```
gs://live150-docs-{env}/users/{user_id}/{document_id}.{ext}
```

### Size + MIME

- Cap: **25 MB**
- Allowed: `application/pdf`, `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `image/heif`

### Wrapper — `server/src/live150/integrations/gcs.py`

Thin functions over `google.cloud.storage.Client()` with ADC:

- `upload(user_id, document_id, file, mime_type) -> gs_uri`
- `open_read(gs_uri) -> BinaryIO` (streams back for previews)
- `delete(gs_uri) -> None`

Dep added: `google-cloud-storage` in `server/requirements.txt`.

---

## Data model — `db/models/document.py`

| Field | Type | Notes |
|---|---|---|
| `document_id` | UUID PK (uuid7) | |
| `user_id` | String | |
| `doc_type` | enum | `lab_result` / `prescription` / `insurance` / `imaging` / `visit_note` / `vaccine` / `other` |
| `status` | enum | `pending` / `uploaded` / `processing` / `ready` / `failed` |
| `error_message` | Text nullable | populated on `failed` |
| `storage_uri` | Text | `gs://...` |
| `original_filename`, `mime_type`, `size_bytes` | | |
| `source` | enum | `app_camera` / `file_upload` / `email_forward` (email deferred) |
| `extracted_text` | Text | full transcription from Pro — kept for future re-analysis |
| `summary_detailed` | Text | ~300-600 words, narrative + findings + trends + flags + goal comparisons |
| `tags` | `text[]` | |
| `structured` | JSONB | e.g. labs → `{markers: [{name, value, unit, range_low, range_high}]}` |
| `expiry_alert_date` | Date nullable | for prescriptions |
| `uploaded_at`, `processed_at` | timestamptz | |

Alembic migration: new revision in `server/migrations/versions/`. Creates enum types + table + indexes on (`user_id`, `uploaded_at DESC`) and (`user_id`, `doc_type`).

---

## Memory integration

Three persisted artifacts per document — single Pro call emits all of them:

| Artifact | Where | Purpose |
|---|---|---|
| `extracted_text` | `document.extracted_text` | raw transcription; future reprocessing |
| `summary_detailed` | `document.summary_detailed` **and** chunked + embedded into `memory_entry` with `kind="document"`, `source="document"`, `source_ref=document_id` | primary recall surface |
| `structured` | `document.structured` JSONB | typed queries from tools (`list_documents(doc_type=lab_result)`) |

Existing `MemoryService.save()` handles chunking (1600 chars) and embedding unchanged. New `kind="document"` lets us filter memory recall to docs when needed.

---

## DocAgent — `agent/doc_agent.py`

Mirrors `search_agent.py` — singleton `LlmAgent`, built once.

```python
LlmAgent(
    name="doc_analyst",
    model="gemini-3.1-pro",
    description=(
        "Analyze a health document (PDF/image): lab results, prescriptions, "
        "visit notes, imaging, insurance, vaccines. Compare to the user's "
        "goals and recent trends. Emit structured JSON with a detailed "
        "summary, extracted markers, tags, and expiry dates."
    ),
    instruction=_DOC_INSTRUCTION,
    tools=[
        FunctionTool(func=get_health_goals),       # personalization
        FunctionTool(func=get_holistic_analysis),  # trend context
    ],
)
```

### Input

The worker passes a user-role `Content` containing:
1. A `Part.from_uri(gs_uri, mime_type=...)` referencing the GCS object.
2. A text part: doc-level hints (filename, user-supplied note if any).

### Output schema (Pydantic, enforced via `response_schema`)

```python
class Marker(BaseModel):
    name: str
    value: float | str
    unit: str | None = None
    range_low: float | None = None
    range_high: float | None = None

class DocAnalysis(BaseModel):
    doc_type: Literal["lab_result", "prescription", "insurance",
                      "imaging", "visit_note", "vaccine", "other"]
    summary_detailed: str           # 300-600 words, narrative
    extracted_text: str             # full transcription
    tags: list[str]
    structured: dict                # {markers: [...]} for labs, {rx: ...} for prescriptions, etc.
    expiry_alert_date: date | None = None
```

### Instruction (abridged)

System prompt tells Pro:
- You analyze a single health document.
- Before writing the summary, call `get_health_goals` and `get_holistic_analysis` so you can compare findings to the user's baselines.
- The `summary_detailed` must be 300–600 words, written for the main coaching agent to recall later. Include: one-line identity (what is this doc), 3–6 key findings, trend comparison to user's prior data, any flags (out-of-range markers, missing data), and concrete next-step-relevant facts (e.g. refill date for prescriptions).
- `extracted_text` is the full transcription, preserving tables where possible.
- If `doc_type=prescription`, compute `expiry_alert_date = fill_date + days_supply - 7`.

Exposed to the main agent via `AgentTool(agent=build_doc_agent())` in `tools/registry.py`, for ad-hoc re-analysis with a custom prompt. Also invoked directly from the APScheduler worker (same singleton, two call sites).

---

## API — `api/documents.py`

All routes under `/api/v1/documents`, user-scoped via existing `X-Phone-Number` → `user_id` middleware.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/` | Multipart upload. Creates row, streams bytes to GCS, enqueues processor, returns `{document_id, status}`. |
| `GET` | `/` | List user's documents. Supports `?doc_type=...&limit=...`. |
| `GET` | `/{id}` | Row details (summary, structured, status). |
| `GET` | `/{id}/content` | Streams raw file from GCS back to client. |
| `DELETE` | `/{id}` | Soft-delete row + hard-delete GCS object. |

Validation on upload: reject MIME not in allow-list, reject size > 25 MB.

---

## Processor — `documents/processor.py`

APScheduler job `process_document(document_id)`:

1. Load row; guard `status in {uploaded, failed}`; flip to `processing`.
2. Build input `Content` with `Part.from_uri(gs_uri, mime_type)` + optional hint text.
3. Invoke DocAgent via ADK runner (synchronous).
4. Validate response against `DocAnalysis` schema.
5. Update document row (`extracted_text`, `summary_detailed`, `structured`, `tags`, `expiry_alert_date`, `doc_type`, `status=ready`, `processed_at=now()`).
6. `MemoryService.save(db, user_id, kind="document", content=summary_detailed, source="document", source_ref=document_id, metadata={"doc_type": ..., "filename": ...})`.
7. If `expiry_alert_date` present → register a one-off APScheduler job that creates a renewal reminder on that date.
8. On any exception → `status=failed`, `error_message=str(exc)`, log telemetry.

---

## Main-agent tools — `tools/document_tools.py`

FunctionTools added to `tools/registry.py`:

- `list_documents(doc_type: str | None = None, limit: int = 10) -> list[dict]`
- `get_document(document_id: str, include_extracted_text: bool = False) -> dict`

Plus the `AgentTool(agent=build_doc_agent())` wrapper for ad-hoc re-analysis.

`REMINDER_SAFE_TOOLS` gains `list_documents` and `get_document` (both read-only).

---

## Rollout

1. Alembic migration + `document` model.
2. `integrations/gcs.py` + `google-cloud-storage` dep.
3. `agent/doc_agent.py` + Pydantic response schema.
4. `documents/processor.py` worker + APScheduler registration.
5. `api/documents.py` + router wired in `main.py`.
6. `tools/document_tools.py` + registry additions.
7. Update `AGENTS.md` / `SOUL.md` instruction so main agent knows when to use the document tools and DocAgent.
8. Run `gcloud storage buckets create` for both envs (human-run).
9. Happy-path test: upload a lab PDF → confirm processing completes → confirm memory recall surfaces it.
10. Update `docs/test/agent-browser-tests.md` with the doc upload + recall flow.

---

## Deferred

- Email ingestion (`docs@live150.ai` inbound) — spec §9.2, deferred to a later phase.
- Virus scanning — deferred.
- CMEK encryption — GCS default encryption for v1.
- Per-marker `HealthMetric` rows — comes with the broader metric store work in Phase 4 of the main feature spec.
- On-demand re-analysis prompts through the AgentTool — background-only processing for now.
