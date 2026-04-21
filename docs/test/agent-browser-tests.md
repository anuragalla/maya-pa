# Live150 Chat UI — Agent Browser E2E Test Plan

**Target URL:** http://localhost:3000
**Backend:** http://localhost:8000

## Test Users

| User | Phone | Profile | Tier | Key Scenarios |
|---|---|---|---|---|
| Nigel | +19084329987 | Prediabetes, weight loss, 41yo | Paid | Full data, meal plan, glucose pillar |
| Murthy | +19083612019 | Type 2 diabetes, 52yo | Free | Sparse data, no meal plan (upgrade prompt) |
| Pragya | +12243347204 | General wellness, 34yo | Paid | No meal plan generated yet, good sleep |

---

## Suite 1: Page Load & Empty State

### T1.1 — Initial load
1. Navigate to http://localhost:3000
2. **Verify:** Page loads (dark or light theme depending on system preference)
3. **Verify:** Header shows "L" badge + "Live150" text (no leaf icon)
4. **Verify:** Header contains a theme toggle button (sun/moon icon)
5. **Verify:** User selector in header shows the user's name only (e.g., "Nigel")
6. **Verify:** Empty state shows time-based greeting: "Good morning, Nigel" / "Good afternoon, Nigel" / "Good evening, Nigel" / "Up late, Nigel?" / "Winding down, Nigel?" — matches current time
7. **Verify:** Empty state subtitle is "What would you like to know?"
8. **Verify:** No static suggestion buttons in the empty state
9. **Verify:** Composer is a single rounded-2xl card with a soft shadow that deepens on focus
10. **Verify:** Textarea placeholder reads "Reply…" (not "Ask anything")
11. **Verify:** Bottom-left of the composer shows a paperclip icon Button (ghost variant, lucide Paperclip)
12. **Verify:** Bottom-right of the composer shows the Send Button
13. **Verify:** Send button is disabled (no input and no attachment)

### T1.2 — Theme toggle
1. Click the sun/moon icon in the header
2. **Verify:** Theme switches between light and dark
3. Click again
4. **Verify:** Theme reverts

### T1.3 — History restore on load
1. Send a message as Nigel, wait for response
2. Reload the page
3. **Verify:** Previous conversation messages are visible on reload (loaded from `/api/v1/stream/history`)
4. **Verify:** Empty state is NOT shown if history exists
5. **Verify:** Any previously attached documents render as DocCards above their user message (via `chat_message_id` join)

---

## Suite 2: User Switching

### T2.1 — Switch to Murthy
1. Click the user selector dropdown in the header
2. Select "Murthy"
3. **Verify:** Empty state greeting changes to the time-appropriate greeting for Murthy (e.g., "Good evening, Murthy")
4. **Verify:** Any previous messages are cleared (new history loaded for Murthy)
5. **Verify:** Input clears

### T2.2 — Switch to Pragya
1. Click the user selector dropdown
2. Select "Pragya"
3. **Verify:** Empty state greeting changes to time-appropriate greeting for Pragya

### T2.3 — Switch back to Nigel
1. Switch back to Nigel
2. **Verify:** Greeting shows time-appropriate greeting for Nigel
3. **Verify:** Nigel's conversation history loads (not Pragya's)

---

## Suite 3: Chat — Basic Message Flow (Nigel)

### T3.1 — Send a simple greeting
1. Select Nigel
2. Type "hi" in the input
3. Click send button (or press Enter)
4. **Verify:** User message appears in the message list
5. **Verify:** Thinking block appears with pulsing state while agent is working
6. **Verify:** Agent response streams in left-aligned
7. **Verify:** Response is personalized (mentions Nigel or health context)
8. **Verify:** No "Great question!" or filler (SOUL compliance)
9. **Verify:** After response completes, 4 suggestion pills appear above the input field
10. **Verify:** Input field is re-enabled after response completes

### T3.2 — Send via Enter key
1. Type "what time is it?" in the input
2. Press Enter
3. **Verify:** Message sends without clicking the button

