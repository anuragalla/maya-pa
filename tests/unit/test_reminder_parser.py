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
async def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        await parse_schedule("gibberish nonsense", "UTC")


def test_validate_invalid_cron():
    s = ParsedSchedule(kind="cron", expr="not a cron", timezone="UTC")
    assert not validate_schedule(s)


def test_validate_invalid_once():
    s = ParsedSchedule(kind="once", expr="not a date", timezone="UTC")
    assert not validate_schedule(s)


def test_validate_invalid_interval():
    s = ParsedSchedule(kind="interval", expr="-1", timezone="UTC")
    assert not validate_schedule(s)
