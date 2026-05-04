# Maya Voice Agent Design

## Goal

Add real-time voice conversation to Maya, Liv150's health companion. Maya becomes a universal voice layer across the entire app — a floating orb accessible from any screen. The voice agent shares memory with the existing text agent so Maya is one continuous personality regardless of interface.

## Architecture

Maya voice lives in the **maya-pa server** alongside the existing text agent. The mobile app (maya-ppa) connects via WebSocket. The server proxies audio bidirectionally to Gemini Live API, handles tool calls server-side, and shares the pgvector memory store with the text agent.

```
Mobile App (maya-ppa)
  │
  │  WebSocket (JSON frames: audio as base64 PCM 16kHz 16-bit mono)
  │  Auth: JWT access token as query param
  │
maya-pa server (FastAPI)
  ├── /api/v1/voice/ws        ← NEW: WebSocket voice endpoint
  │     ├── Validate JWT, load user profile + recent memories
  │     ├── Open Gemini Live session
  │     ├── Inject system prompt (SOUL.md + voice addendum) + user context
  │     ├── Relay: mobile audio → Gemini, Gemini audio → mobile
  │     ├── Tool calls: intercept, execute server-side, respond to Gemini
  │     └── On disconnect: close Gemini session
  │
  ├── /api/v1/voice/prewarm   ← NEW: background warm-up
  ├── /api/v1/stream/chat     ← existing text endpoint (unchanged)
  │
  └── Shared: pgvector memory, user context, liv150-api
```

**Model:** `gemini-2.5-flash-native-audio-preview-12-2025` via Vertex AI, `global` region.

**Key decisions:**
- Direct `google-genai` SDK (no PipeCat framework)
- Server proxies all audio (mobile never talks to Gemini directly)
- Tool calls handled server-side (client stays thin)
- Temperature 1.0 (required — lower values cause tool-call loops per Gemini Live known issue)
- Ephemeral conversation turns, durable memory (no transcript persistence)

---

## Server: WebSocket Endpoint

### Connection Flow

**Endpoint:** `GET /api/v1/voice/ws?token=<jwt_access_token>`

1. **Authenticate** — validate JWT, extract user phone. Reject with WebSocket close code 4001 if invalid.

2. **Initialize context:**
   - Fetch user profile from liv150-api (`GET /api/v1/users/me`)
   - Load recent memories via `MemoryService.recall()` (top 10-15 facts/preferences)
   - Build system instruction: SOUL.md + voice-specific addendum
   - Get user's local time and timezone

3. **Open Gemini Live session:**
   ```python
   session = await genai_client.aio.live.connect(
       model="gemini-2.5-flash-native-audio-preview-12-2025",
       config={
           "system_instruction": system_prompt,
           "tools": [{"function_declarations": voice_tool_declarations}],
           "response_modalities": ["AUDIO"],
           "generation_config": {"temperature": 1.0},
       },
   )
   ```

4. **Inject user context** as initial message (before any audio):
   ```python
   await session.send_client_content(
       turns=Content(role="user", parts=[Part(text=user_context_text)]),
       turn_complete=True,
   )
   ```

5. **Start relay loop** — two concurrent async tasks.

### Relay Loop

**Inbound task (mobile → Gemini):**
```python
async for message in websocket:
    payload = json.loads(message)
    if payload["type"] == "audio":
        pcm_bytes = base64.b64decode(payload["data"])
        await session.send_realtime_input(audio=Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000"))
```

**Outbound task (Gemini → mobile):**
```python
async for msg in session.receive():
    if msg.server_content and msg.server_content.parts:
        for part in msg.server_content.parts:
            if part.inline_data:
                await websocket.send_json({
                    "type": "audio",
                    "data": base64.b64encode(part.inline_data.data).decode(),
                })

    if msg.tool_call:
        results = await execute_tool_calls(msg.tool_call.function_calls, user_phone, db)
        await session.send_tool_response(function_responses=results)
```

**State messages** — server sends state updates to drive orb animation:
```json
{"type": "state", "state": "listening"}
{"type": "state", "state": "thinking"}
{"type": "state", "state": "speaking"}
```

State transitions:
- `listening` — default state, user is speaking or silence
- `thinking` — tool call in progress
- `speaking` — Gemini is sending audio response

### Disconnect

Either side closes the WebSocket. Server cancels both relay tasks, closes the Gemini session. No special cleanup — memory is already persisted via `save_memory` tool calls during conversation.

### Error Handling

- Gemini session drops: send WebSocket close frame with code 1011, mobile auto-reconnects
- Tool call fails: return error message to Gemini (it will verbalize the failure naturally)
- JWT expired mid-session: mobile detects 4001 close, refreshes token, reconnects

