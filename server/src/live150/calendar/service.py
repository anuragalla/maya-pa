"""CalendarService — provider-agnostic calendar operations.

Delegates to CalendarProvider via the registry. Tools call this, never
the provider directly.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from live150.calendar.provider import CalendarProvider, ProviderAuthError
from live150.calendar.registry import CalendarProviderRegistry
from live150.calendar.types import Event, EventInput, FreeBusy
from live150.db.models.calendar_snapshot import CalendarSnapshot
from live150.db.models.user_calendar import UserCalendar

logger = logging.getLogger(__name__)


class CalendarService:
    def __init__(self, registry: CalendarProviderRegistry) -> None:
        self._registry = registry

    # ------------------------------------------------------------------
    # Sub-calendar management
    # ------------------------------------------------------------------

    async def ensure_live150_calendar(
        self, user_id: str, db: AsyncSession, *, provider_name: str | None = None
    ) -> str:
        """Ensure the Live150 sub-calendar exists. Returns calendar_id."""
        client, uc = await self._resolve(user_id, db, provider_name)
        if uc.calendar_id:
            return uc.calendar_id

        tz = uc.timezone or "UTC"
        cal_id = await client.ensure_managed_calendar("Live150", tz)
        uc.calendar_id = cal_id
        await db.commit()
        return cal_id

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def list_upcoming_user_events(
        self, user_id: str, db: AsyncSession, days: int = 30, *, provider_name: str | None = None
    ) -> list[Event]:
        client, uc = await self._resolve(user_id, db, provider_name)
        now = datetime.now(timezone.utc)
        # Get user's primary calendar events
        calendars = await client.list_calendars()
        primary = next((c for c in calendars if c.calendar_id == "primary" or not c.is_managed), None)
        if not primary:
            return []
        return await client.list_events(
            primary.calendar_id,
            now,
            now + timedelta(days=days),
            fields_mask=["id", "summary", "start", "end", "location"],
        )

    async def list_live150_events(
        self, user_id: str, db: AsyncSession, time_min: datetime, time_max: datetime,
        *, provider_name: str | None = None
    ) -> list[Event]:
        client, uc = await self._resolve(user_id, db, provider_name)
        cal_id = await self.ensure_live150_calendar(user_id, db, provider_name=provider_name)
        return await client.list_events(cal_id, time_min, time_max)

    # ------------------------------------------------------------------
    # Write operations (Live150 sub-calendar only)
    # ------------------------------------------------------------------

    async def create_live150_event(
        self, user_id: str, db: AsyncSession, event: EventInput,
        *, provider_name: str | None = None
    ) -> Event:
        client, uc = await self._resolve(user_id, db, provider_name)
        cal_id = await self.ensure_live150_calendar(user_id, db, provider_name=provider_name)
        return await client.create_event(cal_id, event)

    async def delete_live150_event(
        self, user_id: str, db: AsyncSession, event_id: str,
        *, provider_name: str | None = None
    ) -> None:
        """Delete an event only if it belongs to the Live150 sub-calendar."""
        client, uc = await self._resolve(user_id, db, provider_name)
        cal_id = await self.ensure_live150_calendar(user_id, db, provider_name=provider_name)

        # Belt-and-suspenders: verify event is in the managed calendar
        now = datetime.now(timezone.utc)
        events = await client.list_events(cal_id, now - timedelta(days=365), now + timedelta(days=365))
        if not any(e.provider_event_id == event_id for e in events):
            raise ValueError("Event not found in Live150 calendar — refusing to delete")

        await client.delete_event(cal_id, event_id)

    # ------------------------------------------------------------------
    # Scheduling helpers
    # ------------------------------------------------------------------

    async def find_live150_conflict(
        self, user_id: str, db: AsyncSession, start_at: datetime, end_at: datetime,
        *, provider_name: str | None = None
    ) -> Event | None:
        """Check for overlapping Live150 events. Returns first conflict or None."""
        events = await self.list_live150_events(user_id, db, start_at, end_at, provider_name=provider_name)
        for ev in events:
            if ev.start_at < end_at and ev.end_at > start_at:
                return ev
        return None

    async def find_free_slots(
        self, user_id: str, db: AsyncSession, duration_minutes: int,
        within_days: int = 7,
        preferred_hours: list[tuple[str, str, str]] | None = None,
        *, provider_name: str | None = None,
    ) -> list[tuple[datetime, datetime]]:
        """Find free slots using freebusy across user + Live150 calendars."""
        client, uc = await self._resolve(user_id, db, provider_name)
        cal_id = await self.ensure_live150_calendar(user_id, db, provider_name=provider_name)

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=within_days)

        # Query freebusy for primary + managed calendar
        fb = await client.freebusy(["primary", cal_id], now, end)

        # Build free windows
        duration = timedelta(minutes=duration_minutes)
        slots: list[tuple[datetime, datetime]] = []

        # Merge busy windows and find gaps
        busy = sorted(fb.busy_windows, key=lambda w: w[0])

        # Start scanning from now
        cursor = now
        for busy_start, busy_end in busy:
            if cursor + duration <= busy_start:
                slots.append((cursor, cursor + duration))
                if len(slots) >= 10:
                    break
            cursor = max(cursor, busy_end)

        # Check after last busy window
        if len(slots) < 10 and cursor + duration <= end:
            slots.append((cursor, cursor + duration))

        return slots

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def sync_snapshot(self, user_id: str, db: AsyncSession, *, provider_name: str | None = None) -> None:
        """Refresh the 7-day calendar snapshot for a user."""
        try:
            client, uc = await self._resolve(user_id, db, provider_name)
        except (ValueError, ProviderAuthError) as e:
            logger.warning("Cannot sync calendar for user=%s: %s", user_id, e)
            # Mark auth failure if applicable
            stmt = select(UserCalendar).where(UserCalendar.user_id == user_id)
            if provider_name:
                stmt = stmt.where(UserCalendar.provider == provider_name)
            else:
                stmt = stmt.where(UserCalendar.preferred == True)  # noqa: E712
            uc_row = (await db.execute(stmt)).scalar_one_or_none()
            if uc_row and isinstance(e, ProviderAuthError):
                uc_row.last_sync_status = "auth_failed"
                uc_row.last_sync_error = str(e)
                await db.commit()
            return

        provider = uc.provider
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(days=7)

        try:
            # Fetch user calendar events (title, times only — privacy minimization)
            calendars = await client.list_calendars()
            primary = next((c for c in calendars if not c.is_managed), None)

            user_events: list[Event] = []
            if primary:
                user_events = await client.list_events(
                    primary.calendar_id, now, window_end,
                    fields_mask=["id", "summary", "start", "end"],
                )

            # Fetch Live150 events
            live150_events: list[Event] = []
            if uc.calendar_id:
                live150_events = await client.list_events(uc.calendar_id, now, window_end)

            # Delete old snapshot rows and re-insert
            await db.execute(
                delete(CalendarSnapshot).where(
                    CalendarSnapshot.user_id == user_id,
                    CalendarSnapshot.provider == provider,
                )
            )

            for ev in user_events:
                db.add(CalendarSnapshot(
                    snapshot_id=uuid7(),
                    user_id=user_id,
                    provider=provider,
                    source="user",
                    event_id=ev.provider_event_id,
                    calendar_id=ev.calendar_id,
                    title=ev.title,
                    start_at=ev.start_at,
                    end_at=ev.end_at,
                    all_day=ev.all_day,
                    location=ev.location,
                ))

            for ev in live150_events:
                db.add(CalendarSnapshot(
                    snapshot_id=uuid7(),
                    user_id=user_id,
                    provider=provider,
                    source="live150",
                    event_id=ev.provider_event_id,
                    calendar_id=ev.calendar_id,
                    title=ev.title,
                    start_at=ev.start_at,
                    end_at=ev.end_at,
                    all_day=ev.all_day,
                    location=ev.location,
                ))

            uc.last_sync_at = now
            uc.last_sync_status = "ok"
            uc.last_sync_error = None
            await db.commit()
            logger.info("Synced calendar snapshot for user=%s provider=%s", user_id, provider)

        except ProviderAuthError as e:
            uc.last_sync_status = "auth_failed"
            uc.last_sync_error = str(e)
            await db.commit()
            logger.warning("Auth failed during sync for user=%s: %s", user_id, e)
        except Exception as e:
            uc.last_sync_status = "other"
            uc.last_sync_error = str(e)
            await db.commit()
            logger.error("Sync failed for user=%s: %s", user_id, e, exc_info=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _resolve(
        self, user_id: str, db: AsyncSession, provider_name: str | None
    ) -> tuple[CalendarProvider, UserCalendar]:
        """Resolve the CalendarProvider + UserCalendar row for a user."""
        if provider_name:
            client = await self._registry.get_provider(user_id, provider_name, db)
            stmt = select(UserCalendar).where(
                UserCalendar.user_id == user_id,
                UserCalendar.provider == provider_name,
            )
        else:
            client = await self._registry.get_active_provider(user_id, db)
            stmt = select(UserCalendar).where(
                UserCalendar.user_id == user_id,
                UserCalendar.preferred == True,  # noqa: E712
            )
        uc = (await db.execute(stmt)).scalar_one_or_none()
        if uc is None:
            raise ValueError(f"No user_calendar row for user={user_id}")
        return client, uc
