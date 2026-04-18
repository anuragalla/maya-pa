"""OAuth-powered tools (Google Calendar, Gmail, etc.)."""


async def list_calendar_events(timeframe: str = "this week", tool_context=None) -> dict:
    """List the user's upcoming calendar events.

    Args:
        timeframe: Natural language timeframe (e.g., "today", "this week", "next 3 days").
    """
    return {
        "placeholder": True,
        "tool": "list_calendar_events",
        "timeframe": timeframe,
        "message": "Calendar listing — will use Google Calendar API via stored OAuth token",
    }


async def create_calendar_event(
    title: str,
    start_time: str,
    end_time: str,
    description: str = "",
    tool_context=None,
) -> dict:
    """Create a calendar event. Risky write — requires user confirmation.

    Args:
        title: Event title.
        start_time: ISO datetime for event start.
        end_time: ISO datetime for event end.
        description: Optional event description.
    """
    return {
        "placeholder": True,
        "tool": "create_calendar_event",
        "title": title,
        "start_time": start_time,
        "end_time": end_time,
        "description": description,
        "message": "Calendar event creation — will use Google Calendar API via stored OAuth token",
    }
