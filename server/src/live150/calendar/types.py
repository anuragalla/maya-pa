"""Neutral domain types for calendar integration.

These types are provider-agnostic. Nothing outside calendar/providers/
should import from googleapiclient or similar.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Calendar:
    provider: str
    calendar_id: str
    summary: str
    timezone: str
    is_managed: bool  # true = Live150-owned sub-calendar


@dataclass
class Event:
    provider: str
    provider_event_id: str
    calendar_id: str
    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool
    location: str | None
    is_managed: bool  # true = we created it in the Live150 sub-calendar


@dataclass
class EventInput:
    title: str
    start_at: datetime
    end_at: datetime
    description: str | None = None
    location: str | None = None
    recurrence_rrule: str | None = None  # RFC 5545 RRULE


@dataclass
class FreeBusy:
    busy_windows: list[tuple[datetime, datetime]] = field(default_factory=list)
