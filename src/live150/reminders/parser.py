"""Parse natural language schedule expressions into structured schedules.

Uses a small LLM call (Flash-Lite) for parsing, validated with croniter/datetime.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from croniter import croniter

logger = logging.getLogger(__name__)


@dataclass
class ParsedSchedule:
    kind: Literal["once", "cron", "interval"]
    expr: str  # ISO datetime or cron string
    timezone: str  # IANA tz name


def validate_schedule(schedule: ParsedSchedule) -> bool:
    """Validate a parsed schedule expression."""
    if schedule.kind == "once":
        try:
            datetime.fromisoformat(schedule.expr)
            return True
        except ValueError:
            return False
    elif schedule.kind == "cron":
        try:
            croniter(schedule.expr)
            return True
        except (ValueError, KeyError):
            return False
    elif schedule.kind == "interval":
        # Interval is in seconds
        try:
            seconds = int(schedule.expr)
            return seconds > 0
        except ValueError:
            return False
    return False


async def parse_schedule(
    text: str,
    user_timezone: str = "UTC",
) -> ParsedSchedule:
    """Parse a natural language schedule expression.

    In production, this uses a Flash-Lite LLM call with strict JSON output.
    For now, implements basic pattern matching as a fallback.
    """
    text_lower = text.lower().strip()

    # Basic pattern matching (fallback before LLM is wired)
    if text_lower.startswith("in "):
        # "in 2 hours", "in 30 minutes"
        from datetime import timedelta, timezone as tz

        parts = text_lower.removeprefix("in ").split()
        if len(parts) >= 2:
            try:
                amount = int(parts[0])
                unit = parts[1].rstrip("s")  # hours -> hour
                if unit == "hour":
                    dt = datetime.now(tz.utc) + timedelta(hours=amount)
                elif unit == "minute":
                    dt = datetime.now(tz.utc) + timedelta(minutes=amount)
                elif unit == "day":
                    dt = datetime.now(tz.utc) + timedelta(days=amount)
                else:
                    raise ValueError(f"Unknown unit: {unit}")
                return ParsedSchedule(kind="once", expr=dt.isoformat(), timezone=user_timezone)
            except (ValueError, IndexError):
                pass

    if "every" in text_lower:
        # Basic cron patterns
        if "every day" in text_lower or "daily" in text_lower:
            return ParsedSchedule(kind="cron", expr="0 9 * * *", timezone=user_timezone)
        if "every monday" in text_lower:
            return ParsedSchedule(kind="cron", expr="0 9 * * 1", timezone=user_timezone)
        if "every hour" in text_lower:
            return ParsedSchedule(kind="interval", expr="3600", timezone=user_timezone)

    # Fallback: try to parse as ISO datetime
    try:
        datetime.fromisoformat(text)
        return ParsedSchedule(kind="once", expr=text, timezone=user_timezone)
    except ValueError:
        pass

    # TODO(llm-parser): Use Flash-Lite call for complex expressions
    raise ValueError(f"Could not parse schedule expression: {text}")