---

## Server: Prewarm Endpoint

**Endpoint:** `POST /api/v1/voice/prewarm`

Called by mobile in the background when app launches or user navigates to a screen with the voice button. Does NOT open a Gemini session (avoids billing).

Actions:
- Touch DB to prime connection pool
- Refresh Google ADC credentials if stale
- Optionally pre-load user profile into a short-lived cache

Returns 204 immediately (fire-and-forget background task).

---

## Server: Voice Tools

8 tools registered directly with Gemini Live API (not via ADK). Tool handler functions live in the server and share implementation with the text agent where possible.

### Tool Declarations

| Tool | Description | Backend |
|------|-------------|---------|
| `search_memory` | Recall facts, preferences, past events | Shared MemoryService (pgvector) |
| `save_memory` | Persist facts, preferences, events | Shared MemoryService (pgvector) |
| `log_nams` | Log nutrition/activity/mindfulness/sleep | liv150-api + memory write |
| `get_progress_by_date` | Daily health summary | liv150-api |
| `get_health_goals` | User's active goals | liv150-api (user profile) |
| `create_reminder` | Schedule a future notification | liv150-api |
| `list_reminders` | List active reminders | liv150-api |
| `cancel_reminder` | Delete a reminder | liv150-api |

### Consolidation

Following the reference project's pattern, `log_nams` consolidates nutrition, activity, mindfulness, and sleep logging into one tool with a `category` dispatch parameter. This keeps the tool count low (Gemini Live performs best with 10-20 tools).

### Tool Handler Pattern

```python
async def execute_tool_calls(function_calls, user_phone, db):
    results = []
    for fc in function_calls:
        handler = TOOL_HANDLERS.get(fc.name)
        result = await handler(fc.args, user_phone, db)
        results.append(FunctionResponse(name=fc.name, id=fc.id, response=result))
    return results
```

Tool handlers are async functions that return dicts. Memory tools use `MemoryService` directly (same singleton instance as the text agent). Health/reminder tools call liv150-api via `httpx.AsyncClient` using the user's JWT access token (same token used to authenticate the WebSocket). A shared `Liv150Client` wrapper handles base URL config and auth headers.

---

## Server: System Prompt

### Base Identity

Reuse `SOUL.md` unchanged. Maya's personality is the same in voice and text.

### Voice-Specific Addendum

Appended to the system instruction:

```
You are speaking aloud in a real-time voice conversation. Follow these voice-specific rules:

- Keep responses to 1-3 sentences. Brevity is critical — the user is listening, not reading.
- Never use markdown, bullets, numbered lists, or formatting. Speak naturally.
- Never spell out URLs, code, or structured data. Say "I'll save that" or "check your app for details."
- Use natural speech fillers sparingly ("let me check", "so") — don't be robotic.
- When you use a tool, don't narrate it. Just pause briefly and continue with the answer.
- If the answer would be long (meal plans, multi-day summaries), give a 1-sentence summary and say "I've put the details in your app" — then save a note via memory.
- Match the user's energy. Short question → short answer. Excited → match warmth.
```

### User Context (injected on connect)

```
User: {display_name}, Age: {age}, Goals: {goals joined by comma}
Health conditions: {conditions joined by comma}
Local time: {HH:MM} ({timezone_name})

Recent context:
- {memory_hit_1}
- {memory_hit_2}
- ...up to 10-15 entries
```

---

## Server: Shared Memory Bridge

Both voice and text agents read/write to the same pgvector `memory_entry` table via the shared `MemoryService`.

**Voice → Text continuity:** User tells voice-Maya "I started intermittent fasting." Maya calls `save_memory(kind="fact", content="User started intermittent fasting")`. Next morning, text-Maya's daily briefing searches memory and incorporates this.

**Text → Voice continuity:** Text-Maya saves "Recommended user try 10-minute evening walks." User asks voice-Maya "what did you suggest for my evenings?" Memory search returns the recommendation.

**On voice connect:** server loads top 10-15 recent memories and injects as initial context. This gives Maya immediate awareness of prior conversations without replaying transcripts.

The `MemoryService` is a singleton in maya-pa — both the text agent's `memory_tools.py` and the new voice tool handlers import the same instance.

---

## Mobile: Voice Provider

### VoiceProvider (root-level context)

Wraps the entire app in `_layout.tsx`, inside `AuthProvider` (needs access token).

**State:**
- `isActive: boolean` — voice session overlay is open
- `isConnected: boolean` — WebSocket is established
- `agentState: "listening" | "thinking" | "speaking" | "idle"` — drives orb animation

**Methods:**
- `startSession()` — open overlay, request mic permission, connect WebSocket, start audio capture
- `endSession()` — stop audio, close WebSocket, dismiss overlay

