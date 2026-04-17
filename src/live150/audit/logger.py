"""Audit log writer."""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from live150.db.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def write_audit(
    db: AsyncSession,
    user_id: str,
    event_type: str,
    event_payload: dict,
    session_id: uuid.UUID | None = None,
    model: str | None = None,
    latency_ms: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
) -> None:
    """Append a row to the audit log."""
    row = AuditLog(
        user_id=user_id,
        session_id=session_id,
        event_type=event_type,
        event_payload=event_payload,
        model=model,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    db.add(row)
    await db.flush()
