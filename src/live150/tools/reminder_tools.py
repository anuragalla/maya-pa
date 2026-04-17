"""Reminder tools for the agent to create, list, and cancel reminders."""


async def create_reminder(
    title: str,
    when: str,
    prompt: str,
    recurrence: str | None = None,
    tool_context=None,
) -> dict:
    """Create a reminder for the user.

    Args:
        title: Short description of the reminder.
        when: Natural language time expression (e.g., "every Monday 9am", "tomorrow at 7pm", "in 2 hours").
        prompt: What the agent should do when the reminder fires.
        recurrence: Optional recurrence pattern if different from 'when'.
    """
    return {
        "placeholder": True,
        "tool": "create_reminder",
        "title": title,
        "when": when,
        "prompt": prompt,
        "recurrence": recurrence,
        "message": "Reminder creation — will be wired to APScheduler",
    }


async def list_reminders(tool_context=None) -> dict:
    """List the user's active reminders."""
    return {
        "placeholder": True,
        "tool": "list_reminders",
        "reminders": [],
        "message": "Reminder listing — will be wired to DB query",
    }


async def cancel_reminder(reminder_id: str, tool_context=None) -> dict:
    """Cancel a reminder by its ID."""
    return {
        "placeholder": True,
        "tool": "cancel_reminder",
        "reminder_id": reminder_id,
        "message": "Reminder cancellation — will be wired to APScheduler",
    }
