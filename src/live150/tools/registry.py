"""Assembles all FunctionTools into the agent's tool registry."""

from google.adk.tools import FunctionTool

from live150.tools.health_api import (
    cancel_workout_plan,
    get_activity_summary,
    get_current_plan,
    get_meal_log,
    get_sleep_summary,
    log_water,
)
from live150.tools.memory_tools import save_memory, search_memory
from live150.tools.oauth_tools import create_calendar_event, list_calendar_events
from live150.tools.reminder_tools import cancel_reminder, create_reminder, list_reminders

# Risky tools: intercepted by before_tool_cb, require user confirmation
RISKY_TOOLS = {"cancel_workout_plan", "create_calendar_event", "send_calendar_invite"}

# Safe writes: execute immediately, logged to audit
SAFE_WRITES = {"log_water", "log_mood", "save_memory", "create_reminder", "cancel_reminder"}

# Tools allowed during reminder-time runs (service token, read-only digest endpoints)
REMINDER_SAFE_TOOLS = {
    "get_sleep_summary",
    "get_activity_summary",
    "get_meal_log",
    "search_memory",
    "list_reminders",
}


def build_tool_registry() -> list[FunctionTool]:
    """Build the complete list of agent tools."""
    tools = [
        # Health API — sleep
        FunctionTool(func=get_sleep_summary),
        # Health API — activity
        FunctionTool(func=get_activity_summary),
        # Health API — nutrition
        FunctionTool(func=get_meal_log),
        FunctionTool(func=log_water),
        # Health API — plans
        FunctionTool(func=get_current_plan),
        FunctionTool(func=cancel_workout_plan),
        # Memory
        FunctionTool(func=search_memory),
        FunctionTool(func=save_memory),
        # Reminders
        FunctionTool(func=create_reminder),
        FunctionTool(func=list_reminders),
        FunctionTool(func=cancel_reminder),
        # OAuth / Google
        FunctionTool(func=list_calendar_events),
        FunctionTool(func=create_calendar_event),
    ]
    return tools
