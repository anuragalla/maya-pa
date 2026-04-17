from unittest.mock import patch

import pytest

from live150.reminders.parser import ParsedSchedule, parse_schedule, validate_schedule


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
    assert "1" in result.expr  # Monday
    assert validate_schedule(result)


@pytest.mark.asyncio
async def test_parse_every_hour():
    result = await parse_schedule("every hour", "UTC")
    assert result.kind == "interval"
    assert result.expr == "3600"
    assert validate_schedule(result)


@pytest.mark.asyncio
async def test_parse_iso_datetime():
    result = await parse_schedule("2026-04-20T10:00:00+00:00", "UTC")
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
