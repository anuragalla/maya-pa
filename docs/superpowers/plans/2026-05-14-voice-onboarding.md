# Voice Onboarding Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a voice-powered onboarding flow where Maya guides new users through profile setup (age through diet) via Gemini Live API, while users can still type manually. Name step remains text-only.

**Architecture:** Separate `OnboardingVoiceSession` in maya-pa connects to Gemini 3.1 Flash Live with 3 function-calling tools (`set_onboarding_field`, `advance_step`, `go_back`). Tool calls are forwarded over the existing WebSocket to the mobile app, which updates local onboarding state and makes the API calls itself. A new `/api/v1/voice/onboarding/ws` endpoint handles the onboarding-specific voice session. The genai client switches from Vertex AI to API key auth across the whole project.

**Tech Stack:** Python FastAPI, google-genai SDK (API key mode), Gemini 3.1 Flash Live, WebSocket, React Native (Expo), `@mykin-ai/expo-audio-stream` (real-time PCM streaming), `@shopify/react-native-skia` (border glow effect)

---

## File Map

### Backend (maya-pa)

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `server/src/live150/config.py` | Add `gemini_api_key`, `jwt_secret`, `jwt_algorithm` settings |
| Modify | `server/src/live150/agent/genai_client.py` | Switch from Vertex AI to API key |
| Create | `server/src/live150/voice/onboarding_context.py` | System prompt for onboarding agent |
| Create | `server/src/live150/voice/onboarding_tools.py` | 3 tool declarations + handlers |
| Create | `server/src/live150/voice/onboarding_session.py` | OnboardingVoiceSession class |
| Modify | `server/src/live150/voice/session.py` | Update VOICE_MODEL constant |
| Modify | `server/src/live150/api/voice.py` | Add `/onboarding/ws` endpoint, update JWT decode |

### Mobile (maya-ppa)

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `src/voice/ws.ts` | Add onboarding WS connection + tool_call + step_sync message types |
| Create | `src/voice/useOnboardingVoice.ts` | Hook: manages onboarding voice session lifecycle, real-time audio I/O, tool call dispatch |
| Create | `src/components/ds/ScreenBorderGlow.tsx` | Skia-based screen edge glow (Siri-style) animated by agent state |
| Modify | `src/app/(auth)/onboarding.tsx` | Wire voice from step 2+, ScreenBorderGlow, mute button, step sync |

---

## Task 1: Switch genai client from Vertex AI to API key

**Files:**
- Modify: `server/src/live150/config.py`
- Modify: `server/src/live150/agent/genai_client.py`

- [ ] **Step 1: Add `gemini_api_key` to config**

In `server/src/live150/config.py`, add to the `Settings` class:

```python
    # Gemini
    gemini_api_key: str = ""
```

- [ ] **Step 2: Switch genai_client.py to API key**

Replace the entire `get_genai_client` function in `server/src/live150/agent/genai_client.py`:

```python
"""Shared, cached `google.genai` client.

Single cached client using API key auth.
Lazy-imports `google.genai` so tests don't need credentials.
"""

import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.genai import Client


@lru_cache(maxsize=1)
def get_genai_client() -> "Client":
    """Return a cached Gemini client using API key."""
    from google import genai

    return genai.Client(
        api_key=os.environ.get("LIVE150_GEMINI_API_KEY", ""),
    )
```

- [ ] **Step 3: Update .env.example**

Remove the Vertex AI env vars and add:

```
# Gemini
LIVE150_GEMINI_API_KEY=<your-gemini-api-key>
```

- [ ] **Step 4: Verify existing voice session still initializes**

Run: `cd server && PYTHONPATH=src python -c "from live150.agent.genai_client import get_genai_client; print('OK')"`

Expected: `OK` (no import errors)

- [ ] **Step 5: Commit**

```bash
git add server/src/live150/config.py server/src/live150/agent/genai_client.py
git commit -m "feat: switch genai client from Vertex AI to API key auth"
```

---

## Task 2: Update JWT decode to accept liv150-api tokens

**Files:**
- Modify: `server/src/live150/config.py`
- Modify: `server/src/live150/api/voice.py`

- [ ] **Step 1: Add JWT settings to config**

In `server/src/live150/config.py`, add to `Settings`:

```python
    # JWT (shared with liv150-api)
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
```

- [ ] **Step 2: Update `_decode_token` in voice.py**

Replace the `_decode_token` function in `server/src/live150/api/voice.py`:

```python
def _decode_token(token: str) -> dict | None:
    """Decode a liv150-api JWT. Returns claims or None."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
```

- [ ] **Step 3: Update user_phone extraction in `voice_ws`**

The liv150-api JWT has `sub` = user UUID and `phone` = phone number. Update the `voice_ws` handler to extract phone from the `phone` claim:

In `voice_ws`, change:

```python
    user_phone = claims.get("sub", "")
```

to:

```python
    user_id = claims.get("sub", "")
    user_phone = claims.get("phone", "")
    if not user_id or not user_phone:
        await websocket.close(code=4001, reason="Invalid token: missing claims")
        return
```

And update the logger and `VoiceSession` to use `user_phone` (which now comes from the `phone` claim). Also pass the token directly as `access_token` to `_load_user_profile` and `VoiceSession`:

```python
    profile = await _load_user_profile(token)
```

This already works correctly — `_load_user_profile` calls `/api/v1/users/me` with `Bearer {token}`, and liv150-api will validate its own JWT.

- [ ] **Step 4: Commit**

```bash
git add server/src/live150/config.py server/src/live150/api/voice.py
git commit -m "feat: accept liv150-api JWT tokens in voice WebSocket"
```

---