### Audio Pipeline

**Recording:**
- `expo-audio` for microphone capture
- PCM 16-bit, 16kHz, mono
- Echo cancellation configured at OS level:
  - iOS: `AVAudioSession` category `.playAndRecord` with `.defaultToSpeaker` — AEC is automatic
  - Android: `VOICE_COMMUNICATION` audio source — activates built-in AEC
- Stream chunks to WebSocket as they're captured (no wait-for-silence — Gemini's VAD handles turn detection)

**Playback:**
- Receive PCM chunks from server via WebSocket
- Play through the same audio session used for recording (required for AEC)
- Small buffer (~100-150ms) before playback to smooth jitter
- Drain buffer when audio stops (turn complete)

**Interruption:**
- User speaks while Maya is talking → Gemini VAD detects, cancels response
- Server stops sending audio → mobile drains buffer and stops playback
- Server sends `{"type": "state", "state": "listening"}` to confirm

### WebSocket Message Format

```
Client → Server:  {"type": "audio", "data": "<base64 PCM chunk>"}
Server → Client:  {"type": "audio", "data": "<base64 PCM chunk>"}
Server → Client:  {"type": "state", "state": "listening" | "thinking" | "speaking"}
```

---

## Mobile: Voice UI Components

### VoiceFab (floating action button)

- Renders at app root level (in `_layout.tsx`), visible on every screen
- Positioned bottom-right, above tab bar when tabs visible
- Uses existing `MayaOrb` component (smaller size, ~48px)
- Tap → calls `startSession()`
- Hidden when voice session is active (replaced by overlay)
- "Ask Maya" buttons throughout the app also call `startSession()`

### VoiceOverlay (full-screen session UI)

- Absolute-positioned view covering the full screen with dark background
- Large `MayaOrb` centered (pulsing when listening, glowing when speaking, still when thinking)
- Close button (top-right or bottom)
- No transcript, no text — pure voice interface
- Orb animation driven by `agentState` from VoiceProvider

---

## Mobile: File Structure

```
src/
├── voice/
│   ├── VoiceProvider.tsx     # Root context: WebSocket, audio, state management
│   ├── useVoice.ts           # Hook: startSession, endSession, isActive, agentState
│   ├── audio.ts              # expo-audio config: PCM capture, AEC, playback queue
│   └── ws.ts                 # WebSocket client: connect, send/receive, reconnect
├── components/
│   └── ds/
│       ├── VoiceFab.tsx      # Floating orb button (visible on all screens)
│       └── VoiceOverlay.tsx  # Full-screen voice session UI
```

**Modified files:**
- `src/app/_layout.tsx` — add `VoiceProvider` + `VoiceFab` at root level

---

## Server: File Structure

```
server/src/live150/
├── api/
│   └── voice.py              # WebSocket endpoint + prewarm endpoint
├── voice/
│   ├── session.py            # GeminiLiveSession: connect, relay, tool dispatch
│   ├── tools.py              # 8 tool declarations + handler functions
│   ├── context.py            # System prompt builder + user context loader
│   └── prewarm.py            # Prewarm logic (DB ping, ADC refresh)
```

**Modified files:**
- `server/src/live150/main.py` — register voice router

**Unchanged:** all existing text agent code (builder.py, runner.py, stream.py, registry.py, tools/).

---

## Scope Boundary

**In scope:**
- Voice WebSocket endpoint with Gemini Live proxy
- 8 voice tools hitting liv150-api + shared memory
- Mobile voice UI (VoiceProvider, VoiceFab, VoiceOverlay, audio pipeline)
- Prewarm endpoint
- Echo cancellation (OS-level AEC)

**Out of scope (future work):**
- Onboarding voice integration (Maya listening during onboarding steps)
- Voice-to-text transcript display
- Multi-language voice support
- Voice wake word ("Hey Maya")
- Push-to-talk mode
- New liv150-api endpoints (health progress, reminders) — these will be built as part of the voice agent tasks since the tools need them

---

## Key Technical Constraints

1. **Temperature must be 1.0** — Gemini Live has a known issue where lower temperatures cause infinite tool-call loops.
2. **Tool call IDs are required** — Gemini Live requires the exact `id` from the function call in the tool response (Vertex AI is slightly more forgiving but we should always include it).
3. **No ADK for voice** — the voice agent uses Gemini Live API directly, not Google ADK. ADK doesn't support the Live API protocol.
4. **`send_realtime_input` takes one argument per call** — enforced by the SDK. Send audio OR text, not both.
5. **AEC requires shared audio session** — recording and playback must use the same audio session for OS-level echo cancellation to work on both iOS and Android.