### T3.3 — Empty input blocked
1. Clear the input field
2. **Verify:** Send button is disabled
3. Try pressing Enter with empty input
4. **Verify:** Nothing happens

### T3.4 — Copy button on assistant messages
1. After receiving an agent response, hover over the message
2. **Verify:** Copy icon appears in message actions area
3. Click the copy icon
4. **Verify:** Icon briefly changes to a green checkmark
5. **Verify:** Response text is copied to clipboard

---

## Suite 4: Dynamic Suggestions

### T4.1 — Suggestions appear after response
1. Select Nigel, send any message
2. Wait for response to complete
3. **Verify:** 4 suggestion pills appear above the input field
4. **Verify:** Pills are not visible while streaming is in progress
5. **Verify:** Pills are contextually relevant to the response (not generic)

### T4.2 — Clicking a suggestion sends it
1. After suggestions appear, click any suggestion pill
2. **Verify:** The suggestion text appears as a user message
3. **Verify:** Agent responds to it
4. **Verify:** New suggestions appear after the follow-up response

### T4.3 — Suggestions update after each turn
1. Send a message about nutrition, note the 4 suggestions
2. Send another message about sleep
3. **Verify:** Suggestions update to reflect the new response context

### T4.4 — Suggestion pill 4 is a discovery question
1. After any response, look at the 4th suggestion pill
2. **Verify:** The 4th pill reads like a discovery question ("Show my bio age trend", "What's my weakest pillar this week") — an adjacent health thread, not a follow-up to what was just said

---

## Suite 5: Tool Call Display

### T5.1 — Tool call pill renders
1. Send "How did I sleep?" (triggers a tool)
2. **Verify:** Tool call pill appears in the thinking block with icon + label (e.g., "Holistic Analysis", "Daily Progress", "Memory Search")
3. **Verify:** Spinner shows while tool is running
4. **Verify:** Thinking block shows "Done" or similar when tools complete

### T5.2 — All tool labels map correctly

The following tool names should display with these labels:

| Tool | Label |
|---|---|
| `get_holistic_analysis` | Holistic Analysis |
| `get_progress_by_date` | Daily Progress |
| `get_health_goals` | Health Goals |
| `get_meal_plan` | Meal Plan |
| `get_initial_context` | User Context |
| `search_memory` | Memory Search |
| `save_memory` | Save Memory |
| `log_nams` | *(check UI label if displayed)* |
| `create_reminder` | Create Reminder |
| `list_reminders` | List Reminders |
| `cancel_reminder` | Cancel Reminder |
| `skill_search` | Skill Search |
| `skill_load` | Load Skill |
| `get_calendar_schedule` | Calendar Schedule |
| `create_live150_event` | Create Event |
| `delete_live150_event` | Delete Event |
| `find_free_slots` | Find Free Slots |
| `check_calendar_connection` | Calendar Status |
| `list_available_integrations` | Integrations |
| `request_integration_connect` | Connect Integration |
| `list_documents` | List Documents |
| `get_document` | Get Document |
| `doc_analyst` | Analyze Document |

### T5.3 — Tool call expandable
1. Click on a completed tool call pill in the thinking block
2. **Verify:** Expands to show Args and Result
3. **Verify:** Result shows JSON data from the API
4. Click again
5. **Verify:** Collapses back

---

## Suite 6: NAMS Auto-Logging

### T6.1 — Activity logging
1. Select Nigel
2. Send "I just ran 5k this morning"
3. **Verify:** Agent calls `log_nams` tool (visible in thinking block) immediately
4. **Verify:** Response acknowledges the log (e.g., "Logged your 5k run.") briefly before continuing
5. **Verify:** Agent continues with coaching after logging

### T6.2 — Nutrition logging
1. Send "just had lunch, ate some rice and dal"
2. **Verify:** Agent calls `log_nams` with category nutrition
3. **Verify:** Response briefly acknowledges the log then continues

### T6.3 — Sleep logging
1. Send "I slept for 7 hours last night"
2. **Verify:** Agent calls `log_nams` with category sleep
3. **Verify:** Agent continues with relevant sleep context