## Task 3: Update voice model to Gemini 3.1 Flash Live

**Files:**
- Modify: `server/src/live150/voice/session.py`

- [ ] **Step 1: Update the model constant**

In `server/src/live150/voice/session.py`, change:

```python
VOICE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
```

to:

```python
VOICE_MODEL = "gemini-3.1-flash-live-preview"
```

- [ ] **Step 2: Commit**

```bash
git add server/src/live150/voice/session.py
git commit -m "feat: upgrade voice model to gemini-3.1-flash-live-preview"
```

---

## Task 4: Create onboarding voice tools

**Files:**
- Create: `server/src/live150/voice/onboarding_tools.py`

- [ ] **Step 1: Create tool declarations and handlers**

Create `server/src/live150/voice/onboarding_tools.py`:

```python
"""Onboarding voice tool declarations and handlers.

Three tools for the onboarding voice agent:
- set_onboarding_field: Set a profile field value
- advance_step: Move to the next onboarding step
- go_back: Return to the previous step
"""

import logging

logger = logging.getLogger(__name__)

VALID_STEPS = ["age", "gender", "height", "weight", "conditions", "goals", "diet"]

GENDER_OPTIONS = ["female", "male", "nonbinary", "prefer_not_to_say"]
CONDITION_OPTIONS = ["stress", "heart", "bp", "diabetes", "sleep", "thyroid", "pcos", "none"]
GOAL_OPTIONS = ["fatloss", "glucose", "sleep", "strength", "stress", "longevity"]
DIET_OPTIONS = ["vegetarian", "non_veg", "vegan", "pescatarian", "flexible"]

TOOL_DECLARATIONS: list[dict] = [
    {
        "name": "set_onboarding_field",
        "description": (
            "Set a value for a specific onboarding profile field. "
            "Call this when the user provides information for any onboarding step. "
            "The frontend will update the UI to reflect the selection."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "step": {
                    "type": "string",
                    "enum": VALID_STEPS,
                    "description": "Which onboarding field to set.",
                },
                "value": {
                    "description": (
                        "The value to set. Type depends on step:\n"
                        "- age: integer (e.g. 28)\n"
                        "- gender: one of 'female', 'male', 'nonbinary', 'prefer_not_to_say'\n"
                        "- height: integer in centimeters (convert from feet/inches if needed, e.g. 5'10\" = 178)\n"
                        "- weight: integer in kilograms (convert from pounds if needed, e.g. 165 lb = 75)\n"
                        "- conditions: array of strings from ['stress', 'heart', 'bp', 'diabetes', 'sleep', 'thyroid', 'pcos', 'none']\n"
                        "- goals: array of strings from ['fatloss', 'glucose', 'sleep', 'strength', 'stress', 'longevity']\n"
                        "- diet: one of 'vegetarian', 'non_veg', 'vegan', 'pescatarian', 'flexible'"
                    ),
                },
            },
            "required": ["step", "value"],
        },
    },
    {
        "name": "advance_step",
        "description": (
            "Move to the next onboarding step. Call this when the user confirms "
            "their current selection or says something like 'next', 'continue', 'that's it', 'done'. "
            "Do NOT call this immediately after set_onboarding_field — wait for user confirmation."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "go_back",
        "description": (
            "Go back to the previous onboarding step. Call when the user says "
            "'go back', 'previous', 'wait let me change that', etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


def _validate_field(step: str, value) -> tuple[bool, str]:
    """Validate a field value. Returns (is_valid, error_message)."""
    if step == "age":
        if not isinstance(value, (int, float)) or value < 13 or value > 120:
            return False, "Age must be a number between 13 and 120."
        return True, ""

    if step == "gender":
        if value not in GENDER_OPTIONS:
            return False, f"Gender must be one of: {', '.join(GENDER_OPTIONS)}"
        return True, ""

    if step == "height":
        if not isinstance(value, (int, float)) or value < 120 or value > 240:
            return False, "Height must be between 120 and 240 cm."
        return True, ""

    if step == "weight":
        if not isinstance(value, (int, float)) or value < 30 or value > 200:
            return False, "Weight must be between 30 and 200 kg."
        return True, ""

    if step == "conditions":
        if not isinstance(value, list):
            return False, "Conditions must be a list."
        invalid = [v for v in value if v not in CONDITION_OPTIONS]
        if invalid:
            return False, f"Invalid conditions: {', '.join(invalid)}"
        return True, ""

    if step == "goals":
        if not isinstance(value, list):
            return False, "Goals must be a list."
        invalid = [v for v in value if v not in GOAL_OPTIONS]
        if invalid:
            return False, f"Invalid goals: {', '.join(invalid)}"
        return True, ""

    if step == "diet":
        if value not in DIET_OPTIONS:
            return False, f"Diet must be one of: {', '.join(DIET_OPTIONS)}"
        return True, ""

    return False, f"Unknown step: {step}"


async def handle_set_onboarding_field(args: dict, **_ctx) -> dict:
    step = args.get("step", "")
    value = args.get("value")

    if step not in VALID_STEPS:
        return {"success": False, "error": f"Unknown step: {step}"}

    if value is None:
        return {"success": False, "error": "No value provided."}

    if step in ("height", "weight", "age") and isinstance(value, (int, float)):
        value = int(round(value))

    valid, error = _validate_field(step, value)
    if not valid:
        return {"success": False, "error": error}

    return {"success": True, "step": step, "value": value}


async def handle_advance_step(**_ctx) -> dict:
    return {"success": True, "action": "advance"}


async def handle_go_back(**_ctx) -> dict:
    return {"success": True, "action": "go_back"}


ONBOARDING_TOOL_HANDLERS: dict = {
    "set_onboarding_field": handle_set_onboarding_field,
    "advance_step": handle_advance_step,
    "go_back": handle_go_back,
}


def get_onboarding_tool_config() -> list[dict]:
    """Return the tools config for the onboarding Gemini Live session."""
    return [{"function_declarations": TOOL_DECLARATIONS}]
```

