"""Reminder-to-calendar mirroring.

Decides whether a reminder should be mirrored to connected calendar
providers and performs the mirroring as best-effort post-commit.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from live150.calendar.service import CalendarService
from live150.calendar.types import EventInput
from live150.db.models.reminder import Reminder
from live150.db.models.reminder_calendar_event import ReminderCalendarEvent
from live150.db.models.user_calendar import UserCalendar

logger = logging.getLogger(__name__)

# Titles that are too generic to warrant a calendar event
_NOISE_TITLES = {"drink water", "water", "hydrate", "stretch", "breathe"}


def should_mirror(reminder: Reminder, *, force: bool | None = None) -> bool:
    """Decide whether a reminder should be mirrored to calendar.

    Heuristic:
    - once + specific time → yes (15-min event)
    - cron + daily/weekly → yes (recurring)
    - interval → no (doesn't map cleanly)
    - generic title → no (noise)
    - force=True/False overrides
    """
    if force is True:
        return True
    if force is False:
        return False

    if reminder.schedule_kind == "interval":
        return False

    if reminder.title.lower().strip() in _NOISE_TITLES:
        return False

    return True


async def mirror_reminder_to_calendar(
    reminder: Reminder,
    cal_service: CalendarService,
    db: AsyncSession,
    *,
    force: bool | None = None,
) -> None:
    """Mirror a reminder to all connected calendar providers. Best-effort."""
    if not should_mirror(reminder, force=force):
        return

    # Get connected providers
    stmt = select(UserCalendar).where(UserCalendar.user_id == reminder.user_id)
    rows = (await db.execute(stmt)).scalars().all()

    for uc in rows:
        if not uc.calendar_id:
            continue

        try:
            event_input = _reminder_to_event_input(reminder)
            event = await cal_service.create_live150_event(
                reminder.user_id, db, event_input, provider_name=uc.provider
            )

            db.add(ReminderCalendarEvent(
                reminder_id=reminder.reminder_id,
                provider=uc.provider,
                provider_event_id=event.provider_event_id,
                calendar_id=event.calendar_id,
            ))
            await db.commit()
            logger.info(
                "Mirrored reminder %s to %s calendar",
                reminder.reminder_id, uc.provider,
            )
        except Exception as e:
            logger.warning(
                "Failed to mirror reminder %s to %s: %s",
                reminder.reminder_id, uc.provider, e,
            )


async def unmirror_reminder_from_calendar(
    reminder_id: uuid.UUID,
    cal_service: CalendarService,
    db: AsyncSession,
) -> None:
    """Remove calendar events created for a reminder. Best-effort."""
    stmt = select(ReminderCalendarEvent).where(
        ReminderCalendarEvent.reminder_id == reminder_id
    )
    rows = (await db.execute(stmt)).scalars().all()

    for rce in rows:
        try:
            await cal_service.delete_live150_event(
                # We need user_id — get it from the reminder
                (await db.execute(
                    select(Reminder.user_id).where(Reminder.reminder_id == reminder_id)
                )).scalar_one(),
                db, rce.provider_event_id, provider_name=rce.provider,
            )
        except Exception as e:
            logger.warning("Failed to delete mirrored event %s: %s", rce.provider_event_id, e)

    # Clean up junction rows
    await db.execute(
        delete(ReminderCalendarEvent).where(ReminderCalendarEvent.reminder_id == reminder_id)
    )
    await db.commit()


def _reminder_to_event_input(reminder: Reminder) -> EventInput:
    """Convert a Reminder into an EventInput for calendar creation."""
    if reminder.schedule_kind == "once":
        start = datetime.fromisoformat(reminder.schedule_expr)
        end = start + timedelta(minutes=15)
        return EventInput(
            title=reminder.title,
            start_at=start,
            end_at=end,
            description=f"Live150 reminder: {reminder.prompt_template[:200]}",
        )

    if reminder.schedule_kind == "cron":
        # For cron, create a recurring event starting from now
        # Map cron to RRULE
        rrule = _cron_to_rrule(reminder.schedule_expr)
        now = datetime.now(timezone.utc)
        # Default to a 15-min event at the cron time
        fields = reminder.schedule_expr.split()
        hour = int(fields[1]) if fields[1] != "*" else 9
        minute = int(fields[0]) if fields[0] != "*" else 0
        start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start < now:
            start += timedelta(days=1)
        end = start + timedelta(minutes=15)
        return EventInput(
            title=reminder.title,
            start_at=start,
            end_at=end,
            description=f"Live150 reminder: {reminder.prompt_template[:200]}",
            recurrence_rrule=rrule,
        )

    # Shouldn't reach here due to should_mirror check
    raise ValueError(f"Cannot mirror schedule_kind={reminder.schedule_kind}")


def _cron_to_rrule(cron_expr: str) -> str:
    """Best-effort conversion of 5-field cron to RFC 5545 RRULE."""
    fields = cron_expr.split()
    if len(fields) != 5:
        return "FREQ=DAILY"

    _minute, _hour, day, _month, dow = fields

    # Daily pattern: * * * * *  or  0 9 * * *
    if day == "*" and dow == "*":
        return "FREQ=DAILY"

    # Weekly pattern: 0 9 * * 1  or  0 9 * * MON,WED,FRI
    if day == "*" and dow != "*":
        day_map = {"0": "SU", "1": "MO", "2": "TU", "3": "WE", "4": "TH", "5": "FR", "6": "SA",
                   "SUN": "SU", "MON": "MO", "TUE": "TU", "WED": "WE", "THU": "TH", "FRI": "FR", "SAT": "SA"}
        days = []
        for d in dow.split(","):
            days.append(day_map.get(d.upper(), d.upper()))
        return f"FREQ=WEEKLY;BYDAY={','.join(days)}"

    return "FREQ=DAILY"