### T6.4 — No log on non-NAMS messages
1. Send "What are my health goals?"
2. **Verify:** Agent does NOT call `log_nams` (no food/activity/sleep/mindfulness event)
3. **Verify:** Agent calls `get_health_goals` instead

---

## Suite 7: Memory Tools

### T7.1 — Memory search on historical reference
1. Select Nigel
2. Send "what did we discuss last time about my sleep?"
3. **Verify:** Agent calls `search_memory` before responding (checks for historical context)
4. **Verify:** Response references past conversation if memory exists, or gracefully acknowledges if empty

### T7.2 — Fact saved to memory
1. Send "I don't eat pork"
2. **Verify:** Agent calls `save_memory` with the dietary fact
3. **Verify:** Response acknowledges the preference has been noted

### T7.3 — Summary recall
1. Send "How did I do this week overall?"
2. **Verify:** Agent calls `search_memory` with a query like "weekly summary" before falling back to API tools
3. **Verify:** If a weekly summary is stored, response uses it

---

## Suite 8: Calendar Integration

### T8.1 — Calendar connect offer (not connected)
1. Select Nigel
2. Send "Put tomorrow's workout on my calendar"
3. **Verify:** Agent calls `check_calendar_connection` or `list_available_integrations`
4. **Verify:** If calendar not connected, agent calls `request_integration_connect` and includes a connect link in the response
5. **Verify:** Connect link is a real URL from the tool (not fabricated)
6. **Verify:** Agent does NOT claim the event was created before connection confirmed

### T8.2 — Calendar tools in tool display
1. If calendar is connected, ask "What does my week look like?"
2. **Verify:** Agent calls `get_calendar_schedule`
3. **Verify:** "Calendar Schedule" label appears in tool pill

### T8.3 — No connect offer in proactive contexts
1. If a reminder fires or a morning brief is generated
2. **Verify:** Agent does NOT offer to connect calendar mid-briefing (only offers when user explicitly requests scheduling)

---

## Suite 9: Murthy-Specific (Free Tier)

### T9.1 — Meal plan for free user
1. Switch to Murthy
2. Ask "What's my meal plan for today?"
3. **Verify:** Agent calls `get_meal_plan` tool
4. **Verify:** Response acknowledges free tier — mentions upgrade or premium
5. **Verify:** Agent doesn't fabricate a meal plan

### T9.2 — Health goals (sparse)
1. Ask "What are my health goals?"
2. **Verify:** Agent calls `get_health_goals` tool
3. **Verify:** Response handles sparse data gracefully (Murthy has minimal goals)
4. **Verify:** Mentions diabetes management

### T9.3 — Diabetes-specific advice
1. Ask "What should I eat for dinner tonight?"
2. **Verify:** Response is personalized for type 2 diabetes
3. **Verify:** Mentions blood glucose / carb management
4. **Verify:** Does NOT give medical advice or prescribe medications

---

## Suite 10: Pragya-Specific

### T10.1 — Meal plan not generated
1. Switch to Pragya
2. Ask "Show me today's meal plan"
3. **Verify:** Agent calls `get_meal_plan` tool
4. **Verify:** Response acknowledges no plan generated yet
5. **Verify:** Doesn't fabricate a plan

### T10.2 — General wellness
1. Ask "How am I doing overall?"
2. **Verify:** Agent fetches relevant data (holistic analysis or progress)
3. **Verify:** Response is encouraging but specific (not generic)

---

## Suite 11: Multi-Turn Conversation

### T11.1 — Follow-up questions
1. Select Nigel
2. Ask "How did I sleep?"
3. Wait for response
4. Ask "Why might that be?"
5. **Verify:** Agent references the previous answer (conversation context works)
6. **Verify:** Agent may call additional tools or reason from existing context

### T11.2 — Cross-pillar reasoning
1. Ask "My energy has been low this week. What's going on?"
2. **Verify:** Agent calls multiple tools (sleep + activity + nutrition likely)
3. **Verify:** Response connects pillars (e.g., sleep affecting energy, or nutrition)

---

## Suite 12: Notifications & Reminders

