# DocAgent — Frontend Plan (v2, Draft for review)

**Status.** Draft v2 incorporating review notes. Review before implementation.

Backend: `POST /api/v1/documents` (multipart), `GET /api/v1/documents`, `GET /{id}`, `GET /{id}/content`, `DELETE /{id}`. Processing is async — status flows `uploaded → processing → ready | failed`.

This rev folds in: SSE for real-time status, 50/50 pane split, redesigned composer (Claude-style), single attachment per message, no reprocess, no HEIC server convert, `<Button>` everywhere, install full shadcn registry.

---

## 1. UX flows

### Flow A — User attaches and sends one document

```
1. User clicks paperclip in composer (just a shadcn Button + Paperclip lucide icon).
   → File picker opens. accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif". Single file.
   → Single-attach: if a file is already staged, the new file replaces it.

2. File picked.
   → DocAttachmentChip appears above the textarea: [icon · filename · size · ✕].
   → No upload yet. Pure staging.

3. User types optional message + Send.
   → POST /documents (multipart) with progress bar inside the chip.
   → On success: append the user message to chat. Message includes
     documents: [doc_id]. ChatMessageItem detects this and renders a
     DocCard above the text bubble.

4. Realtime status via SSE (replaces polling).
   → Frontend opens EventSource('/api/v1/documents/{id}/events') for the new doc.
   → Backend emits events as the processor moves through stages:
       event: status     data: {"status":"uploaded"}
       event: stage      data: {"stage":"reading","label":"Maya is reading…"}
       event: stage      data: {"stage":"context","label":"Pulling your goals…"}
       event: stage      data: {"stage":"summarizing","label":"Summarizing…"}
       event: ready      data: { full doc summary payload }
       event: failed     data: {"error":"..."}
   → DocCard renders the most recent stage label in the caption row.
   → On 'ready' or 'failed', the EventSource closes itself.

5. User clicks the DocCard → DocPreviewPane slides in (50/50 split).
```

### Flow B — Drag and drop

Drop a file anywhere on the chat surface → highlights a dropzone overlay → on drop, behaves identically to step 2 (replaces any existing staged file).

### Flow C — Recall via agent tools

When the agent calls `list_documents` / `get_document`, results render as the existing tool pill. Each row gets a clickable inline `DocCard` (compact variant) that opens the same right pane.

### Flow D — Right pane (Claude-style, 50/50 desktop)

```
┌──────────────────────────┬──────────────────────────┐
│                          │  ◀ filename.pdf    ⋯  ✕  │
│      Chat (50%)          │  Lab result · 2 days ago │
│                          │  ─────────────────────── │
│                          │  [ Preview ] [ Summary ] │
│                          │                          │
│                          │  (tab content)           │
│                          │                          │
└──────────────────────────┴──────────────────────────┘
```

- Desktop (≥1024px): true 50/50 flex split. Chat reflows automatically (already a centered column).
- Mobile (<1024px): full-screen `Sheet`.
- Header: ← close, doc title, subtitle (`<doc_type> · <relative time>`), `DropdownMenu` with Download + Delete, `✕` close.
- Tabs (shadcn `Tabs`):
  - **Preview** — `react-pdf` for PDFs (single-page paginate, `‹` `›`, zoom `+`/`−`, indicator). For images, a centered `<img>` with object-contain. HEIC: lazy-load `heic2any` only when a HEIC doc opens.
  - **Summary** — `streamdown`-rendered `summary_detailed` + tag chips + structured (markers table for labs, refill block for prescriptions) + collapsible raw `extracted_text`.
- URL-synced via TanStack Router: `?doc=<id>&tab=preview|summary`. Browser back closes.

### Flow E — Loading & error states

