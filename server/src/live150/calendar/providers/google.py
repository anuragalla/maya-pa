"""Google Calendar provider — implements CalendarProvider Protocol.

All Google API specifics stay in this file. Nothing outside calendar/providers/
should import from googleapiclient.
"""

import asyncio
import logging
from datetime import datetime, timezone

from google.auth.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from live150.calendar.provider import (
    ProviderAuthError,
    ProviderError,
    ProviderNotFoundError,
    ProviderPermissionError,
    ProviderQuotaError,
)
from live150.calendar.types import Calendar, Event, EventInput, FreeBusy

logger = logging.getLogger(__name__)

MANAGED_CALENDAR_SUMMARY = "Live150"


def _is_transient(exc: BaseException) -> bool:
    return isinstance(exc, HttpError) and exc.resp.status >= 500


class GoogleCalendarClient:
    """Implements CalendarProvider for Google Calendar API v3."""

    provider_name = "google"

    def __init__(self, credentials: Credentials) -> None:
        self._creds = credentials
        self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, max=2),
        reraise=True,
    )
    async def _run(self, request):
        """Execute a sync Google API request on a thread."""
        try:
            return await asyncio.to_thread(request.execute)
        except HttpError as e:
            _raise_provider_error(e)

    async def list_calendars(self) -> list[Calendar]:
        result = await self._run(self._service.calendarList().list())
        return [
            Calendar(
                provider="google",
                calendar_id=item["id"],
                summary=item.get("summary", ""),
                timezone=item.get("timeZone", "UTC"),
                is_managed=item.get("summary") == MANAGED_CALENDAR_SUMMARY
                and item.get("accessRole") == "owner",
            )
            for item in result.get("items", [])
        ]

    async def ensure_managed_calendar(self, summary: str, timezone: str) -> str:
        calendars = await self.list_calendars()
        for cal in calendars:
            if cal.summary == summary and cal.is_managed:
                return cal.calendar_id

        # Create it
        body = {"summary": summary, "timeZone": timezone}
        result = await self._run(self._service.calendars().insert(body=body))
        logger.info("Created managed calendar %s", result["id"])
        return result["id"]

    async def list_events(
        self,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        *,
        fields_mask: list[str] | None = None,
    ) -> list[Event]:
        params: dict = {
            "calendarId": calendar_id,
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": 250,
        }
        if fields_mask:
            params["fields"] = f"items({','.join(fields_mask)})"

        result = await self._run(self._service.events().list(**params))
        managed = await self._is_managed_calendar(calendar_id)
        return [_parse_event(item, calendar_id, managed) for item in result.get("items", [])]

    async def create_event(self, calendar_id: str, event: EventInput) -> Event:
        body: dict = {
            "summary": event.title,
            "start": _dt_body(event.start_at),
            "end": _dt_body(event.end_at),
        }
        if event.description:
            body["description"] = event.description
        if event.location:
            body["location"] = event.location
        if event.recurrence_rrule:
            body["recurrence"] = [f"RRULE:{event.recurrence_rrule}"]

        result = await self._run(
            self._service.events().insert(calendarId=calendar_id, body=body)
        )
        return _parse_event(result, calendar_id, is_managed=True)

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        try:
            await self._run(
                self._service.events().delete(calendarId=calendar_id, eventId=event_id)
            )
        except ProviderNotFoundError:
            pass  # Already gone — success

    async def freebusy(
        self,
        calendar_ids: list[str],
        time_min: datetime,
        time_max: datetime,
    ) -> FreeBusy:
        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": cid} for cid in calendar_ids],
        }
        result = await self._run(self._service.freebusy().query(body=body))

        windows: list[tuple[datetime, datetime]] = []
        for cal_data in result.get("calendars", {}).values():
            for busy in cal_data.get("busy", []):
                windows.append((
                    datetime.fromisoformat(busy["start"]),
                    datetime.fromisoformat(busy["end"]),
                ))
        windows.sort(key=lambda w: w[0])
        return FreeBusy(busy_windows=windows)

    async def _is_managed_calendar(self, calendar_id: str) -> bool:
        calendars = await self.list_calendars()
        return any(c.calendar_id == calendar_id and c.is_managed for c in calendars)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dt_body(dt: datetime) -> dict:
    """Convert a datetime to Google Calendar API start/end body."""
    return {"dateTime": dt.isoformat(), "timeZone": dt.tzinfo.key if hasattr(dt.tzinfo, "key") else "UTC"}


def _parse_event(item: dict, calendar_id: str, is_managed: bool) -> Event:
    start = item.get("start", {})
    end = item.get("end", {})

    if "dateTime" in start:
        start_at = datetime.fromisoformat(start["dateTime"])
        end_at = datetime.fromisoformat(end["dateTime"])
        all_day = False
    else:
        start_at = datetime.fromisoformat(start["date"]).replace(tzinfo=timezone.utc)
        end_at = datetime.fromisoformat(end["date"]).replace(tzinfo=timezone.utc)
        all_day = True

    return Event(
        provider="google",
        provider_event_id=item["id"],
        calendar_id=calendar_id,
        title=item.get("summary", "(no title)"),
        start_at=start_at,
        end_at=end_at,
        all_day=all_day,
        location=item.get("location"),
        is_managed=is_managed,
    )


def _raise_provider_error(e: HttpError) -> None:
    status = e.resp.status
    if status in (401, 403) and "insufficient" in str(e).lower():
        raise ProviderPermissionError(str(e)) from e
    if status == 401:
        raise ProviderAuthError(str(e)) from e
    if status == 403:
        raise ProviderQuotaError(str(e)) from e
    if status in (404, 410):
        raise ProviderNotFoundError(str(e)) from e
    raise ProviderError(str(e)) from e
