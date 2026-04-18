"""Health API tools — wired to real Live150 dev-route endpoints.

These map to the 5 user-scoped GETs in the dev handoff doc.
The access_token comes from session state (set by the auth middleware
after impersonating the user).
"""

import logging
from datetime import date, datetime, timezone

from live150.live150_client import get_client

logger = logging.getLogger(__name__)


async def get_holistic_analysis(tool_context=None) -> dict:
    """Get the user's forward-looking holistic analysis across all health pillars.

    Returns Maya's per-pillar analysis: nutrition, activity, mindfulness,
    sleep, glucose, and weight — plus short "Maya says" summaries.
    """
    token = tool_context.state["access_token"]
    client = get_client()
    try:
        result = await client.get_holistic_analysis(token)
    except Exception as e:
        logger.warning("get_holistic_analysis failed", extra={"error": str(e)})
        return {"error": True, "message": f"Could not fetch holistic analysis: {e}"}
    if result is None:
        return {"message": "No holistic analysis generated for today yet."}
    return result.model_dump()


async def get_progress_by_date(date_lookup: str | None = None, tool_context=None) -> dict:
    """Get the user's progress summary for a specific date.

    Shows logged meals, activity, goal progress (calories, macros, etc).

    Args:
        date_lookup: Date in YYYY-MM-DD format. Defaults to today.
    """
    token = tool_context.state["access_token"]
    if not date_lookup:
        date_lookup = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    client = get_client()
    try:
        text = await client.get_progress_by_date(token, date_lookup)
    except Exception as e:
        logger.warning("get_progress_by_date failed", extra={"error": str(e), "date": date_lookup})
        return {"error": True, "date": date_lookup, "message": f"Could not fetch progress: {e}"}
    return {"date": date_lookup, "summary": text}


async def get_health_goals(tool_context=None) -> dict:
    """Get the user's health goals derived from onboarding.

    Returns holistic goals, daily nutritional targets, weight goals,
    and health concerns.
    """
    token = tool_context.state["access_token"]
    client = get_client()
    try:
        result = await client.get_my_health_goals(token)
    except Exception as e:
        logger.warning("get_health_goals failed", extra={"error": str(e)})
        return {"error": True, "message": f"Could not fetch health goals: {e}"}
    return {"goals": result.response}


async def get_meal_plan(tool_context=None) -> dict:
    """Get the user's meal plan for today.

    Returns the full day's meals with portions and macros (paid users),
    or a message about upgrading (free users).
    """
    token = tool_context.state["access_token"]
    client = get_client()
    try:
        result = await client.get_meal_plan(token)
    except Exception as e:
        logger.warning("get_meal_plan failed", extra={"error": str(e)})
        return {"error": True, "message": f"Could not fetch meal plan: {e}"}
    return {"meal_plan": result.response}


async def get_initial_context(tool_context=None) -> dict:
    """Get the user's full profile context: personal info, health profile,
    and all questionnaire responses (nutrition, activity, sleep, mindfulness).
    """
    token = tool_context.state["access_token"]
    client = get_client()
    try:
        result = await client.get_initial_context(token)
    except Exception as e:
        logger.warning("get_initial_context failed", extra={"error": str(e)})
        return {"error": True, "message": f"Could not fetch user context: {e}"}
    return result.model_dump()