| Stage | Visual | Source |
|---|---|---|
| Composer chip, before send | Static chip. | local |
| Upload in flight | Linear `Progress` inside chip + percent. ✕ aborts. | fetch onUploadProgress |
| Upload failed | Chip turns destructive-tinted. Inline Retry. Tooltip with reason. | local |
| DocCard, processing | Caption row reads the latest SSE label. Sparkles icon + Skeleton over title. | SSE |
| DocCard, stage = reading | "Maya is reading…" | SSE |
| DocCard, stage = context | "Pulling your goals…" | SSE |
| DocCard, stage = summarizing | "Summarizing…" | SSE |
| DocCard, ready | Mime icon + filename + 2-3 tag chips + doc_type Badge. | SSE → query refetch |
| DocCard, failed | Destructive Badge + caption with error. | SSE |
| Pane opening | 220ms slide-in spring. Skeleton tabs while blob loads. | local |
| Preview blob loading | Skeleton page outline. | TanStack Query |
| Summary loading (status≠ready) | Skeleton lines, swap when SSE flips to ready. | SSE |

---

## 2. Composer redesign

Reference: Claude's composer (single rounded card, two-row layout, paperclip bottom-left, model + mic bottom-right, soft shadow).

Design spec:
- Container: rounded-2xl card, `bg-background`, subtle 1px border + soft shadow (`shadow-sm` ramping to `shadow-md` on focus).
- Row 1: textarea (no border, transparent bg, placeholder "Reply…"). Auto-resizes 1-8 rows.
- Row 2: left = paperclip Button (ghost, icon-size); right = future model selector + future mic + Send Button (primary, icon-size, sends on click). Equal vertical padding to Row 1.
- Composer chip (`DocAttachmentChip`) renders *above* Row 1, inside the same rounded card, pushing the textarea down when present.
- When DocAttachmentChip is present and showing upload progress, the Send Button is disabled with a Spinner.

Implementation: keep the existing `prompt-input.tsx` attachments context (it works), wrap it in a new `chat-composer.tsx` that owns the visual chrome. `prompt-input.tsx` itself isn't modified — just composed differently.

---

## 3. SSE pipeline

### Backend

New endpoint: `GET /api/v1/documents/{id}/events` (SSE via `sse-starlette`, already in deps).

Cross-process coordination (API container holds the SSE conn, scheduler container runs the processor): **Postgres `LISTEN/NOTIFY`** on channel `doc:{document_id}`. No new infra deps.

Flow:
- API endpoint subscribes via async pg connection: `LISTEN doc:{id}`.
- Processor calls a new helper `publish_doc_event(document_id, stage, label, payload?)` that does `NOTIFY doc:{id}, '<json>'`.
- API yields each notification as an SSE event, plus an initial `status` event with current row state, and closes on ready/failed.
- Heartbeat every 15s to keep proxies happy.

Processor instrumentation hooks (added to `documents/processor.py`):
- After flipping to processing → `publish('reading', 'Maya is reading…')`
- On first ADK tool_call event → `publish('context', 'Pulling your goals…')`
- After tools resolve, before final text → `publish('summarizing', 'Summarizing…')`
- On ready → `publish('ready', '', payload=full_doc_dict)`
- On failed → `publish('failed', '', payload={'error': msg})`

Stage labels are **server-authoritative** so we can iterate copy without a deploy. Frontend just renders `event.data.label`.

### Frontend

`useDocStream(documentId)` hook:
- Opens `EventSource('/api/v1/documents/{id}/events')`.
- Returns `{stage, label, status, payload}` with React state.
- Closes on `ready` / `failed` / unmount.
- Falls back to a one-shot `GET /documents/{id}` on EventSource error so the card doesn't get stuck.

---

## 4. Component split (lean)

11 → 6 components. Inline shadcn primitives wherever there's no custom logic.

```
web/src/
  components/
    chat-composer.tsx              # new wrapper around PromptInput with redesigned chrome
    documents/
      doc-attachment-chip.tsx      # composer chip: progress, ✕, retry
      doc-card.tsx                 # in-message card; includes status badge + caption inline
      doc-preview-pane.tsx         # right pane: header + Tabs + close, all in one file
      doc-pdf-viewer.tsx           # react-pdf wrapper (paginate, zoom, skeleton)
      doc-image-viewer.tsx         # img + lazy heic2any
      doc-summary.tsx              # streamdown summary + structured + extracted_text disclosure
  hooks/
    use-doc-upload.ts              # POST /documents w/ progress; abortable
    use-doc-stream.ts              # EventSource hook (replaces polling)
    use-doc-blob.ts                # GET /{id}/content as blob URL; revoke on unmount
    use-doc-pane.ts                # URL-synced pane state
  lib/
    documents.ts                   # MIME→ext map, ALLOWED_MIME, MAX_SIZE, mimeIcon()
```

