"""Confirmation endpoints for risky tool calls."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from live150.auth.middleware import AuthedUser, require_user
from live150.db.models.pending_confirmation import PendingConfirmation
from live150.db.session import get_db
from live150.safety.write_gate import resolve_confirmation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/confirmations", tags=["confirmations"])


@router.get("")
async def list_pending(
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """List pending confirmations for the user."""
    stmt = (
        select(PendingConfirmation)
        .where(
            PendingConfirmation.user_id == user.user_id,
            PendingConfirmation.status == "pending",
        )
        .order_by(PendingConfirmation.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return {
        "confirmations": [
            {
                "confirmation_id": str(r.confirmation_id),
                "tool_name": r.tool_name,
                "tool_args": r.tool_args,
                "summary": r.summary,
                "created_at": r.created_at.isoformat(),
                "expires_at": r.expires_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.post("/{confirmation_id}/approve")
async def approve(
    confirmation_id: uuid.UUID,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending confirmation and execute the tool."""
    row = await resolve_confirmation(db, confirmation_id, user.user_id, approved=True)
    if not row:
        raise HTTPException(status_code=404, detail="Confirmation not found or already resolved")

    if row.status == "expired":
        raise HTTPException(status_code=410, detail="Confirmation has expired")

    await db.commit()

    # TODO: Execute the tool and stream result back / write to session
    return {"status": "approved", "tool_name": row.tool_name}


@router.post("/{confirmation_id}/reject")
async def reject(
    confirmation_id: uuid.UUID,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending confirmation."""
    row = await resolve_confirmation(db, confirmation_id, user.user_id, approved=False)
    if not row:
        raise HTTPException(status_code=404, detail="Confirmation not found or already resolved")

    await db.commit()
    return {"status": "rejected"}