- [ ] **Step 2: Commit**

```bash
git add server/src/live150/voice/onboarding_tools.py
git commit -m "feat: add onboarding voice tool declarations and handlers"
```

---

## Task 5: Create onboarding voice context (system prompt)

**Files:**
- Create: `server/src/live150/voice/onboarding_context.py`

- [ ] **Step 1: Create the onboarding system prompt**

Create `server/src/live150/voice/onboarding_context.py`:

```python
"""System prompt and user context for onboarding voice sessions."""

ONBOARDING_SYSTEM_PROMPT = """\
You are Maya, a friendly health companion guiding a new user through onboarding.

## Your job
Walk the user through setting up their health profile. They can see a form on screen \
and can type OR speak — you help with the voice side.

## Steps (in order)
The user's name is already set. You guide them through these steps:
1. age — Ask their age (integer)
2. gender — Options: Female, Male, Non-binary, Prefer not to say
3. height — In cm or feet/inches (you convert to cm for the tool call)
4. weight — In kg or pounds (you convert to kg for the tool call)
5. conditions — Multi-select: stress, heart condition, high blood pressure, diabetes, sleep issues, thyroid, PCOS, none
6. goals — Multi-select: lose fat, control blood sugar, sleep deeper, build strength, manage stress, pure longevity
7. diet — Options: vegetarian, non-veg, vegan, pescatarian, flexible

## Voice rules
- Keep responses to ONE sentence. "Got it, 28!" not "Great, I've recorded your age as 28 years old."
- Never list all options aloud — the user can see them on screen.
- For ambiguous input, ask ONE short clarifying question.
- When the user provides a value, call set_onboarding_field immediately, then confirm briefly.
- Do NOT call advance_step right after setting a field. Wait for the user to say "next", "continue", "done", "that's it", or similar.
- If the user corrects a previous step ("actually I'm 30, not 28"), call set_onboarding_field with that step. Briefly acknowledge that you're updating it and remind them which step they're currently on. Example: "Updated your age to 30. We're on height — how tall are you?"
- Match their energy — short answers for short inputs.
- Never use markdown, bullets, or formatting. Speak naturally.
- When they complete the last step (diet), say something warm like "All set! Let's get started."

## Unit conversion
- Heights in feet/inches: multiply feet by 30.48, add inches times 2.54, round to nearest integer.
  Example: 5'10" = 5*30.48 + 10*2.54 = 152.4 + 25.4 = 178 cm
- Weights in pounds: divide by 2.205, round to nearest integer.
  Example: 165 lb = 75 kg

## Multi-select steps (conditions, goals)
- Send the FULL list of selected items each time, not just the new one.
- If user says "add sleep issues", and they already have "diabetes", send ["diabetes", "sleep"].
- If user says "none of the above" for conditions, send ["none"].
"""


def build_onboarding_system_prompt() -> str:
    return ONBOARDING_SYSTEM_PROMPT


def build_onboarding_user_context(display_name: str) -> str:
    return f"The user's name is {display_name}. They just completed the name step and are ready for voice-guided onboarding. Greet them briefly by name and ask their age."
```

- [ ] **Step 2: Commit**

```bash
git add server/src/live150/voice/onboarding_context.py
git commit -m "feat: add onboarding voice agent system prompt"
```

---

## Task 6: Create OnboardingVoiceSession

**Files:**
- Create: `server/src/live150/voice/onboarding_session.py`

- [ ] **Step 1: Create the session class**

Create `server/src/live150/voice/onboarding_session.py`:

```python
"""OnboardingVoiceSession — Gemini Live session for onboarding flow.

Lighter than the general VoiceSession:
- Onboarding-specific system prompt and tools
- Tool calls forwarded to the client as structured commands (the mobile app handles API calls)
- No database access needed for tool handlers
"""

import asyncio
import base64
import json
import logging
from typing import Any, Literal

from google.genai import types

from live150.agent.genai_client import get_genai_client
from live150.voice.onboarding_context import (
    build_onboarding_system_prompt,
    build_onboarding_user_context,
)
from live150.voice.onboarding_tools import (
    ONBOARDING_TOOL_HANDLERS,
    get_onboarding_tool_config,
)

logger = logging.getLogger(__name__)

ONBOARDING_VOICE_MODEL = "gemini-3.1-flash-live-preview"

State = Literal["idle", "listening", "thinking", "speaking"]


class OnboardingVoiceSession:
    def __init__(self, user_id: str, user_phone: str):
        self.user_id = user_id
        self.user_phone = user_phone
        self.state: State = "idle"
        self.is_connected: bool = False
        self._gemini_session: Any = None
        self._gemini_ctx: Any = None
        self._tasks: list[asyncio.Task] = []

    async def connect(self, display_name: str) -> None:
        system_prompt = build_onboarding_system_prompt()
        user_context = build_onboarding_user_context(display_name)

        client = get_genai_client()
        config = types.LiveConnectConfig(
            system_instruction=system_prompt,
            tools=get_onboarding_tool_config(),
            response_modalities=["AUDIO"],
            temperature=0.7,
            enable_affective_dialog=True,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede"),
                ),
            ),
        )

        self._gemini_ctx = client.aio.live.connect(
            model=ONBOARDING_VOICE_MODEL, config=config,
        )
        self._gemini_session = await self._gemini_ctx.__aenter__()
        self.is_connected = True
        self.state = "listening"

        await self._gemini_session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part(text=user_context)],
            ),
            turn_complete=True,
        )

    async def relay(self, websocket: Any) -> None:
        inbound = asyncio.create_task(
            self._inbound_loop(websocket), name="onboarding_voice_inbound",
        )
        outbound = asyncio.create_task(
            self._outbound_loop(websocket), name="onboarding_voice_outbound",
        )
        self._tasks = [inbound, outbound]

        try:
            done, pending = await asyncio.wait(
                self._tasks, return_when=asyncio.FIRST_EXCEPTION,
            )
            for task in pending:
                task.cancel()
            for task in done:
                if task.exception():
                    raise task.exception()
        except asyncio.CancelledError:
            pass

    async def _inbound_loop(self, websocket: Any) -> None:
        try:
            async for raw in websocket.iter_text():
                msg = json.loads(raw)
                if msg.get("type") == "audio":
                    pcm_bytes = base64.b64decode(msg["data"])
                    await self._gemini_session.send_realtime_input(
                        audio=types.Blob(
                            data=pcm_bytes, mime_type="audio/pcm;rate=16000",
                        ),
                    )
        except Exception as e:
            logger.info("onboarding_inbound_closed", extra={"reason": str(e)})

    async def _outbound_loop(self, websocket: Any) -> None:
        try:
            async for msg in self._gemini_session.receive():
                if msg.server_content and msg.server_content.parts:
                    for part in msg.server_content.parts:
                        if part.inline_data and part.inline_data.data:
                            self.state = "speaking"
                            await websocket.send_json({
                                "type": "audio",
                                "data": base64.b64encode(
                                    part.inline_data.data,
                                ).decode(),
                            })

                    if msg.server_content.turn_complete:
                        self.state = "listening"
                        await websocket.send_json({
                            "type": "state", "state": "listening",
                        })

                if msg.tool_call and msg.tool_call.function_calls:
                    self.state = "thinking"
                    await websocket.send_json({
                        "type": "state", "state": "thinking",
                    })
                    responses = await self._execute_tools(
                        msg.tool_call.function_calls, websocket,
                    )
                    await self._gemini_session.send_tool_response(
                        function_responses=responses,
                    )

        except Exception as e:
            logger.info("onboarding_outbound_closed", extra={"reason": str(e)})

    async def _execute_tools(
        self, function_calls: list, websocket: Any,
    ) -> list:
        results = []
        for fc in function_calls:
            handler = ONBOARDING_TOOL_HANDLERS.get(fc.name)
            if not handler:
                results.append(types.FunctionResponse(
                    name=fc.name, id=fc.id,
                    response={"error": f"Unknown tool: {fc.name}"},
                ))
                continue

            try:
                result = await handler(args=fc.args or {})
            except Exception as e:
                logger.warning(
                    "onboarding_tool_failed",
                    extra={"tool": fc.name, "error": str(e)},
                )
                result = {"error": True, "message": str(e)}

            # Forward tool call to mobile app so it can update UI
            await websocket.send_json({
                "type": "tool_call",
                "name": fc.name,
                "args": fc.args or {},
                "result": result,
            })

            results.append(types.FunctionResponse(
                name=fc.name, id=fc.id, response=result,
            ))
        return results

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._gemini_session:
            try:
                await self._gemini_ctx.__aexit__(None, None, None)
            except Exception:
                pass
        self.is_connected = False
        self.state = "idle"
```

- [ ] **Step 2: Commit**

```bash
git add server/src/live150/voice/onboarding_session.py
git commit -m "feat: add OnboardingVoiceSession for voice-guided onboarding"
```

---

## Task 7: Add onboarding WebSocket endpoint

**Files:**
- Modify: `server/src/live150/api/voice.py`

- [ ] **Step 1: Add the onboarding WS endpoint**

Add this handler below the existing `voice_ws` function in `server/src/live150/api/voice.py`:

```python
from live150.voice.onboarding_session import OnboardingVoiceSession


@router.websocket("/onboarding/ws")
async def onboarding_voice_ws(websocket: WebSocket, token: str = ""):
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    claims = _decode_token(token)
    if not claims:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = claims.get("sub", "")
    user_phone = claims.get("phone", "")
    if not user_id or not user_phone:
        await websocket.close(code=4001, reason="Invalid token: missing claims")
        return

    await websocket.accept()
    logger.info("onboarding_voice_ws_connected", extra={"user": user_phone})

    profile = await _load_user_profile(token)
    display_name = (profile.get("display_name") or "there") if profile else "there"

    session = OnboardingVoiceSession(user_id=user_id, user_phone=user_phone)

    try:
        await session.connect(display_name=display_name)
        await websocket.send_json({"type": "state", "state": "listening"})
        await session.relay(websocket)

    except WebSocketDisconnect:
        logger.info("onboarding_voice_ws_disconnected", extra={"user": user_phone})
    except Exception as e:
        logger.error("onboarding_voice_ws_error", extra={"user": user_phone, "error": str(e)})
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=1011, reason="Internal error")
    finally:
        await session.close()
        logger.info("onboarding_voice_session_closed", extra={"user": user_phone})
```

- [ ] **Step 2: Add the import at the top of the file**

Add to imports:

```python
from live150.voice.onboarding_session import OnboardingVoiceSession
```

- [ ] **Step 3: Commit**

```bash
git add server/src/live150/api/voice.py
git commit -m "feat: add /voice/onboarding/ws WebSocket endpoint"
```

---

## Task 8: Add onboarding voice WS to mobile

**Files:**
- Modify: `maya-ppa/src/voice/ws.ts`