### T12.1 — Notification banner appears
1. If a scheduled reminder fires while the app is open
2. **Verify:** A notification banner slides in near the top of the chat area
3. **Verify:** Banner shows reminder title and body
4. **Verify:** Reminder message is also injected into the message list

### T12.2 — Dismiss notification
1. With a notification banner visible, click the dismiss control
2. **Verify:** Banner animates out and disappears
3. **Verify:** The injected message remains in the conversation

### T12.3 — Notifications arrive via SSE (no polling)
1. Open devtools → Network tab, filter `notifications`
2. **Verify:** One short-lived `GET /api/v1/notifications/catchup` on mount (backlog)
3. **Verify:** One long-lived `GET /api/v1/notifications/events` (SSE — stays open)
4. **Verify:** No recurring polling every 5 seconds against `/api/v1/notifications` — the old endpoint is gone
5. Trigger a reminder via `create_reminder` with a 1-minute schedule
6. **Verify:** When the reminder fires, the SSE stream delivers a `notification` event and the banner appears without a page refresh

---

## Suite 13: Error Handling

### T13.1 — Streaming error recovery
1. If an error occurs during streaming:
2. **Verify:** Error message appears: "Something went wrong."
3. **Verify:** Retry link is visible
4. Click Retry
5. **Verify:** Agent retries the last message

---

## Suite 14: Responsive & Accessibility

### T14.1 — Keyboard navigation
1. Tab through the page
2. **Verify:** Focus ring visible on interactive elements
3. **Verify:** Can tab to input, type, and press Enter to send
4. **Verify:** Theme toggle button is keyboard accessible

### T14.2 — Screen reader attributes
1. Inspect the message area
2. **Verify:** `role="log"` and `aria-live="polite"` on message container (or equivalent)
3. **Verify:** Send button has `aria-label="Send message"` (or similar accessible label)
4. **Verify:** User selector has `aria-label="Select user"`

---

## Suite 15: SOUL Compliance

### T15.1 — No filler language
1. Send several messages across all users
2. **Verify:** No "Great question!", "I'd be happy to help!", "Let me know if you have any other questions!"
3. **Verify:** Responses end on the action/recommendation, not on filler
4. **Verify:** No emoji in any response

### T15.2 — No medical advice
1. Ask Nigel: "Should I change my metformin dose?"
2. **Verify:** Agent declines and recommends consulting a doctor
3. **Verify:** Does NOT give medication dosage advice

### T15.3 — Specific, not generic
1. Ask "What should I eat?"
2. **Verify:** Response references the user's actual goals, restrictions, plan
3. **Verify:** NOT a generic "eat more vegetables" response

### T15.4 — Suggestions not generic
1. After any response, verify the 4 suggestion pills are:
   - Pill 1: natural follow-up from the specific response
   - Pill 2: different angle on the same topic
   - Pill 3: a concrete action ("Set my 10pm wind-down reminder", not "Do something healthy")
   - Pill 4: a discovery question about adjacent health data

### T15.5 — No suggestions in reminder turns
1. If a reminder fires and its message is shown in the UI
2. **Verify:** No suggestion pills appear below the reminder message

---

## Suite 16: Document Upload — Composer

### T16.1 — Paperclip opens the file picker
1. Click the paperclip Button in the composer
2. **Verify:** Native file picker opens
3. **Verify:** Picker is filtered to: `.pdf, .jpg, .jpeg, .png, .webp, .heic, .heif`

### T16.2 — Staged attachment chip renders
1. Pick a ≤25 MB PDF
2. **Verify:** A DocAttachmentChip appears ABOVE the textarea, inside the same rounded card
3. **Verify:** Chip shows the mime icon, filename (truncated if long), formatted size (`X.X MB`)
4. **Verify:** Chip has an `✕` remove Button on the right
5. **Verify:** Send Button is now enabled (because an attachment is staged)
6. **Verify:** No upload has happened yet — this is pure staging (no network request to `/api/v1/documents`)

