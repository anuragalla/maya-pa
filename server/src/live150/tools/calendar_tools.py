"""Calendar tools — exposed to the agent via FunctionTool.

All operations go through CalendarService (provider-agnostic).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from live150.calendar.provider import ProviderAuthError
from live150.calendar.service import CalendarService
from live150.calendar.types import EventInput
from live150.db.models.calendar_snapshot import CalendarSnapshot
from live150.db.models.user_calendar import UserCalendar
from live150.db.session import async_session_factory

logger = logging.getLogger(__name__)

# Lazy singleton — set by wire_calendar_service() at startup
_cal_service: CalendarService | None = None


def set_calendar_service(svc: CalendarService) -> None:
    global _cal_service
    _cal_service = svc


def _get_service() -> CalendarService:
    if _cal_service is None:
        raise RuntimeError("CalendarService not initialized")
    return _cal_service


async def get_calendar_schedule(days: int = 7, tool_context=None) -> dict:
    """Get the user's upcoming calendar schedule.

    Returns user events and Live150-managed events. Uses a cached snapshot
    if the data is within the 7-day window and recent; falls back to a live
    query for larger windows.

    Args:
        days: Number of days to look ahead (default 7, max 30).
    """
    user_id = tool_context.state["user_id"]
    days = min(days, 30)

    async with async_session_factory() as db:
        # Check if connected
        uc = (await db.execute(
            select(UserCalendar).where(
                UserCalendar.user_id == user_id,
                UserCalendar.preferred == True,  # noqa: E712
            )
        )).scalar_one_or_none()

        if uc is None:
            return {"connected": False, "integrations_available": ["google_calendar"]}

        # Try snapshot for <=7 day requests
        if days <= 7 and uc.last_sync_at and uc.last_sync_status == "ok":
            now = datetime.now(timezone.utc)
            stale = (now - uc.last_sync_at).total_seconds() > 7200  # >2h

            stmt = (
                select(CalendarSnapshot)
                .where(
                    CalendarSnapshot.user_id == user_id,
                    CalendarSnapshot.start_at >= now,
                    CalendarSnapshot.start_at <= now + timedelta(days=days),
                )
                .order_by(CalendarSnapshot.start_at)
            )
            rows = (await db.execute(stmt)).scalars().all()

            user_events = [
                {"title": r.title, "start": r.start_at.isoformat(), "end": r.end_at.isoformat(),
                 "all_day": r.all_day, "location": r.location}
                for r in rows if r.source == "user"
            ]
            live150_events = [
                {"title": r.title, "start": r.start_at.isoformat(), "end": r.end_at.isoformat(),
                 "all_day": r.all_day, "event_id": r.event_id, "location": r.location}
                for r in rows if r.source == "live150"
            ]

            return {
                "provider": uc.provider,
                "user_events": user_events,
                "live150_events": live150_events,
                "source": "snapshot",
                "stale": stale,
            }

        # Live query for larger windows or missing snapshot
        try:
            svc = _get_service()
            now = datetime.now(timezone.utc)
            user_events_raw = await svc.list_upcoming_user_events(user_id, db, days=days)
            live150_events_raw = await svc.list_live150_events(
                user_id, db, now, now + timedelta(days=days)
            )

            return {
                "provider": uc.provider,
                "user_events": [
                    {"title": e.title, "start": e.start_at.isoformat(), "end": e.end_at.isoformat(),
                     "all_day": e.all_day, "location": e.location}
                    for e in user_events_raw
                ],
                "live150_events": [
                    {"title": e.title, "start": e.start_at.isoformat(), "end": e.end_at.isoformat(),
                     "all_day": e.all_day, "event_id": e.provider_event_id, "location": e.location}
                    for e in live150_events_raw
                ],
                "source": "live",
                "stale": False,
            }
        except ProviderAuthError:
            return {"connected": True, "needs_reconnect": True, "provider": uc.provider}
        except Exception as e:
            logger.error("Failed to fetch calendar", exc_info=True)
            return {"error": str(e)}


async def create_live150_event(
    title: str,
    start_at: str,
    end_at: str,
    description: str | None = None,
    recurrence: str | None = None,
    tool_context=None,
) -> dict:
    """Create an event in the user's Live150 calendar.

    Events land in a dedicated Live150 sub-calendar, never the user's
    primary calendar.

    Args:
        title: Event title (e.g., "7am Workout").
        start_at: ISO 8601 start time (e.g., "2026-04-19T07:00:00-04:00").
        end_at: ISO 8601 end time (e.g., "2026-04-19T08:00:00-04:00").
        description: Optional event description.
        recurrence: Optional RFC 5545 RRULE (e.g., "FREQ=WEEKLY;BYDAY=MO,WE,FR").
    """
    user_id = tool_context.state["user_id"]

    async with async_session_factory() as db:
        uc = (await db.execute(
            select(UserCalendar).where(
                UserCalendar.user_id == user_id,
                UserCalendar.preferred == True,  # noqa: E712
            )
        )).scalar_one_or_none()

        if uc is None:
            return {"error": "not_connected", "integrations_available": ["google_calendar"]}

        try:
            event_input = EventInput(
                title=title,
                start_at=datetime.fromisoformat(start_at),
                end_at=datetime.fromisoformat(end_at),
                description=description,
                recurrence_rrule=recurrence,
            )
            svc = _get_service()
            event = await svc.create_live150_event(user_id, db, event_input)
            return {
                "created": True,
                "event_id": event.provider_event_id,
                "title": event.title,
                "start": event.start_at.isoformat(),
                "end": event.end_at.isoformat(),
            }
        except ProviderAuthError:
            return {"error": "not_connected", "needs_reconnect": True}
        except Exception as e:
            logger.error("Failed to create event", exc_info=True)
            return {"error": str(e)}


async def delete_live150_event(event_id: str, tool_context=None) -> dict:
    """Delete an event from the Live150 sub-calendar.

    Only deletes events that Live150 created. Cannot delete user-created events.

    Args:
        event_id: The event ID to delete (from get_calendar_schedule).
    """
    user_id = tool_context.state["user_id"]

    async with async_session_factory() as db:
        try:
            svc = _get_service()
            await svc.delete_live150_event(user_id, db, event_id)
            return {"deleted": True, "event_id": event_id}
        except ValueError as e:
            return {"deleted": False, "error": str(e)}
        except ProviderAuthError:
            return {"deleted": False, "needs_reconnect": True}
        except Exception as e:
            logger.error("Failed to delete event", exc_info=True)
            return {"deleted": False, "error": str(e)}


async def find_free_slots(
    duration_minutes: int,
    within_days: int = 7,
    preferred_hours: list[dict] | None = None,
    tool_context=None,
) -> dict:
    """Find free time slots in the user's calendar.

    Checks both user events and Live150 events to find open windows.

    Args:
        duration_minutes: How long the slot needs to be (in minutes).
        within_days: How many days ahead to search (default 7).
        preferred_hours: Optional list of preferred time ranges.
    """
    user_id = tool_context.state["user_id"]

    async with async_session_factory() as db:
        uc = (await db.execute(
            select(UserCalendar).where(
                UserCalendar.user_id == user_id,
                UserCalendar.preferred == True,  # noqa: E712
            )
        )).scalar_one_or_none()

        if uc is None:
            return {"connected": False, "integrations_available": ["google_calendar"]}

        try:
            svc = _get_service()
            slots = await svc.find_free_slots(user_id, db, duration_minutes, within_days)
            return {
                "slots": [
                    {"start": s.isoformat(), "end": e.isoformat()}
                    for s, e in slots
                ]
            }
        except ProviderAuthError:
            return {"connected": True, "needs_reconnect": True}
        except Exception as e:
            logger.error("Failed to find free slots", exc_info=True)
            return {"error": str(e)}


async def check_calendar_connection(tool_context=None) -> dict:
    """Check the status of the user's calendar connection.

    Returns connection status, provider, last sync time, and whether
    the connection needs to be re-established.
    """
    user_id = tool_context.state["user_id"]

    async with async_session_factory() as db:
        uc = (await db.execute(
            select(UserCalendar).where(
                UserCalendar.user_id == user_id,
                UserCalendar.preferred == True,  # noqa: E712
            )
        )).scalar_one_or_none()

        if uc is None:
            return {"connected": False}

        return {
            "connected": True,
            "provider": uc.provider,
            "last_sync_at": uc.last_sync_at.isoformat() if uc.last_sync_at else None,
            "last_sync_status": uc.last_sync_status,
            "needs_reconnect": uc.last_sync_status == "auth_failed",
        }