- [ ] **Step 1: Add tool_call message type and onboarding connection**

Update `maya-ppa/src/voice/ws.ts`. Add the `OnboardingToolCall` type and `connectOnboardingVoiceWS` function:

```typescript
import { authStorage } from '@/auth/storage';

const BASE_URL = process.env.EXPO_PUBLIC_MAYA_BASE_URL ?? 'https://150.trackgenie.in';

export type AgentState = 'idle' | 'listening' | 'thinking' | 'speaking';

export type VoiceMessage =
  | { type: 'audio'; data: string }
  | { type: 'state'; state: AgentState };

export type OnboardingStep = 'age' | 'gender' | 'height' | 'weight' | 'conditions' | 'goals' | 'diet';

export type OnboardingToolCall =
  | { type: 'tool_call'; name: 'set_onboarding_field'; args: { step: OnboardingStep; value: number | string | string[] }; result: { success: boolean } }
  | { type: 'tool_call'; name: 'advance_step'; args: Record<string, never>; result: { success: boolean } }
  | { type: 'tool_call'; name: 'go_back'; args: Record<string, never>; result: { success: boolean } };

type OnboardingMessage = VoiceMessage | OnboardingToolCall;

export type VoiceWSCallbacks = {
  onAudio: (pcmBase64: string) => void;
  onStateChange: (state: AgentState) => void;
  onClose: (code: number, reason: string) => void;
  onError: (error: Event) => void;
};

export type OnboardingVoiceWSCallbacks = VoiceWSCallbacks & {
  onToolCall: (toolCall: OnboardingToolCall) => void;
};

export function connectVoiceWS(callbacks: VoiceWSCallbacks): {
  send: (msg: VoiceMessage) => void;
  close: () => void;
} {
  const token = authStorage.getAccessToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const wsUrl = BASE_URL.replace(/^http/, 'ws') + `/api/v1/voice/ws?token=${token}`;
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const msg: VoiceMessage = JSON.parse(event.data as string);
      if (msg.type === 'audio') {
        callbacks.onAudio(msg.data);
      } else if (msg.type === 'state') {
        callbacks.onStateChange(msg.state);
      }
    } catch {
      // ignore malformed messages
    }
  };

  ws.onclose = (event) => {
    callbacks.onClose(event.code, event.reason);
  };

  ws.onerror = (event) => {
    callbacks.onError(event);
  };

  return {
    send: (msg: VoiceMessage) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg));
      }
    },
    close: () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    },
  };
}

export function connectOnboardingVoiceWS(callbacks: OnboardingVoiceWSCallbacks): {
  send: (msg: VoiceMessage) => void;
  close: () => void;
} {
  const token = authStorage.getAccessToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const wsUrl = BASE_URL.replace(/^http/, 'ws') + `/api/v1/voice/onboarding/ws?token=${token}`;
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const msg: OnboardingMessage = JSON.parse(event.data as string);
      if (msg.type === 'audio') {
        callbacks.onAudio(msg.data);
      } else if (msg.type === 'state') {
        callbacks.onStateChange(msg.state);
      } else if (msg.type === 'tool_call') {
        callbacks.onToolCall(msg);
      }
    } catch {
      // ignore malformed messages
    }
  };

  ws.onclose = (event) => {
    callbacks.onClose(event.code, event.reason);
  };

  ws.onerror = (event) => {
    callbacks.onError(event);
  };

  return {
    send: (msg: VoiceMessage) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg));
      }
    },
    close: () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    },
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add maya-ppa/src/voice/ws.ts
git commit -m "feat: add onboarding voice WebSocket connection with tool call support"
```

---

## Task 9: Create useOnboardingVoice hook

**Files:**
- Create: `maya-ppa/src/voice/useOnboardingVoice.ts`

- [ ] **Step 1: Create the hook**

Create `maya-ppa/src/voice/useOnboardingVoice.ts`:

```typescript
import { useCallback, useRef, useState } from 'react';
import {
  type AgentState,
  type OnboardingToolCall,
  type VoiceMessage,
  connectOnboardingVoiceWS,
} from './ws';
import { configureAudioSession, requestMicPermission } from './audio';

type OnToolCall = (toolCall: OnboardingToolCall) => void;

export function useOnboardingVoice(onToolCall: OnToolCall) {
  const [isActive, setIsActive] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [agentState, setAgentState] = useState<AgentState>('idle');
  const wsRef = useRef<ReturnType<typeof connectOnboardingVoiceWS> | null>(null);
  const onToolCallRef = useRef(onToolCall);
  onToolCallRef.current = onToolCall;

  const start = useCallback(async () => {
    const granted = await requestMicPermission();
    if (!granted) return;

    await configureAudioSession();
    setIsActive(true);
    setAgentState('listening');

    try {
      const ws = connectOnboardingVoiceWS({
        onAudio: (_pcmBase64: string) => {
          // Audio playback will be wired during integration testing
        },
        onStateChange: (state: AgentState) => {
          setAgentState(state);
        },
        onToolCall: (toolCall: OnboardingToolCall) => {
          onToolCallRef.current(toolCall);
        },
        onClose: () => {
          setIsConnected(false);
          setIsActive(false);
          setAgentState('idle');
        },
        onError: () => {
          setIsConnected(false);
          setIsActive(false);
          setAgentState('idle');
        },
      });
      wsRef.current = ws;
      setIsConnected(true);
    } catch {
      setIsActive(false);
      setAgentState('idle');
    }
  }, []);

  const stop = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
    setIsActive(false);
    setAgentState('idle');
  }, []);

  const send = useCallback((msg: VoiceMessage) => {
    wsRef.current?.send(msg);
  }, []);

  return { isActive, isConnected, agentState, start, stop, send };
}
```

