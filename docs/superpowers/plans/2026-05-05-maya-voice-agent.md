# Maya Voice Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real-time voice conversation to Maya via WebSocket, proxying audio through the maya-pa server to Gemini Live API, with 8 voice tools sharing pgvector memory with the text agent.

**Architecture:** Mobile app connects via WebSocket to maya-pa FastAPI server. Server opens a Gemini Live session, relays PCM audio bidirectionally, and handles all tool calls server-side. Memory is shared with the existing text agent through the same `MemoryService` singleton.

**Tech Stack:** Python FastAPI (WebSocket), google-genai Live API, pgvector, expo-audio (React Native), Expo Router

**Repos:**
- Server: `/Users/anurag/Documents/git/liv150/maya-pa/` (branch: `feat/voice-agent`)
- Mobile: `/Users/anurag/Documents/git/liv150/maya-ppa/` (branch: `liv150-design`)
- Backend API: `/Users/anurag/Documents/git/liv150/liv150-api/` (branch: `main`)

---

## File Structure

### Server (maya-pa) — New Files

| File | Responsibility |
|------|---------------|
| `server/src/live150/voice/context.py` | Build system prompt (SOUL.md + voice addendum) and user context string |
| `server/src/live150/voice/tools.py` | 8 tool declarations (Gemini function_declarations format) + handler dispatch |
| `server/src/live150/voice/session.py` | `VoiceSession` class: manage Gemini Live connection, relay loop, tool execution |
| `server/src/live150/api/voice.py` | FastAPI router: WebSocket endpoint + prewarm POST |
| `tests/unit/test_voice_context.py` | Tests for prompt builder and context formatting |
| `tests/unit/test_voice_tools.py` | Tests for tool declarations and handler dispatch |

### Server (maya-pa) — Modified Files

| File | Change |
|------|--------|
| `server/src/live150/main.py:122-131` | Add voice router import and registration |
| `server/src/live150/config.py:4-39` | Add `liv150_api_base` setting for tool HTTP calls |

### Mobile (maya-ppa) — New Files

| File | Responsibility |
|------|---------------|
| `src/voice/ws.ts` | WebSocket client: connect, send audio, receive audio/state messages |
| `src/voice/audio.ts` | expo-audio config: PCM recording with AEC, playback queue |
| `src/voice/VoiceProvider.tsx` | Root-level React context: session state, start/end session |
| `src/voice/useVoice.ts` | Hook: `startSession`, `endSession`, `isActive`, `agentState` |
| `src/components/ds/VoiceFab.tsx` | Floating Maya orb button, visible on all screens |
| `src/components/ds/VoiceOverlay.tsx` | Full-screen voice session UI with orb animation |

### Mobile (maya-ppa) — Modified Files

| File | Change |
|------|--------|
| `src/app/_layout.tsx` | Add `VoiceProvider` + `VoiceFab` to root layout |

---

## Task 1: Voice Context Builder

Build the system prompt and user context string that gets injected into the Gemini Live session on connect.

**Files:**
- Create: `server/src/live150/voice/context.py`
- Create: `server/tests/unit/test_voice_context.py`

- [ ] **Step 1: Write tests for the context builder**

Create `server/tests/unit/test_voice_context.py`:

```python
import pytest

from live150.voice.context import build_system_prompt, build_user_context


def test_build_system_prompt_contains_soul():
    prompt = build_system_prompt()
    assert "Maya" in prompt
    assert "longevity companion" in prompt


def test_build_system_prompt_contains_voice_addendum():
    prompt = build_system_prompt()
    assert "1-3 sentences" in prompt
    assert "Never use markdown" in prompt


def test_build_user_context_basic():
    ctx = build_user_context(
        display_name="Alex",
        age=34,
        goals=["reduce_inflammation", "improve_sleep"],
        conditions=["pre_diabetes"],
        timezone_name="America/New_York",
        memories=["User prefers morning workouts", "User doesn't eat pork"],
    )
    assert "Alex" in ctx
    assert "34" in ctx
    assert "reduce_inflammation" in ctx
    assert "pre_diabetes" in ctx
    assert "America/New_York" in ctx
    assert "morning workouts" in ctx


def test_build_user_context_empty_memories():
    ctx = build_user_context(
        display_name="Sam",
        age=28,
        goals=[],
        conditions=[],
        timezone_name="UTC",
        memories=[],
    )
    assert "Sam" in ctx
    assert "No prior context" in ctx
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/anurag/Documents/git/liv150/maya-pa/server && PYTHONPATH=src .venv/bin/pytest tests/unit/test_voice_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'live150.voice'`

- [ ] **Step 3: Implement the context builder**

Create `server/src/live150/voice/__init__.py` (empty file).

Create `server/src/live150/voice/context.py`:

```python
"""Build system prompt and user context for voice sessions."""

from datetime import datetime, timezone
from pathlib import Path

_SOUL_PATH = Path(__file__).resolve().parent.parent / "agent" / "SOUL.md"

_VOICE_ADDENDUM = """
You are speaking aloud in a real-time voice conversation. Follow these voice-specific rules:

- Keep responses to 1-3 sentences. Brevity is critical — the user is listening, not reading.
- Never use markdown, bullets, numbered lists, or formatting. Speak naturally.
- Never spell out URLs, code, or structured data. Say "I'll save that" or "check your app for details."
- Use natural speech fillers sparingly ("let me check", "so") — don't be robotic.
- When you use a tool, don't narrate it. Just pause briefly and continue with the answer.
- If the answer would be long (meal plans, multi-day summaries), give a 1-sentence summary and say "I've put the details in your app" — then save a note via memory.
- Match the user's energy. Short question → short answer. Excited → match warmth.
"""


def build_system_prompt() -> str:
    soul = _SOUL_PATH.read_text()
    return f"{soul}\n\n---\n\n## Voice Mode\n{_VOICE_ADDENDUM}"


def build_user_context(
    display_name: str,
    age: int | None,
    goals: list[str],
    conditions: list[str],
    timezone_name: str,
    memories: list[str],
) -> str:
    now = datetime.now(timezone.utc)
    parts = [
        f"User: {display_name}",
    ]
    if age is not None:
        parts.append(f"Age: {age}")
    if goals:
        parts.append(f"Goals: {', '.join(goals)}")
    if conditions:
        parts.append(f"Health conditions: {', '.join(conditions)}")
    parts.append(f"Timezone: {timezone_name}")
    parts.append(f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M')}")

    if memories:
        parts.append("\nRecent context:")
        for mem in memories:
            parts.append(f"- {mem}")
    else:
        parts.append("\nNo prior context available.")

    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/anurag/Documents/git/liv150/maya-pa/server && PYTHONPATH=src .venv/bin/pytest tests/unit/test_voice_context.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/anurag/Documents/git/liv150/maya-pa
git add server/src/live150/voice/__init__.py server/src/live150/voice/context.py server/tests/unit/test_voice_context.py
git commit -m "feat(voice): add system prompt and user context builder"
```

---

## Task 2: Voice Tool Declarations and Handlers

Define the 8 Gemini Live function declarations and a dispatch function that routes tool calls to handlers. Tool handlers reuse the existing `MemoryService` and call liv150-api for health/reminder tools.

**Files:**
- Create: `server/src/live150/voice/tools.py`
- Create: `server/tests/unit/test_voice_tools.py`

**Reference:** Existing tool patterns in `server/src/live150/tools/memory_tools.py` and `server/src/live150/tools/nams_tools.py`. The voice tools adapt these for the Gemini Live API (no `tool_context` — user_phone and db passed directly).

- [ ] **Step 1: Write tests for tool declarations and dispatch**

Create `server/tests/unit/test_voice_tools.py`:

```python
import pytest

from live150.voice.tools import TOOL_DECLARATIONS, TOOL_HANDLERS, get_tool_config


def test_tool_declarations_count():
    assert len(TOOL_DECLARATIONS) == 8


def test_each_declaration_has_required_fields():
    for decl in TOOL_DECLARATIONS:
        assert "name" in decl, f"Missing 'name' in declaration"
        assert "description" in decl, f"Missing 'description' in {decl.get('name')}"
        assert "parameters" in decl, f"Missing 'parameters' in {decl.get('name')}"


def test_handler_exists_for_each_declaration():
    for decl in TOOL_DECLARATIONS:
        name = decl["name"]
        assert name in TOOL_HANDLERS, f"No handler for tool '{name}'"


def test_get_tool_config_format():
    config = get_tool_config()
    assert isinstance(config, list)
    assert len(config) == 1
    assert "function_declarations" in config[0]
    assert len(config[0]["function_declarations"]) == 8


def test_tool_names():
    names = {d["name"] for d in TOOL_DECLARATIONS}
    expected = {
        "search_memory", "save_memory", "log_nams",
        "get_progress_by_date", "get_health_goals",
        "create_reminder", "list_reminders", "cancel_reminder",
    }
    assert names == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/anurag/Documents/git/liv150/maya-pa/server && PYTHONPATH=src .venv/bin/pytest tests/unit/test_voice_tools.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement voice tools**

Create `server/src/live150/voice/tools.py`:

```python
"""Voice tool declarations and handlers for Gemini Live API.

8 tools registered directly with Gemini Live (not via ADK).
Memory tools use the shared MemoryService. Health/reminder tools
call liv150-api via httpx.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from live150.db.session import async_session_factory
from live150.memory.service import MemoryService

logger = logging.getLogger(__name__)

_memory_service = MemoryService()

TOOL_DECLARATIONS: list[dict] = [
    {
        "name": "search_memory",
        "description": (
            "Search the user's long-term memory for relevant information. "
            "Use this to recall facts, preferences, and past events."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."},
                "limit": {"type": "integer", "description": "Max results (default 5)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Save a fact, preference, event, or note to the user's long-term memory. "
            "Use when the user shares something worth remembering across sessions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["fact", "preference", "event", "note"],
                    "description": "Type of memory.",
                },
                "content": {"type": "string", "description": "The information to remember."},
            },
            "required": ["kind", "content"],
        },
    },
    {
        "name": "log_nams",
        "description": (
            "Log a Nutrition, Activity, Mindfulness, or Sleep event. "
            "Call immediately when the user mentions any health activity."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["activity", "nutrition", "mindfulness", "sleep"],
                    "description": "Event category.",
                },
                "logged_at": {"type": "string", "description": "ISO-8601 datetime. Defaults to now."},
                "activity_type": {"type": "string", "description": "e.g. run, walk, cycle, strength, yoga."},
                "duration_minutes": {"type": "integer", "description": "Duration in minutes."},
                "distance_km": {"type": "number", "description": "Distance in km (activity)."},
                "intensity": {"type": "string", "enum": ["low", "medium", "high"]},
                "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack", "drink"]},
                "items": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"name": {"type": "string"}}},
                    "description": "Food items.",
                },
                "water_ml": {"type": "integer", "description": "Water consumed in ml."},
                "calories": {"type": "integer", "description": "Estimated calories."},
                "duration_hours": {"type": "number", "description": "Sleep duration in hours."},
                "bedtime": {"type": "string", "description": "Bedtime as HH:MM."},
                "wake_time": {"type": "string", "description": "Wake time as HH:MM."},
                "quality": {"type": "string", "enum": ["poor", "fair", "good"]},
                "mindfulness_type": {"type": "string", "enum": ["meditation", "breathing", "journaling", "other"]},
            },
            "required": ["category"],
        },
    },
    {
        "name": "get_progress_by_date",
        "description": "Get the user's health progress for a specific date.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD. Defaults to today."},
            },
            "required": [],
        },
    },
    {
        "name": "get_health_goals",
        "description": "Get the user's active health goals.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "create_reminder",
        "description": "Schedule a future notification for the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short reminder title."},
                "when": {"type": "string", "description": "ISO-8601 datetime for when to remind."},
                "prompt": {"type": "string", "description": "The message to show in the notification."},
            },
            "required": ["title", "when", "prompt"],
        },
    },
    {
        "name": "list_reminders",
        "description": "List the user's active reminders.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "cancel_reminder",
        "description": "Cancel a reminder by its ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "reminder_id": {"type": "string", "description": "The reminder ID to cancel."},
            },
            "required": ["reminder_id"],
        },
    },
]

TOOL_HANDLERS: dict[str, Any] = {}


def get_tool_config() -> list[dict]:
    return [{"function_declarations": TOOL_DECLARATIONS}]


# --- Handler implementations ---

async def _handle_search_memory(args: dict, user_phone: str, db: AsyncSession) -> dict:
    query = args.get("query", "")
    limit = args.get("limit", 5)
    try:
        hits = await _memory_service.recall(db=db, user_id=user_phone, query=query, limit=limit)
    except Exception as e:
        logger.warning("voice_memory_search_failed", extra={"error": str(e)})
        return {"results": [], "message": "Memory search unavailable."}
    if not hits:
        return {"results": [], "message": "No matching memories found."}
    return {
        "results": [
            {"kind": h.kind, "content": h.content, "score": round(h.score, 3)}
            for h in hits
        ]
    }


async def _handle_save_memory(args: dict, user_phone: str, db: AsyncSession) -> dict:
    kind = args.get("kind", "fact")
    content = args.get("content", "")
    if kind not in ("fact", "preference", "event", "note"):
        return {"saved": False, "message": f"Invalid kind '{kind}'."}
    try:
        memory_id = await _memory_service.save(
            db=db, user_id=user_phone, kind=kind, content=content,
            source="voice_agent",
        )
    except Exception as e:
        logger.warning("voice_memory_save_failed", extra={"error": str(e)})
        return {"saved": False, "message": "Memory save failed."}
    return {"saved": True, "memory_id": str(memory_id)}


async def _handle_log_nams(args: dict, user_phone: str, db: AsyncSession) -> dict:
    category = args.get("category")
    if category not in ("activity", "nutrition", "mindfulness", "sleep"):
        return {"logged": False, "message": f"Invalid category '{category}'."}

    logged_at = args.get("logged_at") or datetime.now(timezone.utc).isoformat()

    summary_parts = [f"User logged {category}"]
    if args.get("activity_type"):
        summary_parts = [f"User did {args['activity_type']}"]
    if args.get("duration_minutes"):
        summary_parts.append(f"for {args['duration_minutes']} minutes")
    if args.get("meal_type"):
        summary_parts = [f"User logged {args['meal_type']}"]
    if args.get("items"):
        names = ", ".join(i.get("name", "") for i in args["items"] if i.get("name"))
        if names:
            summary_parts.append(f"— {names}")
    if args.get("duration_hours"):
        summary_parts = [f"User slept {args['duration_hours']}h"]

    memory_content = " ".join(summary_parts) + f" on {logged_at[:10]}"

    try:
        await _memory_service.save(
            db=db, user_id=user_phone, kind="event", content=memory_content,
            source="voice_agent", metadata={"category": category, "logged_at": logged_at},
        )
    except Exception as e:
        logger.warning("voice_nams_save_failed", extra={"error": str(e)})
        return {"logged": False, "message": "Could not save event."}

    return {"logged": True, "category": category, "content": memory_content}


async def _handle_liv150_api(
    method: str, path: str, args: dict, api_base: str, access_token: str,
) -> dict:
    async with httpx.AsyncClient(base_url=api_base, timeout=10.0) as client:
        headers = {"Authorization": f"Bearer {access_token}"}
        if method == "GET":
            r = await client.get(path, params=args, headers=headers)
        elif method == "POST":
            r = await client.post(path, json=args, headers=headers)
        elif method == "DELETE":
            r = await client.delete(path, params=args, headers=headers)
        else:
            return {"error": f"Unsupported method {method}"}
        r.raise_for_status()
        return r.json()


async def _handle_get_progress(args: dict, user_phone: str, db: AsyncSession, **ctx) -> dict:
    date = args.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    try:
        return await _handle_liv150_api(
            "GET", f"/api/v1/health/progress", {"date": date},
            ctx["api_base"], ctx["access_token"],
        )
    except Exception as e:
        logger.warning("voice_progress_failed", extra={"error": str(e)})
        return {"error": True, "message": "Could not fetch progress data."}


async def _handle_get_goals(args: dict, user_phone: str, db: AsyncSession, **ctx) -> dict:
    try:
        return await _handle_liv150_api(
            "GET", "/api/v1/users/me", {},
            ctx["api_base"], ctx["access_token"],
        )
    except Exception as e:
        logger.warning("voice_goals_failed", extra={"error": str(e)})
        return {"error": True, "message": "Could not fetch goals."}


async def _handle_create_reminder(args: dict, user_phone: str, db: AsyncSession, **ctx) -> dict:
    try:
        return await _handle_liv150_api(
            "POST", "/api/v1/reminders", args,
            ctx["api_base"], ctx["access_token"],
        )
    except Exception as e:
        logger.warning("voice_create_reminder_failed", extra={"error": str(e)})
        return {"error": True, "message": "Could not create reminder."}


async def _handle_list_reminders(args: dict, user_phone: str, db: AsyncSession, **ctx) -> dict:
    try:
        return await _handle_liv150_api(
            "GET", "/api/v1/reminders", {},
            ctx["api_base"], ctx["access_token"],
        )
    except Exception as e:
        logger.warning("voice_list_reminders_failed", extra={"error": str(e)})
        return {"error": True, "message": "Could not list reminders."}


async def _handle_cancel_reminder(args: dict, user_phone: str, db: AsyncSession, **ctx) -> dict:
    reminder_id = args.get("reminder_id", "")
    try:
        return await _handle_liv150_api(
            "DELETE", f"/api/v1/reminders/{reminder_id}", {},
            ctx["api_base"], ctx["access_token"],
        )
    except Exception as e:
        logger.warning("voice_cancel_reminder_failed", extra={"error": str(e)})
        return {"error": True, "message": "Could not cancel reminder."}


# Register handlers
TOOL_HANDLERS["search_memory"] = _handle_search_memory
TOOL_HANDLERS["save_memory"] = _handle_save_memory
TOOL_HANDLERS["log_nams"] = _handle_log_nams
TOOL_HANDLERS["get_progress_by_date"] = _handle_get_progress
TOOL_HANDLERS["get_health_goals"] = _handle_get_goals
TOOL_HANDLERS["create_reminder"] = _handle_create_reminder
TOOL_HANDLERS["list_reminders"] = _handle_list_reminders
TOOL_HANDLERS["cancel_reminder"] = _handle_cancel_reminder
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/anurag/Documents/git/liv150/maya-pa/server && PYTHONPATH=src .venv/bin/pytest tests/unit/test_voice_tools.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/anurag/Documents/git/liv150/maya-pa
git add server/src/live150/voice/tools.py server/tests/unit/test_voice_tools.py
git commit -m "feat(voice): add 8 tool declarations and handler dispatch"
```

---

## Task 3: Voice Session Manager

The core class that manages a Gemini Live session: connecting, relaying audio, dispatching tool calls, and cleaning up.

**Files:**
- Create: `server/src/live150/voice/session.py`
- Create: `server/tests/unit/test_voice_session.py`

**Reference:** `server/src/live150/agent/genai_client.py` for the Gemini client, `google.genai.types` for Live API types.

- [ ] **Step 1: Write tests for VoiceSession**

Create `server/tests/unit/test_voice_session.py`:

```python
import pytest

from live150.voice.session import VoiceSession


def test_voice_session_init():
    session = VoiceSession(
        user_phone="+1234567890",
        access_token="test-token",
        api_base="http://localhost:8001",
    )
    assert session.user_phone == "+1234567890"
    assert session.access_token == "test-token"
    assert session.is_connected is False


def test_voice_session_state_default():
    session = VoiceSession(
        user_phone="+1234567890",
        access_token="test-token",
        api_base="http://localhost:8001",
    )
    assert session.state == "idle"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/anurag/Documents/git/liv150/maya-pa/server && PYTHONPATH=src .venv/bin/pytest tests/unit/test_voice_session.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement VoiceSession**

Create `server/src/live150/voice/session.py`:

```python
"""VoiceSession — manages a single Gemini Live session for one user.