### T16.3 — ✕ removes the staged attachment
1. With a chip staged, click the `✕`
2. **Verify:** Chip disappears
3. **Verify:** Send Button is disabled again (no text, no attachment)

### T16.4 — Single-attach replaces prior stage
1. Stage a PDF
2. Click paperclip again, pick a different file (PNG)
3. **Verify:** Chip updates to the new file — the PDF is replaced, not added

### T16.5 — Size cap enforcement (client-side)
1. Try to pick a >25 MB file
2. **Verify:** File is rejected; no chip appears (console warn `[composer] rejected size: …`)

### T16.6 — MIME cap enforcement
1. Try to pick a `.docx` or `.txt` (rename an arbitrary file to force it)
2. **Verify:** File is rejected (console warn `[composer] rejected mime: …`)

---

## Suite 17: Document Upload — Send + Live Status

### T17.1 — Upload happens on send
1. Stage a small PDF lab result
2. Type "summarize this" in the textarea
3. Click Send
4. **Verify:** Network: `POST /api/v1/documents` fires once (multipart/form-data)
5. **Verify:** Response is `{document_id, status}` with status `"processing"` or `"uploaded"`
6. **Verify:** User message bubble appears with a DocCard ABOVE the text
7. **Verify:** Composer clears (text + staged file gone)

### T17.2 — DocCard shows live SSE stages
1. Immediately after send, inspect the DocCard
2. **Verify:** Network: `GET /api/v1/documents/{id}/events` opens (EventSource-style, long-lived, `Content-Type: text/event-stream`)
3. **Verify:** Card shows a Sparkles icon + shimmer over the title area
4. **Verify:** Caption row text cycles through the stages as SSE events arrive:
   - `reading` → "Maya is reading…"
   - `context` → "Pulling your goals…"
   - `summarizing` → "Summarizing…"
5. **Verify:** Caption row has `aria-live="polite"`
6. **Verify:** On `ready`, SSE stream closes; the card snaps to its final shape:
   - Mime icon + filename
   - 2-3 tag chips (shadcn `Badge variant="secondary"`)
   - Doc type Badge right-aligned (e.g. "lab_result")

### T17.3 — Failure state
1. Force a failure (e.g., upload a corrupt PDF or disable Vertex AI temporarily)
2. **Verify:** DocCard transitions to a destructive visual: red border, "Couldn't process this document." caption
3. **Verify:** Processor logs the failure in the scheduler container logs

### T17.4 — Upload error toast
1. Upload while backend is down (stop agent container, try to send)
2. **Verify:** Sonner toast appears at top-center: "Upload failed for …"
3. **Verify:** No DocCard is added to the chat (request aborted before optimistic inject)

### T17.5 — Agent reads the attached document
1. Attach a lab PDF, message "walk me through this"
2. **Verify:** Agent's thinking block includes a `get_document` tool call (new pill "Get Document")
3. **Verify:** Response references specific markers / values from the PDF (proves the server injected the `[Attached documents: …]` framing and DocAgent produced structured output)

---

## Suite 18: Document Preview Pane (Right Side)

### T18.1 — Click card opens the pane
1. With a DocCard in status `ready`, click it
2. **Verify:** URL gains `?doc=<id>&tab=summary` search params
3. **Verify:** Right pane slides in from the right with a 220ms spring motion
4. **Verify:** On desktop (≥1024px), the chat column reflows to the left half and the pane occupies the right half (50/50)
5. **Verify:** On mobile (<1024px), the pane is full-screen (chat is hidden)
6. **Verify:** Pane header shows:
   - Close `←` Button (ghost icon)
   - Truncated filename
   - Subtitle: `<doc_type> · <relative time>` (e.g. "lab_result · 2 minutes ago")
   - `⋯` DropdownMenu trigger
   - `✕` close Button

### T18.2 — Tabs work
1. Pane open, default tab is `Summary` (per the `openDoc(id, 'summary')` in DocCard)
2. **Verify:** Underline tabs (not pill tabs), active tab has a bottom underline
3. Click the `Preview` tab
4. **Verify:** URL search updates to `?doc=<id>&tab=preview`
5. **Verify:** Tab content cross-fades on switch

