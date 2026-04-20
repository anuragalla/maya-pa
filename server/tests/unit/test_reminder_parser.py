from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from live150.reminders.parser import ParsedSchedule, parse_schedule, validate_schedule


def _future(seconds: int = 3600) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _past(seconds: int = 3600) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


@pytest.mark.asyncio
async def test_parse_in_hours():
    result = await parse_schedule("in 2 hours", "UTC")
    assert result.kind == "once"
    assert result.timezone == "UTC"
    assert validate_schedule(result)


@pytest.mark.asyncio
async def test_parse_in_minutes():
    result = await parse_schedule("in 30 minutes", "America/New_York")
    assert result.kind == "once"
    assert result.timezone == "America/New_York"
    assert validate_schedule(result)


@pytest.mark.asyncio
async def test_parse_every_day():
    result = await parse_schedule("every day at 9am", "UTC")
    assert result.kind == "cron"
    assert validate_schedule(result)


@pytest.mark.asyncio
async def test_parse_every_monday():
    result = await parse_schedule("every Monday", "UTC")
    assert result.kind == "cron"
    assert result.expr.split()[-1] == "1"  # day-of-week field == Monday
    assert validate_schedule(result)


@pytest.mark.asyncio
async def test_parse_every_hour():
    result = await parse_schedule("every hour", "UTC")
    assert result.kind == "interval"
    assert result.expr == "3600"
    assert validate_schedule(result)


@pytest.mark.asyncio
async def test_parse_iso_datetime():
    # Must be in the future — validate_schedule rejects past `once` timestamps.
    result = await parse_schedule(_future(), "UTC")
    assert result.kind == "once"
    assert validate_schedule(result)


@pytest.mark.asyncio
@patch("live150.reminders.parser._llm_parse")
async def test_regex_miss_falls_through_to_llm(mock_llm):
    """Anything the regex can't handle routes to the Flash-Lite LLM call."""
    mock_llm.return_value = ParsedSchedule(
        kind="cron", expr="0 9 * * 1-5", timezone="America/Los_Angeles"
    )
    result = await parse_schedule("every weekday at 9am", "America/Los_Angeles")
    assert result.kind == "cron"
    assert result.expr == "0 9 * * 1-5"
    mock_llm.assert_awaited_once()


@pytest.mark.asyncio
@patch("live150.reminders.parser._llm_parse")
async def test_llm_invalid_output_raises(mock_llm):
    """If the LLM returns something that fails validation, parse_schedule raises."""
    mock_llm.return_value = ParsedSchedule(kind="cron", expr="garbage", timezone="UTC")
    with pytest.raises(ValueError):
        await parse_schedule("every blue moon", "UTC")


def test_validate_invalid_cron():
    s = ParsedSchedule(kind="cron", expr="not a cron", timezone="UTC")
    assert not validate_schedule(s)


def test_validate_invalid_once():
    s = ParsedSchedule(kind="once", expr="not a date", timezone="UTC")
    assert not validate_schedule(s)


def test_validate_invalid_interval():
    s = ParsedSchedule(kind="interval", expr="-1", timezone="UTC")
    assert not validate_schedule(s)


def test_validate_rejects_past_once():
    """Silent APScheduler misfire-drop was the cost of not validating this —
    LLMs hallucinate dates from their training cutoff, so 'today at 3pm' can
    come back as a year-old timestamp. Surface it instead of dropping."""
    s = ParsedSchedule(kind="once", expr=_past(3600), timezone="UTC")
    assert not validate_schedule(s)


def test_validate_accepts_future_once():
    s = ParsedSchedule(kind="once", expr=_future(60), timezone="UTC")
    assert validate_schedule(s)


def test_validate_once_naive_datetime_treated_as_utc():
    # Naive ISO string (no tz suffix). Parser must not reject solely on tz.
    future_naive = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None).isoformat()
    s = ParsedSchedule(kind="once", expr=future_naive, timezone="UTC")
    assert validate_schedule(s)


@pytest.mark.asyncio
async def test_llm_parser_injects_current_time():
    """Regression test for the root cause: LLM must receive 'now' in its
    prompt, otherwise it hallucinates a date from training data."""
    # Patch the genai client so we can inspect the prompt sent to Flash-Lite.
    fake_resp = MagicMock()
    fake_resp.parsed = ParsedSchedule(
        kind="once", expr=_future(120), timezone="UTC",
    )
    fake_client = MagicMock()
    fake_client.aio.models.generate_content = AsyncMock(return_value=fake_resp)

    with patch("live150.reminders.parser.get_genai_client", return_value=fake_client):
        await parse_schedule("tomorrow morning", "UTC")

    prompt = fake_client.aio.models.generate_content.await_args.kwargs["contents"]
    assert "current moment" in prompt.lower()
    # Today's date (UTC) must appear in the prompt.
    today = datetime.now(timezone.utc).date().isoformat()
    assert today in prompt, f"Expected {today} in prompt; got:\n{prompt}"
