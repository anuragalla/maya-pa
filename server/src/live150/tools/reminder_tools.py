"""Reminder tools — wired to APScheduler + Postgres.

Creates/lists/cancels reminders. The scheduler persists jobs in the
apscheduler_jobs table; our reminder table holds user-facing metadata.
"""

import logging
import uuid

from sqlalchemy import select
from uuid6 import uuid7

from live150.db.models.reminder import Reminder
from live150.db.models.user_profile import UserProfile
from live150.db.session import async_session_factory
from live150.reminders.jobs import fire_reminder
from live150.reminders.parser import parse_schedule, validate_schedule
from live150.reminders.scheduler import get_scheduler

logger = logging.getLogger(__name__)


def _make_trigger(kind: str, expr: str, tz: str):
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from datetime import datetime

    if kind == "once":
        return DateTrigger(run_date=datetime.fromisoformat(expr), timezone=tz)
    elif kind == "cron":
        fields = expr.split()
        return CronTrigger(
            minute=fields[0], hour=fields[1], day=fields[2],
            month=fields[3], day_of_week=fields[4], timezone=tz,
        )
    elif kind == "interval":
        return IntervalTrigger(seconds=int(expr), timezone=tz)
    else:
        raise ValueError(f"Unknown schedule kind: {kind}")


async def create_reminder(
    title: str,
    when: str,
    prompt: str,
    recurrence: str | None = None,
    tool_context=None,
) -> dict:
    """Create a timed reminder for the user.

    The reminder fires at the scheduled time. When it fires, the agent runs
    with the prompt you provide and sends the output as a notification.

    Args:
        title: Short description shown in the notification (e.g., "Drink water").
        when: Natural language schedule (e.g., "every Monday 9am", "tomorrow at 7pm", "in 2 hours", "daily").
        prompt: What the agent should do when the reminder fires (e.g., "Check my water intake and remind me to hydrate").
        recurrence: Optional — override recurrence if 'when' is ambiguous.
    """
    user_id = tool_context.state["user_id"]

    async with async_session_factory() as db:
        profile = (await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )).scalar_one_or_none()
        user_tz = profile.timezone if profile else "UTC"

    schedule_text = recurrence or when
    try:
        schedule = await parse_schedule(schedule_text, user_tz)
    except ValueError as e:
        return {"created": False, "error": f"Could not understand schedule: {e}"}

    if not validate_schedule(schedule):
        return {"created": False, "error": f"Invalid schedule: {schedule.expr}"}

    reminder_id = uuid7()
    job_id = f"reminder:{reminder_id}"

    async with async_session_factory() as db:
        db.add(Reminder(
            reminder_id=reminder_id,
            user_id=user_id,
            created_by="agent",
            title=title,
            prompt_template=prompt,
            schedule_kind=schedule.kind,
            schedule_expr=schedule.expr,
            timezone=schedule.timezone,
            job_id=job_id,
            status="active",
        ))
        await db.commit()

    trigger = _make_trigger(schedule.kind, schedule.expr, schedule.timezone)
    get_scheduler().add_job(
        fire_reminder,
        trigger=trigger,
        args=[str(reminder_id)],
        id=job_id,
        name=title,
        replace_existing=True,
    )

    # Best-effort: mirror to connected calendars
    try:
        from live150.calendar.mirror import mirror_reminder_to_calendar
        from live150.tools.calendar_tools import _cal_service
        if _cal_service is not None:
            async with async_session_factory() as db:
                reminder_row = (await db.execute(
                    select(Reminder).where(Reminder.reminder_id == reminder_id)
                )).scalar_one_or_none()
                if reminder_row:
                    await mirror_reminder_to_calendar(reminder_row, _cal_service, db)
    except Exception as e:
        logger.warning("Calendar mirror failed for reminder %s: %s", reminder_id, e)

    return {
        "created": True,
        "reminder_id": str(reminder_id),
        "title": title,
        "schedule": f"{schedule.kind}: {schedule.expr} ({schedule.timezone})",
    }


async def list_reminders(tool_context=None) -> dict:
    """List the user's active and paused reminders."""
    user_id = tool_context.state["user_id"]

    async with async_session_factory() as db:
        result = await db.execute(
            select(Reminder)
            .where(Reminder.user_id == user_id, Reminder.status.in_(["active", "paused"]))
            .order_by(Reminder.created_at.desc())
        )
        reminders = result.scalars().all()

    if not reminders:
        return {"reminders": [], "message": "No active reminders."}

    return {
        "reminders": [
            {
                "reminder_id": str(r.reminder_id),
                "title": r.title,
                "schedule": f"{r.schedule_kind}: {r.schedule_expr}",
                "timezone": r.timezone,
                "status": r.status,
                "last_fired": r.last_fired_at.isoformat() if r.last_fired_at else None,
                "created_by": r.created_by,
            }
            for r in reminders
        ]
    }


async def cancel_reminder(reminder_id: str, tool_context=None) -> dict:
    """Cancel an active reminder by its ID."""
    user_id = tool_context.state["user_id"]

    async with async_session_factory() as db:
        reminder = (await db.execute(
            select(Reminder).where(
                Reminder.reminder_id == uuid.UUID(reminder_id),
                Reminder.user_id == user_id,
            )
        )).scalar_one_or_none()

        if not reminder:
            return {"cancelled": False, "error": "Reminder not found."}
        if reminder.status == "cancelled":
            return {"cancelled": False, "error": "Reminder is already cancelled."}

        reminder.status = "cancelled"
        await db.commit()

    try:
        get_scheduler().remove_job(reminder.job_id)
    except Exception:
        pass

    # Best-effort: remove mirrored calendar events
    try:
        from live150.calendar.mirror import unmirror_reminder_from_calendar
        from live150.tools.calendar_tools import _cal_service
        if _cal_service is not None:
            async with async_session_factory() as db:
                await unmirror_reminder_from_calendar(uuid.UUID(reminder_id), _cal_service, db)
    except Exception as e:
        logger.warning("Calendar unmirror failed for reminder %s: %s", reminder_id, e)

    return {"cancelled": True, "reminder_id": reminder_id, "title": reminder.title}