What got *removed* vs v1:
- ❌ `doc-attach-button.tsx` → just `<Button variant="ghost" size="icon" onClick={openPicker}><Paperclip /></Button>` inline.
- ❌ `doc-preview-tab.tsx` → small switch inside `doc-preview-pane.tsx`.
- ❌ `doc-status-badge.tsx` → `<Badge variant={statusVariant(status)}>{status}</Badge>` inline in DocCard.
- ❌ `doc-mime-icon.tsx` → `mimeIcon(mime)` function in `lib/documents.ts` returning a lucide component.

---

## 5. shadcn — install everything + migrate raw buttons

### Install all components

```bash
cd web && bunx shadcn@latest add --all
```

This pulls in everything we don't have (`sheet`, `tabs`, `progress`, `skeleton`, `card`, `sonner`, `popover`, etc) and updates existing ones. We commit the lot.

### Migrate existing raw `<button>` to shadcn `<Button>`

Audit (from grep):

| File | Line | Current | Replacement |
|---|---|---|---|
| `chat-view.tsx` | 148 | `<button onClick={reload}>Retry</button>` | `<Button variant="link" size="sm" onClick={reload}>Retry</Button>` |
| `header.tsx` | 36 | raw button | shadcn `<Button>` (variant per visual) |
| `thinking-block.tsx` | 31, 86 | raw buttons | shadcn `<Button variant="ghost" size="sm">` |
| `themes.tsx` | 554, 564, 581, 605 | raw buttons | shadcn `<Button>` per visual |
| `login.tsx` | 76 | raw button | shadcn `<Button>` |
| `oauth.success.tsx` | 34 | raw button | shadcn `<Button>` |

Done as part of this work, separate small commits per file so the diffs are reviewable.

### Hard rule

Going forward: **no raw `<button>` in the codebase.** Add a lint rule via eslint `react/forbid-elements` (configured in a separate small step).

---

## 6. State management

- **Pane state** in URL search params via TanStack Router (`?doc=<id>&tab=summary`). `useDocPane` exposes `{open, doc, tab, openDoc, close, setTab}`. Single source of truth.
- **Document fetches** via TanStack Query.
  - `useDocument(id)` → `GET /documents/{id}` — for the pane header + summary content.
  - `useDocumentBlob(id)` → `GET /{id}/content` — 5min cache, blob URL revoked on cleanup.
- **Status** via `useDocStream(id)` (SSE). On `ready` it invalidates the `useDocument(id)` query so the card and pane both refresh.
- **Composer attachment** stays in `prompt-input`'s existing attachments context (single-file).

---

## 7. Backend follow-ups (small)

1. **`GET /api/v1/documents/{id}/events`** SSE endpoint (sse-starlette + pg LISTEN/NOTIFY).
2. **`publish_doc_event()` helper** in `documents/processor.py` + four call sites (reading, context, summarizing, ready/failed).
3. **`documents` field on `/stream/chat` body schema.** When present, server prepends a system note in the user's turn: `"User attached document <filename> (id=<id>, status=<status>). Use get_document(id) to inspect."` Without this the agent gets a vague string and may hallucinate.
4. **Carry attachments through `/stream/history`.** Extend the per-message payload with `documents: [{document_id, original_filename, doc_type, status}]` so cards survive reload. Read from `chat_message.content` if we serialize `documents` into it on send, or join against `document` rows by message_id (preferred — clean schema).
5. **Reprocess endpoint** — *out of scope per review*.

---

## 8. New deps

shadcn (full registry installed via `add --all`).

```bash
cd web && bun add react-pdf pdfjs-dist
```

