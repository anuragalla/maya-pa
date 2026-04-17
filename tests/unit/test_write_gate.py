import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from live150.safety.write_gate import create_confirmation, resolve_confirmation


@pytest.mark.asyncio
async def test_create_confirmation():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    result = await create_confirmation(
        db=db,
        user_id="user-1",
        session_id=uuid.uuid4(),
        tool_name="cancel_workout_plan",
        tool_args={"plan_id": "plan-123"},
        summary="Cancel your workout plan 'Morning Cardio'",
    )

    assert result.user_id == "user-1"
    assert result.tool_name == "cancel_workout_plan"
    assert result.status == "pending"
    assert result.expires_at > datetime.now(timezone.utc)
    db.add.assert_called_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_confirmation_custom_ttl():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    result = await create_confirmation(
        db=db,
        user_id="user-1",
        session_id=None,
        tool_name="create_calendar_event",
        tool_args={},
        summary="Create event",
        ttl_minutes=5,
    )

    # Should expire within ~5 minutes
    expected_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert abs((result.expires_at - expected_expiry).total_seconds()) < 2
