"""Placeholder health API tools.

Each tool is a plain async function that ADK wraps as a FunctionTool.
Real implementations will call Live150 REST APIs via tools/base.py helpers.
Anurag will replace these with actual API endpoints.
"""


async def get_sleep_summary(days: int = 7, tool_context=None) -> dict:
    """Get the user's sleep summary for the past N days."""
    api_token = tool_context.state["api_token"] if tool_context else ""
    # Placeholder — will call: GET /api/sleep/summary?days={days}
    return {
        "placeholder": True,
        "tool": "get_sleep_summary",
        "days": days,
        "message": "Replace with real Live150 API call to /api/sleep/summary",
    }


async def get_activity_summary(days: int = 7, tool_context=None) -> dict:
    """Get the user's activity summary for the past N days."""
    api_token = tool_context.state["api_token"] if tool_context else ""
    return {
        "placeholder": True,
        "tool": "get_activity_summary",
        "days": days,
        "message": "Replace with real Live150 API call to /api/activity/summary",
    }


async def get_meal_log(days: int = 3, tool_context=None) -> dict:
    """Get the user's meal log for the past N days."""
    api_token = tool_context.state["api_token"] if tool_context else ""
    return {
        "placeholder": True,
        "tool": "get_meal_log",
        "days": days,
        "message": "Replace with real Live150 API call to /api/nutrition/meals",
    }


async def log_water(ml: int, tool_context=None) -> dict:
    """Log water intake in milliliters. Safe write — executes immediately."""
    api_token = tool_context.state["api_token"] if tool_context else ""
    return {
        "placeholder": True,
        "tool": "log_water",
        "ml": ml,
        "message": "Replace with real Live150 API call to POST /api/nutrition/water",
    }


async def get_current_plan(tool_context=None) -> dict:
    """Get the user's current workout/health plan."""
    api_token = tool_context.state["api_token"] if tool_context else ""
    return {
        "placeholder": True,
        "tool": "get_current_plan",
        "message": "Replace with real Live150 API call to /api/plans/current",
    }


async def cancel_workout_plan(plan_id: str, tool_context=None) -> dict:
    """Cancel a workout plan. Risky write — requires user confirmation."""
    api_token = tool_context.state["api_token"] if tool_context else ""
    return {
        "placeholder": True,
        "tool": "cancel_workout_plan",
        "plan_id": plan_id,
        "message": "Replace with real Live150 API call to DELETE /api/plans/{plan_id}",
    }