### T18.3 — Close via ✕ and ← buttons
1. Click `✕`
2. **Verify:** Pane animates out; URL search params `doc` and `tab` are cleared
3. **Verify:** Chat column reflows back to full width

### T18.4 — Close via browser back
1. Open pane, then press browser back button
2. **Verify:** Pane closes; chat column restored

### T18.5 — Close via Escape
1. Pane open, press `Escape` (focus anywhere inside pane)
2. **Verify:** Pane closes

### T18.6 — Deep-link via URL
1. Copy a pane URL (e.g. `http://localhost:3000/?doc=<real-id>&tab=summary`)
2. Paste into a new tab (still logged in as same phone)
3. **Verify:** App loads with the pane already open on that document

---

## Suite 19: Preview Tab

### T19.1 — PDF viewer renders
1. Open a PDF document in the pane, select Preview tab
2. **Verify:** `react-pdf` renders page 1 centered on `bg-muted/20`
3. **Verify:** Footer toolbar shows: `‹` page-prev, `1 / N`, `›` page-next, `−`, `100%`, `+`
4. **Verify:** Skeleton shows briefly while the blob loads (via `GET /api/v1/documents/{id}/content`)
5. Click `›` → page advances; `1 / N` updates
6. At page 1: `‹` is disabled. At last page: `›` is disabled.
7. Click `+` to zoom to 110%, 120%, 130%…
8. **Verify:** Zoom caps at 250% (`+` disables / clamps)
9. Click `−` to reduce below 100%
10. **Verify:** Zoom floor is 50%
11. Double-click the page area
12. **Verify:** Zoom resets to 100%

### T19.2 — Image viewer renders (JPG/PNG/WEBP)
1. Upload a JPG and open its Preview
2. **Verify:** Centered `<img>` with `object-contain` on `bg-muted/20`
3. **Verify:** No PDF toolbar (not a PDF)

### T19.3 — HEIC on Safari vs Chromium
1. Upload a HEIC image
2. **On Safari:** Image renders natively
3. **On Chrome/Firefox:** `<img>` `onError` fires → viewer falls back to a download panel with a Download Button

### T19.4 — Download from `⋯` menu
1. Open any document's pane, click the `⋯` header menu
2. Click "Download"
3. **Verify:** Browser downloads the original file with its `original_filename`

### T19.5 — Delete from `⋯` menu
1. Open any document's pane, click `⋯` → "Delete"
2. **Verify:** An `AlertDialog` asks for confirmation
3. Click Confirm
4. **Verify:** Network: `DELETE /api/v1/documents/{id}` fires
5. **Verify:** Pane closes
6. **Verify:** The DocCard in chat disappears (or shows cancelled/deleted) — exact behavior depends on how TanStack Query refreshes; at minimum the pane data goes stale and can't be re-opened

---

## Suite 20: Summary Tab

### T20.1 — Summary while processing
1. Open the pane while the doc is still in `processing`
2. **Verify:** Summary tab shows a status banner ("Still processing — summary will appear here.")
3. **Verify:** Skeleton lines where the markdown will land
4. **Verify:** When SSE transitions to `ready`, the tab auto-refreshes to show real content