- [ ] **Step 2: Commit**

```bash
git add maya-ppa/src/voice/useOnboardingVoice.ts
git commit -m "feat: add useOnboardingVoice hook for voice-guided onboarding"
```

---

## Task 10: Wire voice into onboarding screen

**Files:**
- Modify: `maya-ppa/src/app/(auth)/onboarding.tsx`

- [ ] **Step 1: Add voice integration to OnboardingScreen**

Add these imports at the top of `onboarding.tsx`:

```typescript
import { useOnboardingVoice } from '@/voice/useOnboardingVoice';
import type { OnboardingToolCall } from '@/voice/ws';
```

- [ ] **Step 2: Add voice hook and tool call handler inside OnboardingScreen**

Inside the `OnboardingScreen` component, after the existing state declarations (`const [profile, setProfile] = ...`), add:

```typescript
  const handleToolCall = useCallback(
    (tc: OnboardingToolCall) => {
      if (tc.name === 'set_onboarding_field' && tc.result.success) {
        const { step: fieldStep, value } = tc.args;
        const patch: Record<string, unknown> = {};

        if (fieldStep === 'age') patch.age = value;
        else if (fieldStep === 'gender') patch.gender = value;
        else if (fieldStep === 'height') patch.height = value;
        else if (fieldStep === 'weight') patch.weight = value;
        else if (fieldStep === 'conditions') patch.conditions = value;
        else if (fieldStep === 'goals') patch.goals = value;
        else if (fieldStep === 'diet') patch.diet = value;

        set(patch);
      } else if (tc.name === 'advance_step') {
        next();
      } else if (tc.name === 'go_back') {
        back();
      }
    },
    [set, next, back],
  );

  const voice = useOnboardingVoice(handleToolCall);

  // Connect voice when entering step 2 (age), disconnect on unmount
  const voiceStartedRef = useRef(false);
  useEffect(() => {
    if (stepIdx >= 1 && !voiceStartedRef.current) {
      voiceStartedRef.current = true;
      voice.start();
    }
  }, [stepIdx, voice]);

  useEffect(() => {
    return () => {
      voice.stop();
    };
  }, [voice]);
```

- [ ] **Step 3: Add VoiceFab to the UI**

Add a voice status indicator above the Continue button (inside the `SafeAreaView` at the bottom). This shows the agent state when voice is active:

```typescript
            {/* Voice indicator — visible from step 2 onward */}
            {stepIdx >= 1 && voice.isActive && (
              <View className="items-center mb-3">
                <Text tone="dim" className="text-xs font-mono-regular">
                  {voice.agentState === 'listening' ? 'Listening...' :
                   voice.agentState === 'thinking' ? 'Processing...' :
                   voice.agentState === 'speaking' ? 'Maya is speaking' : ''}
                </Text>
              </View>
            )}
```

Add this JSX right before the `<SafeAreaView edges={['bottom']}` block.

- [ ] **Step 4: Fix dependency ordering**

The `handleToolCall` callback depends on `next` and `back`, which need to be defined before `handleToolCall`. The existing `next` and `back` functions are already declared with `useCallback` above the profile state, so this ordering works. Just make sure `handleToolCall` is declared after `next` and `back`.

- [ ] **Step 5: Commit**

```bash
git add maya-ppa/src/app/\(auth\)/onboarding.tsx
git commit -m "feat: wire voice agent into onboarding screen with tool call dispatch"
```

---

## Task 11: Install `@mykin-ai/expo-audio-stream` and wire real-time audio I/O

**Files:**
- Modify: `maya-ppa/package.json` (install dependency)
- Modify: `maya-ppa/src/voice/useOnboardingVoice.ts` (wire real audio)

- [ ] **Step 1: Install the package**

```bash
cd maya-ppa && bun add @mykin-ai/expo-audio-stream
```

This is a native module — requires a dev client build (not Expo Go). The project already uses dev clients.

- [ ] **Step 2: Update useOnboardingVoice.ts with real audio streaming**

Replace the entire `maya-ppa/src/voice/useOnboardingVoice.ts` with real audio I/O:

