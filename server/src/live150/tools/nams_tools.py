"""NAMS logging tool — Nutrition, Activity, Mindfulness, Sleep.

When the user mentions any health activity (ran 5k, ate pizza, slept 7h,
meditated 10 mins), the agent calls log_nams immediately. This tool:
  1. POSTs a structured payload to the Live150 log API (fire-and-forget)
  2. Writes a compact event entry to pgvector for semantic memory recall
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Literal

from live150.db.session import async_session_factory
from live150.memory.service import MemoryService
from live150.tools.base import live150_post

logger = logging.getLogger(__name__)

_memory_service = MemoryService()

# Live150 API endpoint — contract TBD, stub logs until confirmed
_NAMS_LOG_PATH = "/api/v1/nams/log"

Category = Literal["activity", "nutrition", "mindfulness", "sleep"]


def _build_payload(
    category: Category,
    logged_at: str,
    # Activity
    activity_type: str | None = None,
    duration_minutes: int | None = None,
    distance_km: float | None = None,
    intensity: Literal["low", "medium", "high"] | None = None,
    # Nutrition
    meal_type: Literal["breakfast", "lunch", "dinner", "snack", "drink"] | None = None,
    items: list[dict] | None = None,
    water_ml: int | None = None,
    calories: int | None = None,
    # Sleep
    duration_hours: float | None = None,
    bedtime: str | None = None,
    wake_time: str | None = None,
    quality: Literal["poor", "fair", "good"] | None = None,
    # Mindfulness
    mindfulness_type: Literal["meditation", "breathing", "journaling", "other"] | None = None,
) -> dict:
    payload: dict = {"category": category, "logged_at": logged_at}

    if category == "activity":
        payload["activity"] = {k: v for k, v in {
            "type": activity_type,
            "duration_minutes": duration_minutes,
            "distance_km": distance_km,
            "intensity": intensity,
        }.items() if v is not None}

    elif category == "nutrition":
        payload["nutrition"] = {k: v for k, v in {
            "meal_type": meal_type,
            "items": items,
            "water_ml": water_ml,
            "calories": calories,
        }.items() if v is not None}

    elif category == "sleep":
        payload["sleep"] = {k: v for k, v in {
            "duration_hours": duration_hours,
            "bedtime": bedtime,
            "wake_time": wake_time,
            "quality": quality,
        }.items() if v is not None}

    elif category == "mindfulness":
        payload["mindfulness"] = {k: v for k, v in {
            "type": mindfulness_type,
            "duration_minutes": duration_minutes,
        }.items() if v is not None}

    return payload


def _build_memory_content(category: Category, payload: dict, logged_at: str) -> str:
    """Build a compact human-readable memory string from the payload."""
    date_str = logged_at[:10]  # YYYY-MM-DD

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


async def _post_to_live150(api_token: str, payload: dict, user_id: str) -> None:
    """Fire-and-forget POST to Live150 NAMS log API."""
    try:
        await live150_post(api_token, _NAMS_LOG_PATH, json=payload)
        logger.info("nams_logged_to_live150", extra={"user_id": user_id, "category": payload["category"]})
    except Exception as e:
        # Non-fatal — memory entry still written
        logger.warning("nams_live150_post_failed", extra={"user_id": user_id, "error": str(e)})


async def log_nams(
    category: str,
    logged_at: str | None = None,
    activity_type: str | None = None,
    duration_minutes: int | None = None,
    distance_km: float | None = None,
    intensity: str | None = None,
    meal_type: str | None = None,
    items: list | None = None,
    water_ml: int | None = None,
    calories: int | None = None,
    duration_hours: float | None = None,
    bedtime: str | None = None,
    wake_time: str | None = None,
    quality: str | None = None,
    mindfulness_type: str | None = None,
    tool_context=None,
) -> dict:
    """Log a Nutrition, Activity, Mindfulness, or Sleep (NAMS) event.

    Call this immediately whenever the user mentions any health activity:
    eating a meal, drinking water, exercising, sleeping, or meditating.
    Do not wait or ask for confirmation — log what was stated.

    Args:
        category: One of 'activity', 'nutrition', 'mindfulness', 'sleep'.
        logged_at: ISO-8601 datetime when the event happened. Defaults to now.
        activity_type: For activity — e.g. 'run', 'walk', 'cycle', 'strength', 'yoga'.
        duration_minutes: Duration in minutes (activity or mindfulness).
        distance_km: Distance in km (activity only).
        intensity: 'low', 'medium', or 'high' (activity only).
        meal_type: 'breakfast', 'lunch', 'dinner', 'snack', or 'drink' (nutrition).
        items: List of {name, quantity} dicts for food items (nutrition).
        water_ml: Water consumed in ml (nutrition).
        calories: Estimated calories (nutrition, optional).
        duration_hours: Sleep duration in hours (sleep).
        bedtime: Bedtime as HH:MM (sleep, optional).
        wake_time: Wake time as HH:MM (sleep, optional).
        quality: 'poor', 'fair', or 'good' (sleep, optional).
        mindfulness_type: 'meditation', 'breathing', 'journaling', or 'other'.
    """
    if category not in ("activity", "nutrition", "mindfulness", "sleep"):
        return {"error": True, "message": f"Invalid category '{category}'."}

    user_id = tool_context.state["user_id"]
    api_token = tool_context.state.get("access_token", "")
    session_id = tool_context.state.get("session_id")

    if not logged_at:
        logged_at = datetime.now(timezone.utc).isoformat()

    payload = _build_payload(
        category=category,
        logged_at=logged_at,
        activity_type=activity_type,
        duration_minutes=duration_minutes,
        distance_km=distance_km,
        intensity=intensity,
        meal_type=meal_type,
        items=items,
        water_ml=water_ml,
        calories=calories,
        duration_hours=duration_hours,
        bedtime=bedtime,
        wake_time=wake_time,
        quality=quality,
        mindfulness_type=mindfulness_type,
    )

    memory_content = _build_memory_content(category, payload, logged_at)

    # Fire Live150 API call in background — don't block on it
    if api_token:
        asyncio.create_task(
            _post_to_live150(api_token, payload, user_id),
            name=f"nams_post:{user_id}:{category}",
        )

    # Write event to pgvector immediately
    async with async_session_factory() as db:
        try:
            await _memory_service.save(
                db=db,
                user_id=user_id,
                kind="event",
                content=memory_content,
                source="user",
                source_ref=session_id,
                metadata={"category": category, "logged_at": logged_at},
            )
        except Exception as e:
            logger.warning("nams_memory_save_failed", extra={"user_id": user_id, "error": str(e)})
            return {"logged": False, "message": "Could not save to memory — database may not be ready."}

    logger.info("nams_logged", extra={"user_id": user_id, "category": category, "content": memory_content})
    return {"logged": True, "category": category, "content": memory_content}