Handles:
- Connecting to Gemini Live API with system prompt + tools
- Injecting user context as initial message
- Relaying audio between a WebSocket client and Gemini
- Dispatching tool calls to voice tool handlers
- State tracking (idle, listening, thinking, speaking)
"""

import asyncio
import base64
import json
import logging
from typing import Any, Literal

from google.genai import types

from live150.agent.genai_client import get_genai_client
from live150.db.session import async_session_factory
from live150.voice.context import build_system_prompt, build_user_context
from live150.voice.tools import TOOL_HANDLERS, get_tool_config

logger = logging.getLogger(__name__)

VOICE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

State = Literal["idle", "listening", "thinking", "speaking"]


class VoiceSession:
    def __init__(
        self,
        user_phone: str,
        access_token: str,
        api_base: str,
    ):
        self.user_phone = user_phone
        self.access_token = access_token
        self.api_base = api_base
        self.state: State = "idle"
        self.is_connected: bool = False
        self._gemini_session: Any = None
        self._tasks: list[asyncio.Task] = []

    async def connect(
        self,
        display_name: str,
        age: int | None,
        goals: list[str],
        conditions: list[str],
        timezone_name: str,
        memories: list[str],
    ) -> None:
        system_prompt = build_system_prompt()
        user_context = build_user_context(
            display_name=display_name,
            age=age,
            goals=goals,
            conditions=conditions,
            timezone_name=timezone_name,
            memories=memories,
        )

        client = get_genai_client()
        config = types.LiveConnectConfig(
            system_instruction=system_prompt,
            tools=get_tool_config(),
            response_modalities=["AUDIO"],
            temperature=1.0,
            enable_affective_dialog=True,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede"),
                ),
            ),
        )

        self._gemini_ctx = client.aio.live.connect(model=VOICE_MODEL, config=config)
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
        inbound = asyncio.create_task(self._inbound_loop(websocket), name="voice_inbound")
        outbound = asyncio.create_task(self._outbound_loop(websocket), name="voice_outbound")
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
                        audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000"),
                    )
        except Exception as e:
            logger.info("voice_inbound_closed", extra={"reason": str(e)})

    async def _outbound_loop(self, websocket: Any) -> None:
        try:
            async for msg in self._gemini_session.receive():
                if msg.server_content and msg.server_content.parts:
                    for part in msg.server_content.parts:
                        if part.inline_data and part.inline_data.data:
                            self.state = "speaking"
                            await websocket.send_json({
                                "type": "audio",
                                "data": base64.b64encode(part.inline_data.data).decode(),
                            })

                    if msg.server_content.turn_complete:
                        self.state = "listening"
                        await websocket.send_json({"type": "state", "state": "listening"})

                if msg.tool_call and msg.tool_call.function_calls:
                    self.state = "thinking"
                    await websocket.send_json({"type": "state", "state": "thinking"})
                    responses = await self._execute_tools(msg.tool_call.function_calls)
                    await self._gemini_session.send_tool_response(function_responses=responses)

        except Exception as e:
            logger.info("voice_outbound_closed", extra={"reason": str(e)})

    async def _execute_tools(self, function_calls: list) -> list:
        results = []
        async with async_session_factory() as db:
            for fc in function_calls:
                handler = TOOL_HANDLERS.get(fc.name)
                if not handler:
                    results.append(types.FunctionResponse(
                        name=fc.name, id=fc.id,
                        response={"error": f"Unknown tool: {fc.name}"},
                    ))
                    continue

                try:
                    result = await handler(
                        fc.args or {}, self.user_phone, db,
                        api_base=self.api_base, access_token=self.access_token,
                    )
                except Exception as e:
                    logger.warning("voice_tool_failed", extra={"tool": fc.name, "error": str(e)})
                    result = {"error": True, "message": str(e)}

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/anurag/Documents/git/liv150/maya-pa/server && PYTHONPATH=src .venv/bin/pytest tests/unit/test_voice_session.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/anurag/Documents/git/liv150/maya-pa
git add server/src/live150/voice/session.py server/tests/unit/test_voice_session.py
git commit -m "feat(voice): add VoiceSession with Gemini Live relay and tool dispatch"
```

---

## Task 4: Voice WebSocket Endpoint and Prewarm

The FastAPI router with the WebSocket endpoint and prewarm POST.

**Files:**
- Create: `server/src/live150/api/voice.py`
- Modify: `server/src/live150/main.py:122-131`
- Modify: `server/src/live150/config.py:4-39`

**Reference:** `server/src/live150/api/stream.py` for endpoint patterns, `server/src/live150/main.py` for router registration.

- [ ] **Step 1: Add `liv150_api_base` to config**

In `server/src/live150/config.py`, add after the `service_api_token` line:

```python
    # Liv150 API (new backend) — used by voice tools
    liv150_api_base: str = "http://localhost:8001"
```

- [ ] **Step 2: Implement the voice router**

Create `server/src/live150/api/voice.py`:

```python
"""Voice WebSocket endpoint and prewarm."""

import logging

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.responses import Response
from starlette.websockets import WebSocketState

from live150.config import settings
from live150.db.session import async_session_factory, engine
from live150.memory.service import MemoryService
from live150.voice.session import VoiceSession

logger = logging.getLogger(__name__)
router = APIRouter()

_memory_service = MemoryService()


def _decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.gate_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


async def _load_user_profile(access_token: str) -> dict | None:
    import httpx
    try:
        async with httpx.AsyncClient(
            base_url=settings.liv150_api_base, timeout=5.0,
        ) as client:
            r = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning("voice_profile_fetch_failed", extra={"error": str(e)})
        return None


@router.websocket("/ws")
async def voice_ws(websocket: WebSocket, token: str = ""):
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    claims = _decode_token(token)
    if not claims:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_phone = claims.get("sub", "")
    if not user_phone:
        await websocket.close(code=4001, reason="Invalid token: no sub")
        return

    await websocket.accept()
    logger.info("voice_ws_connected", extra={"user": user_phone})

    profile = await _load_user_profile(token)

    display_name = "there"
    age = None
    goals: list[str] = []
    conditions: list[str] = []
    timezone_name = "UTC"

    if profile:
        display_name = profile.get("display_name") or "there"
        if profile.get("date_of_birth"):
            from datetime import date
            try:
                dob = date.fromisoformat(profile["date_of_birth"])
                age = date.today().year - dob.year
            except (ValueError, TypeError):
                pass
        goals = profile.get("goals") or []
        conditions = profile.get("conditions") or []
        timezone_name = profile.get("timezone_name") or "UTC"

    memories: list[str] = []
    try:
        async with async_session_factory() as db:
            hits = await _memory_service.recall(
                db=db, user_id=user_phone, query="user profile preferences goals recent", limit=12,
            )
            memories = [h.content for h in hits]
    except Exception as e:
        logger.warning("voice_memory_load_failed", extra={"error": str(e)})

    session = VoiceSession(
        user_phone=user_phone,
        access_token=token,
        api_base=settings.liv150_api_base,
    )

    try:
        await session.connect(
            display_name=display_name,
            age=age,
            goals=goals,
            conditions=conditions,
            timezone_name=timezone_name,
            memories=memories,
        )

        await websocket.send_json({"type": "state", "state": "listening"})
        await session.relay(websocket)

    except WebSocketDisconnect:
        logger.info("voice_ws_disconnected", extra={"user": user_phone})
    except Exception as e:
        logger.error("voice_ws_error", extra={"user": user_phone, "error": str(e)})
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=1011, reason="Internal error")
    finally:
        await session.close()
        logger.info("voice_session_closed", extra={"user": user_phone})


@router.post("/prewarm", status_code=204)
async def prewarm():
    try:
        async with engine.connect() as conn:
            await conn.execute(conn.default_dialect.do_ping(conn))
    except Exception:
        pass
    return Response(status_code=204)
```

- [ ] **Step 3: Register the voice router in main.py**

In `server/src/live150/main.py`, add after line 121 (`from live150.api.documents import router as documents_router`):

```python
from live150.api.voice import router as voice_router  # noqa: E402
```

And after line 130 (`api_v1.include_router(documents_router, prefix="/documents")`), add:

```python
api_v1.include_router(voice_router, prefix="/voice")
```

- [ ] **Step 4: Test the endpoint starts**

Run: `cd /Users/anurag/Documents/git/liv150/maya-pa/server && PYTHONPATH=src .venv/bin/python -c "from live150.main import app; print('Router registered:', [r.path for r in app.routes if hasattr(r, 'path') and 'voice' in r.path])"`
Expected: Output includes `/api/v1/voice/ws` and `/api/v1/voice/prewarm`

- [ ] **Step 5: Commit**

```bash
cd /Users/anurag/Documents/git/liv150/maya-pa
git add server/src/live150/api/voice.py server/src/live150/config.py server/src/live150/main.py
git commit -m "feat(voice): add WebSocket endpoint, prewarm, and router registration"
```

---

## Task 5: Mobile WebSocket Client

The WebSocket client that connects to the voice endpoint, sends/receives JSON messages.

**Files:**
- Create: `maya-ppa/src/voice/ws.ts`

**Reference:** `maya-ppa/src/auth/client.ts` for auth patterns, `maya-ppa/.env` for `EXPO_PUBLIC_MAYA_BASE_URL`.

- [ ] **Step 1: Create the WebSocket client**

Create `maya-ppa/src/voice/ws.ts`:

```typescript
import { authStorage } from '@/auth/storage';

const BASE_URL = process.env.EXPO_PUBLIC_AUTH_BASE_URL ?? 'http://192.168.1.2:8001';

export type AgentState = 'idle' | 'listening' | 'thinking' | 'speaking';

export type VoiceMessage =
  | { type: 'audio'; data: string }
  | { type: 'state'; state: AgentState };

export type VoiceWSCallbacks = {
  onAudio: (pcmBase64: string) => void;
  onStateChange: (state: AgentState) => void;
  onClose: (code: number, reason: string) => void;
  onError: (error: Event) => void;
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
      const msg: VoiceMessage = JSON.parse(event.data);
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
```

- [ ] **Step 2: Commit**

```bash
cd /Users/anurag/Documents/git/liv150/maya-ppa
git add src/voice/ws.ts
git commit -m "feat(voice): add WebSocket client for voice endpoint"
```

---

## Task 6: Mobile Audio Pipeline

Audio recording (PCM 16kHz with AEC) and playback using `expo-audio`.

**Files:**
- Create: `maya-ppa/src/voice/audio.ts`

**Prerequisite:** Install expo-audio: `cd maya-ppa && bunx expo install expo-audio`

**Note:** `expo-audio` is the modern replacement for the deprecated `Audio` from `expo-av`. It provides `useAudioRecorder` and `useAudioPlayer` hooks, plus `RecordingOptions` for configuring sample rate, channels, and encoding. AEC is configured at the native audio session level.

- [ ] **Step 1: Install expo-audio**

Run: `cd /Users/anurag/Documents/git/liv150/maya-ppa && bunx expo install expo-audio`

- [ ] **Step 2: Create the audio module**

Create `maya-ppa/src/voice/audio.ts`:

```typescript
import { AudioModule, RecordingPresets, useAudioRecorder, useAudioPlayer } from 'expo-audio';
import { useCallback, useRef } from 'react';
import { Platform } from 'react-native';

export async function requestMicPermission(): Promise<boolean> {
  const status = await AudioModule.requestRecordingPermissionsAsync();
  return status.granted;
}

export async function configureAudioSession(): Promise<void> {
  if (Platform.OS === 'ios') {
    await AudioModule.setAudioModeAsync({
      playsInSilentMode: true,
      shouldRouteThroughEarpiece: false,
    });
  }
}

export const PCM_RECORDING_OPTIONS = {
  ...RecordingPresets.HIGH_QUALITY,
  extension: '.pcm',
  sampleRate: 16000,
  numberOfChannels: 1,
  bitRate: 256000,
  outputFormat: 'pcm',
};
```

**Important:** The exact `expo-audio` API for streaming PCM chunks in real-time depends on the version installed. The implementer should check `expo-audio` docs for:
1. How to get raw PCM data as the recording progresses (via `onAudioSampleReceived` callback or similar)
2. How to play raw PCM chunks received from WebSocket

If `expo-audio` doesn't support real-time PCM streaming natively, use `react-native-live-audio-stream` as a fallback for recording, and `expo-audio` for playback.

- [ ] **Step 3: Commit**

```bash
cd /Users/anurag/Documents/git/liv150/maya-ppa
git add src/voice/audio.ts
git commit -m "feat(voice): add audio module with PCM recording config and AEC"
```

---

## Task 7: Mobile VoiceProvider and useVoice Hook

Root-level React context that manages WebSocket connection, audio capture/playback, and session state. Exposes `useVoice()` hook.

**Files:**
- Create: `maya-ppa/src/voice/VoiceProvider.tsx`
- Create: `maya-ppa/src/voice/useVoice.ts`

**Reference:** `maya-ppa/src/auth/AuthProvider.tsx` for provider pattern, `maya-ppa/src/health/HealthProvider.tsx` for root provider wrapping.

- [ ] **Step 1: Create useVoice hook**

Create `maya-ppa/src/voice/useVoice.ts`:

```typescript
import { useContext } from 'react';
import { VoiceContext } from './VoiceProvider';

export function useVoice() {
  const ctx = useContext(VoiceContext);
  if (!ctx) throw new Error('useVoice must be inside VoiceProvider');
  return ctx;
}
```

- [ ] **Step 2: Create VoiceProvider**

Create `maya-ppa/src/voice/VoiceProvider.tsx`:

```typescript
import { createContext, useCallback, useRef, useState } from 'react';
import { type AgentState, connectVoiceWS } from './ws';
import { configureAudioSession, requestMicPermission } from './audio';

export type VoiceContextValue = {
  isActive: boolean;
  isConnected: boolean;
  agentState: AgentState;
  startSession: () => Promise<void>;
  endSession: () => void;
};

export const VoiceContext = createContext<VoiceContextValue | null>(null);

export function VoiceProvider({ children }: { children: React.ReactNode }) {
  const [isActive, setIsActive] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [agentState, setAgentState] = useState<AgentState>('idle');
  const wsRef = useRef<ReturnType<typeof connectVoiceWS> | null>(null);

  const startSession = useCallback(async () => {
    const granted = await requestMicPermission();
    if (!granted) return;

    await configureAudioSession();
    setIsActive(true);
    setAgentState('listening');

    try {
      const ws = connectVoiceWS({
        onAudio: (_pcmBase64: string) => {
          // TODO(task-6): pipe to audio playback queue
        },
        onStateChange: (state: AgentState) => {
          setAgentState(state);
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

  const endSession = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
    setIsActive(false);
    setAgentState('idle');
  }, []);

  return (
    <VoiceContext.Provider value={{ isActive, isConnected, agentState, startSession, endSession }}>
      {children}
    </VoiceContext.Provider>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/anurag/Documents/git/liv150/maya-ppa
git add src/voice/VoiceProvider.tsx src/voice/useVoice.ts
git commit -m "feat(voice): add VoiceProvider context and useVoice hook"
```

---

## Task 8: VoiceFab (Floating Action Button)

The floating Maya orb button visible on every screen.

**Files:**
- Create: `maya-ppa/src/components/ds/VoiceFab.tsx`

**Reference:** `maya-ppa/src/components/ds/MayaOrb.tsx` for the orb component, `maya-ppa/src/components/ds/Button.tsx` for press animation patterns.

- [ ] **Step 1: Create VoiceFab component**

Create `maya-ppa/src/components/ds/VoiceFab.tsx`:

```tsx
import { Pressable, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';
import { useEffect } from 'react';
import { useVoice } from '@/voice/useVoice';
import { colors } from '@/components/ds/tokens';
import { Ionicons } from '@expo/vector-icons';

export function VoiceFab() {
  const { isActive, startSession } = useVoice();
  const pulse = useSharedValue(1);

  useEffect(() => {
    pulse.value = withRepeat(
      withTiming(1.08, { duration: 1200 }),
      -1,
      true,
    );
  }, [pulse]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: pulse.value }],
  }));

  if (isActive) return null;

  return (
    <View
      style={{
        position: 'absolute',
        bottom: 100,
        right: 20,
        zIndex: 999,
      }}
    >
      <Pressable onPress={startSession}>
        <Animated.View
          style={[
            {
              width: 56,
              height: 56,
              borderRadius: 28,
              backgroundColor: colors.primary[500],
              alignItems: 'center',
              justifyContent: 'center',
              shadowColor: colors.primary[500],
              shadowOffset: { width: 0, height: 4 },
              shadowOpacity: 0.4,
              shadowRadius: 12,
              elevation: 8,
            },
            animatedStyle,
          ]}
        >
          <Ionicons name="mic" size={24} color="#0B0B14" />
        </Animated.View>
      </Pressable>
    </View>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/anurag/Documents/git/liv150/maya-ppa
git add src/components/ds/VoiceFab.tsx
git commit -m "feat(voice): add floating VoiceFab button"
```

---

## Task 9: VoiceOverlay (Full-Screen Session UI)

The full-screen overlay shown during a voice session with Maya orb animation.

**Files:**
- Create: `maya-ppa/src/components/ds/VoiceOverlay.tsx`

**Reference:** `maya-ppa/src/components/ds/MayaOrb.tsx` for the orb, `maya-ppa/src/components/ds/AmbientBg.tsx` for background.

- [ ] **Step 1: Create VoiceOverlay component**

Create `maya-ppa/src/components/ds/VoiceOverlay.tsx`:

```tsx
import { Pressable, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { MayaOrb } from '@/components/ds/MayaOrb';
import { AmbientBg } from '@/components/ds/AmbientBg';
import { Text } from '@/components/ds/Text';
import { useVoice } from '@/voice/useVoice';
import { colors } from '@/components/ds/tokens';

const STATE_LABELS: Record<string, string> = {
  listening: 'Listening...',
  thinking: 'Thinking...',
  speaking: 'Maya is speaking',
  idle: '',
};

const STATE_AMP: Record<string, number> = {
  listening: 0.3,
  thinking: 0.15,
  speaking: 0.6,
  idle: 0.1,
};

export function VoiceOverlay() {
  const { isActive, agentState, endSession } = useVoice();

  if (!isActive) return null;

  return (
    <View
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 1000,
      }}
      className="bg-base"
    >
      <AmbientBg />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View className="flex-1 items-center justify-center px-7">
          {/* Close button */}
          <View style={{ position: 'absolute', top: 16, right: 24 }}>
            <Pressable
              onPress={endSession}
              className="w-10 h-10 rounded-full bg-white/[0.08] items-center justify-center"
            >
              <Ionicons name="close" size={20} color={colors.text.foreground} />
            </Pressable>
          </View>

          {/* Maya Orb */}
          <MayaOrb amp={STATE_AMP[agentState] ?? 0.2} size={220} />

          {/* State label */}
          <Text tone="muted" className="text-sm mt-8" style={{ fontFamily: 'PlusJakartaSans_500Medium' }}>
            {STATE_LABELS[agentState] ?? ''}
          </Text>
        </View>
      </SafeAreaView>
    </View>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/anurag/Documents/git/liv150/maya-ppa
git add src/components/ds/VoiceOverlay.tsx
git commit -m "feat(voice): add full-screen VoiceOverlay with orb animation"
```

---

## Task 10: Wire Voice into Root Layout

Add `VoiceProvider`, `VoiceFab`, and `VoiceOverlay` to the root layout so voice is accessible from every screen.

**Files:**
- Modify: `maya-ppa/src/app/_layout.tsx`

**Reference:** Current root layout at `maya-ppa/src/app/_layout.tsx` — provider stack order is GestureHandler → KeyboardProvider → SafeArea → Auth → Health → Theme → OnboardingGate → Stack.

- [ ] **Step 1: Add voice components to root layout**

In `maya-ppa/src/app/_layout.tsx`, add imports at the top:

```typescript
import { VoiceProvider } from '@/voice/VoiceProvider';
import { VoiceFab } from '@/components/ds/VoiceFab';
import { VoiceOverlay } from '@/components/ds/VoiceOverlay';
```

In the `RootLayout` component, wrap `VoiceProvider` around the `ThemeProvider` block (inside `HealthProvider`, so it has access to auth context), and add `VoiceFab` + `VoiceOverlay` as siblings to the `Stack`:

Change the return JSX in `RootLayout` from:

```tsx
<HealthProvider>
  <ThemeProvider value={colorScheme === "light" ? DefaultTheme : DarkTheme}>
    <OnboardingGate>
      <Stack screenOptions={{ headerShown: false }}>
        {/* ... screens ... */}
      </Stack>
    </OnboardingGate>
    <StatusBar style="light" />
  </ThemeProvider>
</HealthProvider>
```

To:

```tsx
<HealthProvider>
  <VoiceProvider>
    <ThemeProvider value={colorScheme === "light" ? DefaultTheme : DarkTheme}>
      <OnboardingGate>
        <Stack screenOptions={{ headerShown: false }}>
          {/* ... screens ... */}
        </Stack>
        <VoiceFab />
        <VoiceOverlay />
      </OnboardingGate>
      <StatusBar style="light" />
    </ThemeProvider>
  </VoiceProvider>
</HealthProvider>
```

- [ ] **Step 2: Verify the app builds**

Run: `cd /Users/anurag/Documents/git/liv150/maya-ppa && bunx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
cd /Users/anurag/Documents/git/liv150/maya-ppa
git add src/app/_layout.tsx
git commit -m "feat(voice): wire VoiceProvider, VoiceFab, and VoiceOverlay into root layout"
```

---

## Task 11: End-to-End Integration Test

Verify the full flow works: mobile connects via WebSocket, server opens Gemini Live session, audio relays, tool calls execute.

**Files:**
- No new files — this is a manual integration test

- [ ] **Step 1: Start the backend**

Run in one terminal:
```bash
cd /Users/anurag/Documents/git/liv150/liv150-api
PYTHONPATH=src .venv/bin/uvicorn liv150_api.main:app --reload --port 8001
```

- [ ] **Step 2: Start the maya-pa server**

Run in another terminal:
```bash
cd /Users/anurag/Documents/git/liv150/maya-pa/server
PYTHONPATH=src .venv/bin/uvicorn live150.main:app --reload --port 8000
```

- [ ] **Step 3: Start the mobile app**

Run in another terminal:
```bash
cd /Users/anurag/Documents/git/liv150/maya-ppa
bunx expo start --clear
```

- [ ] **Step 4: Test the voice flow**

1. Open the app on a real device (not simulator — need real mic/speaker for AEC)
2. Complete auth flow (phone + OTP)
3. Verify the floating Maya orb appears on the home screen
4. Tap the orb — verify VoiceOverlay appears with "Listening..." state
5. Speak to Maya — verify:
   - Orb animation changes to "speaking" when Maya responds
   - Audio plays back through the device speaker
   - No echo (your voice isn't fed back through Maya's response)
6. Ask "what are my goals?" — verify Maya responds using the tool (brief pause for tool call)
7. Say "I just went for a 30 minute run" — verify Maya acknowledges and logs it
8. Tap close — verify overlay dismisses and orb reappears

- [ ] **Step 5: Fix any issues found during testing**

If audio doesn't stream, check:
- WebSocket connection established (check server logs for `voice_ws_connected`)
- Gemini session opened (check for errors in server logs)
- Audio format matches (PCM 16kHz 16-bit mono)
- AEC configured (check audio session category on iOS/Android)

---

## Unresolved Questions

1. **expo-audio PCM streaming** — The exact API for streaming raw PCM chunks in real-time from `expo-audio` needs to be verified at implementation time. If it doesn't support real-time chunk callbacks, `react-native-live-audio-stream` is the fallback for recording.

2. **Gemini Live model availability** — `gemini-2.5-flash-native-audio-preview-12-2025` needs to be verified as available on Vertex AI `global` region. If not, try `us-central1` or the latest available model ID.

3. **JWT validation on maya-pa** — The current gate middleware uses its own JWT secret (`gate_jwt_secret`). The voice endpoint validates using the same secret. If the mobile app sends a liv150-api JWT instead, the secrets need to match or the voice endpoint needs to validate against liv150-api's secret.

4. **liv150-api endpoints for voice tools** — `GET /api/v1/health/progress`, `POST /api/v1/reminders`, `GET /api/v1/reminders`, `DELETE /api/v1/reminders/{id}` don't exist yet on liv150-api. They need to be built for the health and reminder tools to work. For initial testing, these tools will return error messages gracefully.