```typescript
import { useCallback, useEffect, useRef, useState } from 'react';
import { ExpoPlayAudioStream } from '@mykin-ai/expo-audio-stream';
import {
  type AgentState,
  type OnboardingToolCall,
  type VoiceMessage,
  connectOnboardingVoiceWS,
} from './ws';
import { requestMicPermission } from './audio';

type OnToolCall = (toolCall: OnboardingToolCall) => void;

export function useOnboardingVoice(onToolCall: OnToolCall) {
  const [isActive, setIsActive] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [agentState, setAgentState] = useState<AgentState>('idle');
  const [isMuted, setIsMuted] = useState(false);
  const wsRef = useRef<ReturnType<typeof connectOnboardingVoiceWS> | null>(null);
  const subscriptionRef = useRef<{ remove: () => void } | null>(null);
  const onToolCallRef = useRef(onToolCall);
  onToolCallRef.current = onToolCall;
  const isMutedRef = useRef(false);

  const start = useCallback(async () => {
    const granted = await requestMicPermission();
    if (!granted) return;

    setIsActive(true);
    setAgentState('listening');

    try {
      // Configure playback for voice processing (echo cancellation)
      await ExpoPlayAudioStream.setSoundConfig({
        sampleRate: 16000,
      });

      const ws = connectOnboardingVoiceWS({
        onAudio: async (pcmBase64: string) => {
          if (isMutedRef.current) return;
          try {
            await ExpoPlayAudioStream.playAudio(pcmBase64);
          } catch {
            // playback errors are non-fatal
          }
        },
        onStateChange: (state: AgentState) => {
          setAgentState(state);
        },
        onToolCall: (toolCall: OnboardingToolCall) => {
          onToolCallRef.current(toolCall);
        },
        onClose: () => {
          setIsConnected(false);
          setIsActive(false);
          setAgentState('idle');
        },
        onError: () => {
          setIsConnected(false);
          setIsActive(false);
          setAgentState('idle');
        },
      });
      wsRef.current = ws;
      setIsConnected(true);

      // Start microphone streaming
      const { subscription } = await ExpoPlayAudioStream.startRecording({
        sampleRate: 16000,
        channels: 1,
        encoding: 'pcm_16bit',
        interval: 250,
        onAudioStream: (event: { data: string }) => {
          if (isMutedRef.current) return;
          ws.send({ type: 'audio', data: event.data });
        },
      });
      subscriptionRef.current = subscription;
    } catch {
      setIsActive(false);
      setAgentState('idle');
    }
  }, []);

  const stop = useCallback(async () => {
    subscriptionRef.current?.remove();
    subscriptionRef.current = null;
    try {
      await ExpoPlayAudioStream.stopRecording();
    } catch {
      // ignore if not recording
    }
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
    setIsActive(false);
    setAgentState('idle');
  }, []);

  const send = useCallback((msg: VoiceMessage) => {
    wsRef.current?.send(msg);
  }, []);

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      isMutedRef.current = !prev;
      return !prev;
    });
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      subscriptionRef.current?.remove();
      wsRef.current?.close();
    };
  }, []);

  return { isActive, isConnected, agentState, isMuted, start, stop, send, toggleMute };
}
```

- [ ] **Step 3: Commit**

```bash
git add maya-ppa/package.json maya-ppa/bun.lock maya-ppa/src/voice/useOnboardingVoice.ts
git commit -m "feat: wire real-time audio I/O with @mykin-ai/expo-audio-stream"
```

---

## Task 12: Create ScreenBorderGlow component

**Files:**
- Create: `maya-ppa/src/components/ds/ScreenBorderGlow.tsx`

- [ ] **Step 1: Create the Skia border glow component**

Create `maya-ppa/src/components/ds/ScreenBorderGlow.tsx`:

```tsx
import { useEffect } from 'react';
import { Dimensions, StyleSheet } from 'react-native';
import {
  Canvas,
  RoundedRect,
  SweepGradient,
  Blur,
  Group,
  vec,
} from '@shopify/react-native-skia';
import {
  useSharedValue,
  useDerivedValue,
  withRepeat,
  withTiming,
  withSequence,
  Easing,
} from 'react-native-reanimated';
import { useColors } from '@/components/ds/tokens';

const { width: SCREEN_W, height: SCREEN_H } = Dimensions.get('window');

type AgentState = 'idle' | 'listening' | 'thinking' | 'speaking';

const BORDER_RADIUS = 44;
const INNER_INSET = 6;

const STATE_CONFIG = {
  idle: { speed: 8000, blur: 15, arc: 0.15, opacity: 0.4 },
  listening: { speed: 6000, blur: 20, arc: 0.2, opacity: 0.6 },
  thinking: { speed: 3000, blur: 25, arc: 0.3, opacity: 0.8 },
  speaking: { speed: 4000, blur: 30, arc: 0.25, opacity: 1.0 },
};

export function ScreenBorderGlow({ state }: { state: AgentState }) {
  const colors = useColors();
  const config = STATE_CONFIG[state];

  const primaryColor = colors.primary[500];

  const rotation = useSharedValue(0);
  const pulsePhase = useSharedValue(0);
  const opacity = useSharedValue(config.opacity);

  const cx = SCREEN_W / 2;
  const cy = SCREEN_H / 2;
  const center = vec(cx, cy);

  useEffect(() => {
    rotation.value = 0;
    rotation.value = withRepeat(
      withTiming(2, { duration: config.speed, easing: Easing.linear }),
      -1,
      false,
    );
  }, [config.speed, rotation]);

  useEffect(() => {
    if (state === 'thinking') {
      pulsePhase.value = withRepeat(
        withSequence(
          withTiming(1, { duration: 1200, easing: Easing.inOut(Easing.ease) }),
          withTiming(0, { duration: 1200, easing: Easing.inOut(Easing.ease) }),
        ),
        -1,
        false,
      );
    } else {
      pulsePhase.value = withTiming(0, { duration: 300 });
    }
  }, [state, pulsePhase]);

  useEffect(() => {
    opacity.value = withTiming(config.opacity, { duration: 500 });
  }, [config.opacity, opacity]);

  const animatedRotation = useDerivedValue(() => [
    { rotate: Math.PI * rotation.value },
  ]);

  const animatedBlur = useDerivedValue(() => {
    const pulse = state === 'thinking' ? pulsePhase.value * 10 : 0;
    return config.blur + pulse;
  });

  const glowWithAlpha = `${primaryColor}AA`;
  const transparent = `${primaryColor}00`;
  const sweepColors = [transparent, glowWithAlpha, glowWithAlpha, transparent];

  const bgColor = colors.surface.base;

  return (
    <Canvas style={StyleSheet.absoluteFill} pointerEvents="none">
      {/* Blurred glow halo */}
      <Group>
        <RoundedRect
          x={0}
          y={0}
          width={SCREEN_W}
          height={SCREEN_H}
          r={BORDER_RADIUS}
        >
          <SweepGradient
            c={center}
            colors={sweepColors}
            transform={animatedRotation}
          />
        </RoundedRect>
        <Blur blur={animatedBlur} />
      </Group>

      {/* Sharp gradient border */}
      <RoundedRect
        x={0}
        y={0}
        width={SCREEN_W}
        height={SCREEN_H}
        r={BORDER_RADIUS}
        style="stroke"
        strokeWidth={2}
      >
        <SweepGradient
          c={center}
          colors={sweepColors}
          transform={animatedRotation}
        />
      </RoundedRect>

      {/* Inner mask to clear center */}
      <RoundedRect
        x={INNER_INSET}
        y={INNER_INSET}
        width={SCREEN_W - INNER_INSET * 2}
        height={SCREEN_H - INNER_INSET * 2}
        r={BORDER_RADIUS - 2}
        color={bgColor}
      />
    </Canvas>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add maya-ppa/src/components/ds/ScreenBorderGlow.tsx
git commit -m "feat: add ScreenBorderGlow Skia component for voice agent state"
```

