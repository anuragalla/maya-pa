"""Risky write confirmation logic.

Tools flagged as 'risky' are intercepted before execution.
A pending_confirmation row is created, and the user must approve/reject
via the /confirmations endpoint before the tool executes.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from live150.db.models.pending_confirmation import PendingConfirmation


async def create_confirmation(
    db: AsyncSession,
    user_id: str,
    session_id: uuid.UUID | None,
    tool_name: str,
    tool_args: dict,
    summary: str,
    ttl_minutes: int = 15,
) -> PendingConfirmation:
    """Create a pending confirmation for a risky tool call."""
    row = PendingConfirmation(
        confirmation_id=uuid7(),
        user_id=user_id,
        session_id=session_id,
        tool_name=tool_name,
        tool_args=tool_args,
        summary=summary,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )
    db.add(row)
    await db.flush()
    return row


async def resolve_confirmation(
    db: AsyncSession,
    confirmation_id: uuid.UUID,
    user_id: str,
    approved: bool,
) -> PendingConfirmation | None:
    """Approve or reject a pending confirmation.

    Returns the confirmation row if found and was pending, None otherwise.
    """
    from sqlalchemy import select

    stmt = select(PendingConfirmation).where(
        PendingConfirmation.confirmation_id == confirmation_id,
        PendingConfirmation.user_id == user_id,
        PendingConfirmation.status == "pending",
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if not row:
        return None

    # Check expiry
    if row.expires_at < datetime.now(timezone.utc):
        row.status = "expired"
        row.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        return row

    row.status = "approved" if approved else "rejected"
    row.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    return row
