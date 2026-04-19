"""Assembles all FunctionTools into the agent's tool registry."""

from google.adk.tools import FunctionTool

from live150.tools.calendar_tools import (
    check_calendar_connection,
    create_live150_event,
    delete_live150_event,
    find_free_slots,
    get_calendar_schedule,
)
from live150.tools.health_api import (
    get_holistic_analysis,
    get_progress_by_date,
    get_health_goals,
    get_meal_plan,
    get_initial_context,
)
from live150.tools.integration_tools import (
    list_available_integrations,
    request_integration_connect,
)
from live150.tools.memory_tools import save_memory, search_memory
from live150.tools.reminder_tools import cancel_reminder, create_reminder, list_reminders
from live150.tools.skill_tools import skill_load, skill_search

# Tools allowed during reminder-time runs (service token, read-only)
REMINDER_SAFE_TOOLS = {
    "get_holistic_analysis",
    "get_progress_by_date",
    "get_health_goals",
    "search_memory",
    "list_reminders",
    "skill_search",
    "skill_load",
    # Calendar reads are safe in reminder mode
    "get_calendar_schedule",
    "check_calendar_connection",
    "find_free_slots",
    "list_available_integrations",
}


def build_tool_registry() -> list[FunctionTool]:
    """Build the complete list of agent tools."""
    tools = [
        # Live150 health data (5 real API routes)
        FunctionTool(func=get_holistic_analysis),
        FunctionTool(func=get_progress_by_date),
        FunctionTool(func=get_health_goals),
        FunctionTool(func=get_meal_plan),
        FunctionTool(func=get_initial_context),
        # Memory
        FunctionTool(func=search_memory),
        FunctionTool(func=save_memory),
        # Reminders
        FunctionTool(func=create_reminder),
        FunctionTool(func=list_reminders),
        FunctionTool(func=cancel_reminder),
        # Skills (on-demand runbook loading)
        FunctionTool(func=skill_search),
        FunctionTool(func=skill_load),
        # Calendar
        FunctionTool(func=get_calendar_schedule),
        FunctionTool(func=create_live150_event),
        FunctionTool(func=delete_live150_event),
        FunctionTool(func=find_free_slots),
        FunctionTool(func=check_calendar_connection),
        # Integrations
        FunctionTool(func=list_available_integrations),
        FunctionTool(func=request_integration_connect),
    ]
    return tools
