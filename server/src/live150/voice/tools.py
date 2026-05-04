"""Voice tool declarations and handlers for Gemini Live API.

Defines 8 function_declarations consumed by the Gemini Live connect config.
When Gemini calls a tool during a voice session, the server dispatches to the
matching handler below.

Handlers use a flat call signature:
    handler(args: dict, user_phone: str, db: AsyncSession, **ctx) -> dict

The **ctx kwargs carry:
    api_base: str       — Live150 API base URL
    access_token: str   — user-scoped bearer token
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

from live150.memory.service import MemoryService

logger = logging.getLogger(__name__)

_memory_service = MemoryService()

# ---------------------------------------------------------------------------
# Tool declarations (JSON-Schema style, Gemini Live format)
# ---------------------------------------------------------------------------

TOOL_DECLARATIONS: list[dict] = [
    {
        "name": "search_memory",
        "description": (
            "Search the user's long-term memory for relevant information. "
            "Use this to recall facts, preferences, and past events the user has shared."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for (e.g. 'dietary restrictions', 'sleep preferences').",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Save a fact, preference, event, or note to the user's long-term memory. "
            "Use this when the user shares something worth remembering across sessions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["fact", "preference", "event", "note"],
                    "description": "The kind of memory entry.",
                },
                "content": {
                    "type": "string",
                    "description": "The information to remember. Be specific and concise.",
                },
            },
            "required": ["kind", "content"],
        },
    },
    {
        "name": "log_nams",
        "description": (
            "Log a Nutrition, Activity, Mindfulness, or Sleep (NAMS) event. "
            "Call this immediately whenever the user mentions any health activity: "
            "eating a meal, drinking water, exercising, sleeping, or meditating."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["activity", "nutrition", "mindfulness", "sleep"],
                    "description": "The NAMS category.",
                },
                "logged_at": {
                    "type": "string",
                    "description": "ISO-8601 datetime when the event happened. Defaults to now.",
                },
                # Activity
                "activity_type": {
                    "type": "string",
                    "description": "For activity — e.g. 'run', 'walk', 'cycle', 'strength', 'yoga'.",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes (activity or mindfulness).",
                },
                "distance_km": {
                    "type": "number",
                    "description": "Distance in km (activity only).",
                },
                "intensity": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Exercise intensity (activity only).",
                },
                # Nutrition
                "meal_type": {
                    "type": "string",
                    "enum": ["breakfast", "lunch", "dinner", "snack", "drink"],
                    "description": "Meal type (nutrition only).",
                },
                "items": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of {name, quantity} dicts for food items (nutrition).",
                },
                "water_ml": {
                    "type": "integer",
                    "description": "Water consumed in ml (nutrition).",
                },
                "calories": {
                    "type": "integer",
                    "description": "Estimated calories (nutrition, optional).",
                },
                # Sleep
                "duration_hours": {
                    "type": "number",
                    "description": "Sleep duration in hours (sleep).",
                },
                "bedtime": {
                    "type": "string",
                    "description": "Bedtime as HH:MM (sleep, optional).",
                },
                "wake_time": {
                    "type": "string",
                    "description": "Wake time as HH:MM (sleep, optional).",
                },
                "quality": {
                    "type": "string",
                    "enum": ["poor", "fair", "good"],
                    "description": "Sleep quality (sleep, optional).",
                },
                # Mindfulness
                "mindfulness_type": {
                    "type": "string",
                    "enum": ["meditation", "breathing", "journaling", "other"],
                    "description": "Mindfulness activity type.",
                },
            },
            "required": ["category"],
        },
    },
    {
        "name": "get_progress_by_date",
        "description": (
            "Get the user's progress summary for a specific date. "
            "Shows logged meals, activity, and goal progress (calories, macros, etc)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format. Defaults to today.",
                },
            },
        },
    },
    {
        "name": "get_health_goals",
        "description": (
            "Get the user's health goals derived from onboarding. "
            "Returns holistic goals, daily nutritional targets, weight goals, and health concerns."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "create_reminder",
        "description": (
            "Create a timed reminder for the user. "
            "The reminder fires at the scheduled time and sends a notification."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short description shown in the notification (e.g. 'Drink water').",
                },
                "when": {
                    "type": "string",
                    "description": (
                        "Natural language schedule "
                        "(e.g. 'every Monday 9am', 'tomorrow at 7pm', 'in 2 hours', 'daily')."
                    ),
                },
                "prompt": {
                    "type": "string",
                    "description": (
                        "What the agent should do when the reminder fires "
                        "(e.g. 'Check my water intake and remind me to hydrate')."
                    ),
                },
            },
            "required": ["title", "when", "prompt"],
        },
    },
    {
        "name": "list_reminders",
        "description": "List the user's active and paused reminders.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "cancel_reminder",
        "description": "Cancel an active reminder by its ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "reminder_id": {
                    "type": "string",
                    "description": "The UUID of the reminder to cancel.",
                },
            },
            "required": ["reminder_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Helper: build NAMS payload and memory content (shared with existing tool)
# ---------------------------------------------------------------------------

def _build_nams_payload(category: str, logged_at: str, args: dict) -> dict:
    payload: dict = {"category": category, "logged_at": logged_at}

    if category == "activity":
        payload["activity"] = {k: v for k, v in {
            "type": args.get("activity_type"),
            "duration_minutes": args.get("duration_minutes"),
            "distance_km": args.get("distance_km"),
            "intensity": args.get("intensity"),
        }.items() if v is not None}

    elif category == "nutrition":
        payload["nutrition"] = {k: v for k, v in {
            "meal_type": args.get("meal_type"),
            "items": args.get("items"),
            "water_ml": args.get("water_ml"),
            "calories": args.get("calories"),
        }.items() if v is not None}

    elif category == "sleep":
        payload["sleep"] = {k: v for k, v in {
            "duration_hours": args.get("duration_hours"),
            "bedtime": args.get("bedtime"),
            "wake_time": args.get("wake_time"),
            "quality": args.get("quality"),
        }.items() if v is not None}

    elif category == "mindfulness":
        payload["mindfulness"] = {k: v for k, v in {
            "type": args.get("mindfulness_type"),
            "duration_minutes": args.get("duration_minutes"),
        }.items() if v is not None}

    return payload


def _build_nams_memory_content(category: str, payload: dict, logged_at: str) -> str:
    date_str = logged_at[:10]

    if category == "activity":
        a = payload.get("activity", {})
        parts = [f"User did {a.get('type', 'activity')}"]
        if "distance_km" in a:
            parts.append(f"{a['distance_km']}km")
        if "duration_minutes" in a:
            parts.append(f"in {a['duration_minutes']} minutes")
        if "intensity" in a:
            parts.append(f"({a['intensity']} intensity)")
        return f"{' '.join(parts)} on {date_str}"

    elif category == "nutrition":
        n = payload.get("nutrition", {})
        parts = []
        if "meal_type" in n:
            parts.append(n["meal_type"])
        if "items" in n:
            names = ", ".join(i.get("name", "") for i in n["items"] if i.get("name"))
            if names:
                parts.append(f"— {names}")
        if "water_ml" in n:
            parts.append(f"(+{n['water_ml']}ml water)")
        if "calories" in n:
            parts.append(f"~{n['calories']} cal")
        label = " ".join(parts) if parts else "meal"
        return f"User logged {label} on {date_str}"

    elif category == "sleep":
        s = payload.get("sleep", {})
        parts = [f"User slept {s['duration_hours']}h"] if "duration_hours" in s else ["User logged sleep"]
        if "bedtime" in s and "wake_time" in s:
            parts.append(f"({s['bedtime']} → {s['wake_time']})")
        if "quality" in s:
            parts.append(f"quality: {s['quality']}")
        return f"{' '.join(parts)} on {date_str}"

    elif category == "mindfulness":
        m = payload.get("mindfulness", {})
        mtype = m.get("type", "mindfulness")
        dur = f" for {m['duration_minutes']} minutes" if "duration_minutes" in m else ""
        return f"User did {mtype}{dur} on {date_str}"

    return f"User logged {category} on {date_str}"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _handle_search_memory(args: dict, user_phone: str, db, **ctx) -> dict:
    query = args.get("query", "")
    limit = int(args.get("limit", 5))
    try:
        hits = await _memory_service.recall(
            db=db,
            user_id=user_phone,
            query=query,
            limit=limit,
        )
    except Exception as e:
        logger.warning("voice:search_memory failed", extra={"user_phone": user_phone, "error": str(e)})
        return {"results": [], "message": "Memory search unavailable — database may not be initialized yet."}

    if not hits:
        return {"results": [], "message": "No matching memories found."}

    return {
        "results": [
            {
                "kind": hit.kind,
                "content": hit.content,
                "source": hit.source,
                "score": round(hit.score, 3),
            }
            for hit in hits
        ]
    }


async def _handle_save_memory(args: dict, user_phone: str, db, **ctx) -> dict:
    kind = args.get("kind", "")
    content = args.get("content", "")

    if kind not in ("fact", "preference", "event", "note"):
        return {"error": True, "message": f"Invalid kind '{kind}'. Must be one of: fact, preference, event, note."}

    try:
        memory_id = await _memory_service.save(
            db=db,
            user_id=user_phone,
            kind=kind,
            content=content,
            source="voice_agent",
        )
    except Exception as e:
        logger.warning("voice:save_memory failed", extra={"user_phone": user_phone, "error": str(e)})
        return {"saved": False, "message": "Memory save unavailable — database may not be initialized yet."}

    return {"saved": True, "memory_id": str(memory_id), "kind": kind, "content": content}


async def _handle_log_nams(args: dict, user_phone: str, db, **ctx) -> dict:
    category = args.get("category", "")
    if category not in ("activity", "nutrition", "mindfulness", "sleep"):
        return {"error": True, "message": f"Invalid category '{category}'."}

    logged_at = args.get("logged_at") or datetime.now(timezone.utc).isoformat()
    payload = _build_nams_payload(category, logged_at, args)
    memory_content = _build_nams_memory_content(category, payload, logged_at)

    # Fire-and-forget POST to Live150 NAMS log API if we have credentials
    access_token = ctx.get("access_token", "")
    api_base = ctx.get("api_base", "")
    if access_token and api_base:
        async def _post_nams() -> None:
            try:
                async with httpx.AsyncClient(base_url=api_base, timeout=15.0) as client:
                    r = await client.post(
                        "/api/v1/nams/log",
                        json=payload,
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    r.raise_for_status()
            except Exception as exc:
                logger.warning("voice:nams_post_failed", extra={"user_phone": user_phone, "error": str(exc)})

        asyncio.create_task(_post_nams(), name=f"voice_nams:{user_phone}:{category}")

    # Write event to memory
    try:
        await _memory_service.save(
            db=db,
            user_id=user_phone,
            kind="event",
            content=memory_content,
            source="user",
            metadata={"category": category, "logged_at": logged_at},
        )
    except Exception as e:
        logger.warning("voice:nams_memory_save_failed", extra={"user_phone": user_phone, "error": str(e)})
        return {"logged": False, "message": "Could not save to memory — database may not be ready."}

    logger.info("voice:nams_logged", extra={"user_phone": user_phone, "category": category})
    return {"logged": True, "category": category, "content": memory_content}


async def _handle_get_progress(args: dict, user_phone: str, db, **ctx) -> dict:
    access_token = ctx.get("access_token", "")
    api_base = ctx.get("api_base", "")
    date_lookup = args.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
            r = await client.get(
                "/api/v1/maya/maya/progress-by-date",
                params={"date_lookup": date_lookup},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            text = r.text
            if text.startswith('"') and text.endswith('"'):
                text = json.loads(text)
    except Exception as e:
        logger.warning("voice:get_progress failed", extra={"user_phone": user_phone, "error": str(e)})
        return {"error": True, "date": date_lookup, "message": f"Could not fetch progress: {e}"}

    return {"date": date_lookup, "summary": text}


async def _handle_get_goals(args: dict, user_phone: str, db, **ctx) -> dict:
    access_token = ctx.get("access_token", "")
    api_base = ctx.get("api_base", "")

    try:
        async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
            r = await client.get(
                "/api/v1/maya/maya/my-health-goals",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("voice:get_health_goals failed", extra={"user_phone": user_phone, "error": str(e)})
        return {"error": True, "message": f"Could not fetch health goals: {e}"}

    return {"goals": data.get("response", data)}


async def _handle_create_reminder(args: dict, user_phone: str, db, **ctx) -> dict:
    access_token = ctx.get("access_token", "")
    api_base = ctx.get("api_base", "")
    title = args.get("title", "")
    when = args.get("when", "")
    prompt = args.get("prompt", "")

    try:
        async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
            r = await client.post(
                "/api/v1/reminders",
                json={"title": title, "when": when, "prompt": prompt},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("voice:create_reminder failed", extra={"user_phone": user_phone, "error": str(e)})
        return {"created": False, "message": f"Could not create reminder: {e}"}

    return {"created": True, **data}


async def _handle_list_reminders(args: dict, user_phone: str, db, **ctx) -> dict:
    access_token = ctx.get("access_token", "")
    api_base = ctx.get("api_base", "")

    try:
        async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
            r = await client.get(
                "/api/v1/reminders",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("voice:list_reminders failed", extra={"user_phone": user_phone, "error": str(e)})
        return {"reminders": [], "message": f"Could not fetch reminders: {e}"}

    return data if isinstance(data, dict) else {"reminders": data}


async def _handle_cancel_reminder(args: dict, user_phone: str, db, **ctx) -> dict:
    access_token = ctx.get("access_token", "")
    api_base = ctx.get("api_base", "")
    reminder_id = args.get("reminder_id", "")

    try:
        async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
            r = await client.delete(
                f"/api/v1/reminders/{reminder_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("voice:cancel_reminder failed", extra={"user_phone": user_phone, "error": str(e)})
        return {"cancelled": False, "message": f"Could not cancel reminder: {e}"}

    return {"cancelled": True, "reminder_id": reminder_id, **data}


# ---------------------------------------------------------------------------
# Handler dispatch map
# ---------------------------------------------------------------------------

TOOL_HANDLERS: dict = {
    "search_memory": _handle_search_memory,
    "save_memory": _handle_save_memory,
    "log_nams": _handle_log_nams,
    "get_progress_by_date": _handle_get_progress,
    "get_health_goals": _handle_get_goals,
    "create_reminder": _handle_create_reminder,
    "list_reminders": _handle_list_reminders,
    "cancel_reminder": _handle_cancel_reminder,
}


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------

def get_tool_config() -> list[dict]:
    """Return the tools config list for the Gemini Live connect call."""
    return [{"function_declarations": TOOL_DECLARATIONS}]
