"""CalendarProvider Protocol and error hierarchy.

Every calendar provider (Google, Microsoft, Apple) implements this Protocol.
Service and tool code depend only on this interface, never on provider internals.
"""

from datetime import datetime
from typing import Protocol

from live150.calendar.types import Calendar, Event, EventInput, FreeBusy


class CalendarProvider(Protocol):
    """Provider-agnostic calendar interface."""

    provider_name: str

    async def list_calendars(self) -> list[Calendar]: ...

    async def ensure_managed_calendar(
        self, summary: str, timezone: str
    ) -> str:
        """Return calendar_id of the Live150-owned calendar. Create if missing."""
        ...

    async def list_events(
        self,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        *,
        fields_mask: list[str] | None = None,
    ) -> list[Event]: ...

    async def create_event(self, calendar_id: str, event: EventInput) -> Event: ...

    async def delete_event(self, calendar_id: str, event_id: str) -> None: ...

    async def freebusy(
        self,
        calendar_ids: list[str],
        time_min: datetime,
        time_max: datetime,
    ) -> FreeBusy: ...


class ProviderError(Exception):
    pass


class ProviderAuthError(ProviderError):
    pass


class ProviderQuotaError(ProviderError):
    pass


class ProviderNotFoundError(ProviderError):
    pass


class ProviderPermissionError(ProviderError):
    pass
