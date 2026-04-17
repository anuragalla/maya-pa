"""Parse natural-language schedule expressions into structured schedules.

Two-stage: a cheap deterministic regex path handles "in 2 hours" / "daily" /
"every monday" etc. Anything it can't handle falls through to a single
Flash-Lite call with a Pydantic `response_schema`, so the model is forced to
return schema-valid JSON. Validation via croniter / datetime happens after.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

from croniter import croniter
from pydantic import BaseModel, Field

from live150.agent.genai_client import get_genai_client
from live150.config import settings

logger = logging.getLogger(__name__)


class ParsedSchedule(BaseModel):
    kind: Literal["once", "cron", "interval"] = Field(
        ..., description="`once` for single timestamps, `cron` for recurring patterns, `interval` for seconds."
    )
    expr: str = Field(
        ...,
        description=(
            "For kind=once: ISO-8601 datetime (timezone-aware). "
            "For kind=cron: a 5-field cron expression. "
            "For kind=interval: an integer number of seconds as a string."
        ),
    )
    timezone: str = Field(..., description="IANA timezone name, e.g. America/Los_Angeles.")


def validate_schedule(schedule: ParsedSchedule) -> bool:
    """Validate a parsed schedule expression."""
    if schedule.kind == "once":
        try:
            datetime.fromisoformat(schedule.expr)
            return True
        except ValueError:
            return False
    if schedule.kind == "cron":
        try:
            croniter(schedule.expr)
            return True
        except (ValueError, KeyError):
            return False
    if schedule.kind == "interval":
        try:
            return int(schedule.expr) > 0
        except ValueError:
            return False
    return False


def _regex_parse(text: str, user_timezone: str) -> ParsedSchedule | None:
    """Cheap deterministic path. Returns None if the expression needs the LLM."""
    text_lower = text.lower().strip()

    if text_lower.startswith("in "):
        parts = text_lower.removeprefix("in ").split()
        if len(parts) >= 2:
            try:
                amount = int(parts[0])
                unit = parts[1].rstrip("s")
                deltas = {"hour": "hours", "minute": "minutes", "day": "days"}
                if unit in deltas:
                    dt = datetime.now(UTC) + timedelta(**{deltas[unit]: amount})
                    return ParsedSchedule(kind="once", expr=dt.isoformat(), timezone=user_timezone)
            except (ValueError, IndexError):
                pass

    if "every" in text_lower:
        if "every day" in text_lower or "daily" in text_lower:
            return ParsedSchedule(kind="cron", expr="0 9 * * *", timezone=user_timezone)
        if "every monday" in text_lower:
            return ParsedSchedule(kind="cron", expr="0 9 * * 1", timezone=user_timezone)
        if "every hour" in text_lower:
            return ParsedSchedule(kind="interval", expr="3600", timezone=user_timezone)

    try:
        datetime.fromisoformat(text)
        return ParsedSchedule(kind="once", expr=text, timezone=user_timezone)
    except ValueError:
        return None


_LLM_PROMPT = (
    "Parse the user's natural-language schedule into a structured schedule. "
    "Prefer `cron` for anything recurring (e.g. 'every Monday 9am'), `once` for "
    "absolute or relative timestamps, and `interval` only when they explicitly "
    "say 'every N minutes/hours'. Always emit an IANA timezone; if none is given, "
    "use the user's timezone: {user_timezone}.\n\n"
    "User input: {text}"
)


async def _llm_parse(text: str, user_timezone: str) -> ParsedSchedule:
    """Call Flash-Lite once with a Pydantic response_schema."""
    client = get_genai_client(settings.lite_model)
    resp = await client.aio.models.generate_content(
        model=settings.lite_model,
        contents=_LLM_PROMPT.format(user_timezone=user_timezone, text=text),
        config={
            "response_mime_type": "application/json",
            "response_schema": ParsedSchedule,
        },
    )
    parsed = resp.parsed
    if parsed is None:
        raise ValueError(f"LLM did not return a parseable schedule for {text!r}")
    return parsed


async def parse_schedule(text: str, user_timezone: str = "UTC") -> ParsedSchedule:
    """Parse a natural language schedule expression.

    Regex fast-path first; falls through to a single Flash-Lite call with a
    Pydantic response_schema for anything the regex cannot handle.
    """
    regex_hit = _regex_parse(text, user_timezone)
    if regex_hit is not None and validate_schedule(regex_hit):
        return regex_hit

    schedule = await _llm_parse(text, user_timezone)
    if not validate_schedule(schedule):
        raise ValueError(
            f"Parsed schedule failed validation: kind={schedule.kind} expr={schedule.expr!r}"
        )
    return schedule
