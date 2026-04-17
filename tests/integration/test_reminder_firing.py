"""Integration test for reminder firing.

Creates a reminder scheduled 2s in the future, waits, and verifies
fire_reminder ran and the notify API was called.
"""

import pytest


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_reminder_fires_on_schedule():
    """Reminder fires within expected timeframe."""
    pass


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_reminder_updates_last_fired():
    """After firing, last_fired_at is updated."""
    pass


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_cancelled_reminder_does_not_fire():
    """Cancelled reminders are skipped."""
    pass