### T20.2 — Detailed summary (markdown)
1. Open a `ready` doc, Summary tab
2. **Verify:** `summary_detailed` renders via `streamdown` — markdown formatted (bold, lists, tables where emitted)
3. **Verify:** Summary is 300–600 words, personalized (references the user's goals / recent trends when applicable)

### T20.3 — Tag chips
1. Summary tab with a `lab_result` doc
2. **Verify:** Below the summary, 2-5 `Badge` chips show tags (e.g. `lipid-panel`, `cholesterol`, `ldl-elevated`)

### T20.4 — Structured — lab result
1. With a lab doc, scroll below the tag chips
2. **Verify:** A shadcn `Table` renders the markers: columns for Name, Value, Unit, Range
3. **Verify:** Row count matches the extracted markers

### T20.5 — Structured — prescription
1. Upload a prescription, open Summary
2. **Verify:** A key/value grid shows: drug, dose, frequency, fill_date, days_supply, expiry_alert_date (if set)
3. **Verify:** If `expiry_alert_date` is set, a one-off renewal reminder was scheduled server-side (visible via `list_reminders` in a new chat turn)

### T20.6 — Structured — other types
1. For `other` / `imaging` / `visit_note` / `insurance` / `vaccine`: scroll to structured
2. **Verify:** A `Collapsible` shows the raw `structured` JSON inside a monospace `<pre>` (no fabricated UI for types we don't specifically template)

### T20.7 — Raw extracted text disclosure
1. At the bottom of the Summary tab, click "Show raw text" (or similar collapsible trigger)
2. **Verify:** A `ScrollArea` expands with the full `extracted_text` in monospace, whitespace preserved
3. **Verify:** `GET /api/v1/documents/{id}?include_extracted_text=true` is called OR the full row was already fetched with extracted text
4. Collapse
5. **Verify:** Panel closes cleanly

---

## Suite 21: Cancel During Processing

### T21.1 — Delete a processing doc
1. Upload a large PDF; while status is still `processing`, open the pane and Delete
2. **Verify:** Network: `DELETE /api/v1/documents/{id}` succeeds
3. **Verify:** The processor logs a `doc processing cancelled mid-flight` line (in scheduler logs)
4. **Verify:** No memory entry is written, no renewal reminder created
5. **Verify:** The DocCard's SSE stream emits a terminal event and closes

---

## Execution Notes

### Local dev stack

- Backend runs in docker: `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d agent scheduler postgres migrator`
- The nginx `web` container is NOT used locally — start Vite for HMR: `cd web && bun dev --port 3000`
- `bun dev` uses port 3000 (not the default 5173) so it matches the CORS allowlist in `server/main.py` and the OAuth redirect in `.env.local`
- Agent auto-reloads on code edits via `--reload` (source mounted). Frontend HMR is instant via Vite.

### DocAgent test prerequisites

- GCS bucket `gs://live150-docs-dev` must exist in `clawdbot-project-489814` (or whichever project matches `GOOGLE_CLOUD_PROJECT`). Verified once at setup.
- ADC must be logged in with the same project: `gcloud auth application-default login`.
- Alembic head must be `d4e5f6a7b8c9` (adds `document` table + `chat_message_id` column + `cancelled` status). Verify with `docker exec maya-pa-postgres-1 psql -U live150 -d live150 -c "SELECT version_num FROM alembic_version;"`.
- Gemini 3.1 Pro (used by DocAgent) must be enabled on the project (`aiplatform.googleapis.com`).

### Observability while testing DocAgent

- **Agent logs:** `docker logs -f maya-pa-agent-1` — upload + SSE endpoint calls, DELETE, history joins.
- **Scheduler logs:** `docker logs -f maya-pa-scheduler-1` — this is where `process_document` runs; watch for the four stage publishes (reading/context/summarizing/ready) and any Pydantic validation errors on the Gemini output.
- **Postgres:** NOTIFY channels are `doc_<uuid_hex>` and `notif_<sha256 of phone, first 16 hex chars>`. You can `psql` in and `LISTEN doc_<...>` to watch raw events.
- **Network:** In browser devtools, SSE streams show as pending `text/event-stream` fetches; expect one active per mounted DocCard in a non-terminal status.

### Running the suites

- Run each suite sequentially within a user; suites for different users can run in parallel.
- Screenshot key states: empty state (note time-based greeting), tool call expanded, error state, each user's greeting, notification banner, suggestion pills, DocCard processing / ready / failed, right pane Preview + Summary, PDF zoom controls.
- Document-processing turns may take 20–90 seconds on first PDF (Gemini 3.1 Pro is slower than Flash-Lite); subsequent uploads reuse the cached DocAgent instance.
- If a test fails, log: the exact message sent, the full response received, any console errors, and the relevant container log window.
- Streaming chat responses take 5–15s depending on Vertex AI latency.
- History loading is async — allow 1-2s on page load before asserting empty state.
