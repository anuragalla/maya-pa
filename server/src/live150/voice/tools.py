"""Voice tool declarations and handlers for Gemini Live API.

Defines function_declarations consumed by the Gemini Live connect config.
When Gemini calls a tool during a voice session, the server dispatches to the
matching handler below.

Handlers use a flat call signature:
    handler(args: dict, user_phone: str, db: AsyncSession, **ctx) -> dict

The **ctx kwargs carry:
    api_base: str       — Live150 API base URL
    access_token: str   — user-scoped bearer token
"""

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
        "name": "log_entry",
        "description": (
            "Log a health metric. Call immediately when the user mentions any "
            "health activity: water intake, steps, exercise, meals, sleep, etc. "
            "Log first, ask clarifying questions only if genuinely ambiguous."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entries": {
                    "type": "array",
                    "description": "One or more metric entries to log.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric": {
                                "type": "string",
                                "description": "Metric name: water_ml, steps, active_minutes, sleep_hours, calories, meditation_min, distance_km, weight_kg",
                            },
                            "value": {
                                "type": "number",
                                "description": "Numeric value for this metric.",
                            },
                            "unit": {
                                "type": "string",
                                "description": "Unit of measurement (ml, steps, min, hours, kcal, km, kg).",
                            },
                        },
                        "required": ["metric", "value", "unit"],
                    },
                },
                "source_detail": {
                    "type": "string",
                    "description": "Natural language description (e.g. 'morning run in the park', '2 glasses of water').",
                },
            },
            "required": ["entries"],
        },
    },
    {
        "name": "get_weekly_plan",
        "description": (
            "Get the user's weekly plan — scheduled actions for the current or specified week. "
            "Use this to see what activities are planned, discuss upcoming tasks, or check completion status."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "week_start": {
                    "type": "string",
                    "description": "Monday date in YYYY-MM-DD format. Defaults to current week.",
                },
            },
        },
    },
    {
        "name": "get_goals",
        "description": (
            "Get the user's current health goals with targets and progress. "
            "Shows daily metrics the user is working toward (steps, water, sleep, etc)."
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


async def _handle_log_entry(args: dict, user_phone: str, db, **ctx) -> dict:
    entries = args.get("entries", [])
    source_detail = args.get("source_detail", "")

    if not entries:
        return {"error": True, "message": "No entries provided."}

    access_token = ctx.get("access_token", "")
    api_base = ctx.get("api_base", "")

    # POST to unified logs endpoint
    payload = {
        "entries": [
            {
                "metric": e["metric"],
                "value": e["value"],
                "unit": e["unit"],
                "source": "voice_agent",
            }
            for e in entries
        ]
    }

    logged = False
    if access_token and api_base:
        try:
            async with httpx.AsyncClient(base_url=api_base, timeout=15.0) as client:
                r = await client.post(
                    "/api/v1/logs",
                    json=payload,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                r.raise_for_status()
                logged = True
        except Exception as exc:
            logger.warning("voice:log_entry_failed", extra={"user_phone": user_phone, "error": str(exc)})

    # Save to memory for context
    memory_parts = []
    for e in entries:
        memory_parts.append(f"{e['value']} {e['unit']} {e['metric']}")
    memory_content = f"User logged: {', '.join(memory_parts)}"
    if source_detail:
        memory_content += f" ({source_detail})"

    try:
        await _memory_service.save(
            db=db,
            user_id=user_phone,
            kind="event",
            content=memory_content,
            source="user",
            metadata={"metrics": [e["metric"] for e in entries]},
        )
    except Exception as e:
        logger.warning("voice:log_entry_memory_failed", extra={"user_phone": user_phone, "error": str(e)})

    return {"logged": logged, "entries_count": len(entries), "summary": memory_content}


async def _handle_get_weekly_plan(args: dict, user_phone: str, db, **ctx) -> dict:
    access_token = ctx.get("access_token", "")
    api_base = ctx.get("api_base", "")
    week_start = args.get("week_start")

    params = {}
    if week_start:
        params["week_start"] = week_start

    try:
        async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
            r = await client.get(
                "/api/v1/plans",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code == 404:
                return {"has_plan": False, "message": "No plan generated for this week yet."}
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("voice:get_weekly_plan failed", extra={"user_phone": user_phone, "error": str(e)})
        return {"error": True, "message": f"Could not fetch plan: {e}"}

    return {"has_plan": True, **data}


async def _handle_get_goals(args: dict, user_phone: str, db, **ctx) -> dict:
    access_token = ctx.get("access_token", "")
    api_base = ctx.get("api_base", "")

    try:
        async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
            r = await client.get(
                "/api/v1/goals/current",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("voice:get_goals failed", extra={"user_phone": user_phone, "error": str(e)})
        return {"error": True, "message": f"Could not fetch goals: {e}"}

    return data


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
    "log_entry": _handle_log_entry,
    "get_weekly_plan": _handle_get_weekly_plan,
    "get_goals": _handle_get_goals,
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