`react-pdf` worker via Vite `?url` import — no public asset.
HEIC: no client-side decode. Native `<img>` (Safari handles), Download fallback on error.

---

## 9. Visual / design notes

- **Composer:** matches the reference screenshot — rounded-2xl single card, soft shadow, two-row layout, paperclip bottom-left, Send (and future model/mic) bottom-right. Placeholder "Reply…".
- **Pane chrome:** 1px left border, no shadow, soft `bg-card`. Header 56px to match composer rhythm.
- **Tabs:** underline (not pill). 200ms ease underline slide. Body fades 120ms on switch.
- **DocCard:**
  - *Processing* — `bg-muted/40` + Skeleton over title + Sparkles icon + caption row tied to SSE label. `aria-live="polite"`.
  - *Ready* — `bg-card` + solid border + mime icon + filename + tag chips + doc_type Badge right-aligned.
  - *Failed* — destructive border + Badge + caption with error text.
  - Compact variant (used inside agent tool-result pills): single row, 32px tall, no caption.
- **PDF viewer:** single-page paginate, indicator `1 / 7` bottom-center, zoom + reset on double-click.
- **Motion:** pane slide 220ms `[0.32, 0.72, 0, 1]` (matches existing `AnimatePresence` rhythm).

---

## 10. Accessibility

- Paperclip Button has `aria-label="Attach document"`.
- DocCard is a `<Button variant="ghost">` (not raw `<button>`) with `aria-haspopup="dialog"` + `aria-expanded`.
- Pane is `<aside role="complementary">`, focus trap on mobile sheet, no trap on desktop split. Esc closes.
- shadcn `Tabs` (Radix) gives keyboard nav free.
- Status updates announced via `aria-live="polite"` inside DocCard.

---

## 11. Rollout order

1. **Setup**
   - `bunx shadcn@latest add --all`
   - `bun add react-pdf pdfjs-dist heic2any`
   - eslint `react/forbid-elements: ['error', { forbid: ['button'] }]`
2. **Button migration** — sweep the 10 raw `<button>` sites to shadcn `<Button>` (small commits per file).
3. **Backend SSE** — pg LISTEN/NOTIFY helper + `/documents/{id}/events` endpoint + processor instrumentation.
4. **Backend extras** — `documents` field on `/stream/chat`, `/stream/history` joins.
5. **Frontend lib + hooks** — `lib/documents.ts`, `useDocUpload`, `useDocStream`, `useDocBlob`, `useDocPane`.
6. **Composer redesign** — new `chat-composer.tsx`, paperclip wired, attachment chip rendered inside.
7. **In-message card** — `doc-card.tsx` + integration into `chat-message-item.tsx`.
8. **Right pane** — `doc-preview-pane.tsx` orchestrator + `doc-pdf-viewer.tsx` + `doc-image-viewer.tsx` + `doc-summary.tsx`.
9. **Drag-and-drop overlay.**
10. **`docs/test/agent-browser-tests.md`** — happy path: upload → SSE stages stream → ready → open pane → summary visible → reload page → card persists.

Each step shippable on its own.

---

## 12. Decisions (locked)

1. **HEIC preview** — no `heic2any`, no server convert. Safari renders HEIC natively (handles iOS users — the dominant case). Chrome/Firefox/Edge get a Download button when `<img>` errors out. Saves ~600 KB chunk.
2. **`chat_message_id` FK on `document`** (nullable). Set at insert time when an upload accompanies a chat message. `/stream/history` joins on this to rehydrate doc cards on page reload.
3. **Cancel during processing** — DELETE while status=`processing` flips status to `cancelled`. Processor checks status before persisting; if cancelled, it skips the write and exits cleanly (the in-flight Gemini call still completes — that's fine, we just throw the result away).
4. **Send while processing** — allowed. Agent can answer unrelated questions; `get_document` exposes in-flight status if the user references the doc.

---

## 13. Out of scope (defer)

- Multi-attach per message.
- Reprocess on failure (manual re-upload only).
- Sidebar with all docs.
- Email-ingest UI.
- Sharing / annotations / cross-doc compare.
- Renaming / re-tagging from the pane.