---

## Task 13: Add step sync (UI typing → agent) and handle inbound step_sync on backend

**Files:**
- Modify: `maya-ppa/src/voice/ws.ts` (add step_sync message type)
- Modify: `maya-ppa/src/app/(auth)/onboarding.tsx` (send step_sync when user types)
- Modify: `server/src/live150/voice/onboarding_session.py` (handle step_sync from client)

- [ ] **Step 1: Add step_sync message type to ws.ts**

In `maya-ppa/src/voice/ws.ts`, update the `VoiceMessage` type:

```typescript
export type VoiceMessage =
  | { type: 'audio'; data: string }
  | { type: 'state'; state: AgentState }
  | { type: 'step_sync'; step: OnboardingStep; current_values: Record<string, unknown> };
```

- [ ] **Step 2: Handle step_sync in OnboardingVoiceSession**

In `server/src/live150/voice/onboarding_session.py`, update `_inbound_loop` to handle step_sync messages by sending context to Gemini:

```python
    async def _inbound_loop(self, websocket: Any) -> None:
        try:
            async for raw in websocket.iter_text():
                msg = json.loads(raw)
                if msg.get("type") == "audio":
                    pcm_bytes = base64.b64decode(msg["data"])
                    await self._gemini_session.send_realtime_input(
                        audio=types.Blob(
                            data=pcm_bytes, mime_type="audio/pcm;rate=16000",
                        ),
                    )
                elif msg.get("type") == "step_sync":
                    step = msg.get("step", "")
                    values = msg.get("current_values", {})
                    context = f"[System: User manually set values via keyboard. Current step: {step}. Filled values: {json.dumps(values)}. Do not re-ask for fields already filled.]"
                    await self._gemini_session.send_client_content(
                        turns=types.Content(
                            role="user",
                            parts=[types.Part(text=context)],
                        ),
                        turn_complete=True,
                    )
        except Exception as e:
            logger.info("onboarding_inbound_closed", extra={"reason": str(e)})
```

- [ ] **Step 3: Send step_sync from onboarding.tsx when user types a value**

In `onboarding.tsx`, update the `set` callback to also send a step_sync when the voice session is active:

```typescript
  const set = useCallback((patch: Record<string, unknown>) => {
    setProfile((p) => {
      const updated = { ...p, ...patch };
      // Sync to voice agent when user types manually
      if (voice.isConnected) {
        voice.send({
          type: 'step_sync',
          step: step.id as OnboardingStep,
          current_values: updated,
        });
      }
      return updated;
    });
  }, [voice, step.id]);
```

Note: The `set` callback needs to be defined after `voice` is initialized (after `useOnboardingVoice`). This requires reordering — move `set` below the voice hook.

- [ ] **Step 4: Commit**

```bash
git add maya-ppa/src/voice/ws.ts maya-ppa/src/app/\(auth\)/onboarding.tsx server/src/live150/voice/onboarding_session.py
git commit -m "feat: add step sync from mobile UI to voice agent on manual input"
```

---

## Task 14: Wire ScreenBorderGlow and mute button into onboarding screen

**Files:**
- Modify: `maya-ppa/src/app/(auth)/onboarding.tsx`

- [ ] **Step 1: Add ScreenBorderGlow import**

```typescript
import { ScreenBorderGlow } from '@/components/ds/ScreenBorderGlow';
```

- [ ] **Step 2: Add ScreenBorderGlow overlay when voice is active (step 2+)**

Place the `ScreenBorderGlow` as the last child inside the root `<View className="flex-1 bg-base">`, after `SafeAreaView`:

```typescript
      {stepIdx >= 1 && voice.isActive && (
        <ScreenBorderGlow state={voice.agentState} />
      )}
```

- [ ] **Step 3: Add mute button to header**

In the header row (the `flex-row items-center justify-between px-6 mt-1` View), add a mute button to the right of the step counter, before the reset/trash button:

```typescript
              {stepIdx >= 1 && voice.isActive && (
                <Pressable
                  onPress={voice.toggleMute}
                  className="w-10 h-10 border-continuous rounded-sm bg-tint border border-hairline items-center justify-center"
                >
                  <Ionicons
                    name={voice.isMuted ? 'volume-mute' : 'volume-high'}
                    size={16}
                    color={voice.isMuted ? colors.text.dim : colors.primary[500]}
                  />
                </Pressable>
              )}
```

- [ ] **Step 4: Remove the old VoiceFab text indicator from Task 10**

If the text-based voice indicator was added in Task 10, remove it. The ScreenBorderGlow replaces it.

- [ ] **Step 5: Commit**

```bash
git add maya-ppa/src/app/\(auth\)/onboarding.tsx
git commit -m "feat: add screen border glow and mute button to onboarding"
```
