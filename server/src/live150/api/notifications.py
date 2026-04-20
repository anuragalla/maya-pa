"""Notification endpoints — durable, DB-backed.

POST /api/notifications/push  — receives a push from fire_reminder. No-op for
                                 chat-linked payloads (the chat_message row
                                 is the source of truth); returns 200 so the
                                 scheduler's NotifyClient is happy.
GET  /api/notifications        — returns reminder chat_messages created in
                                 the lookback window. Frontend dedupes by
                                 message_id so repeated polls are safe.

The previous in-memory store was lost on every agent recreate and on the
5-minute TTL prune — users only saw reminders on full-page refresh (which
reloads chat history from the DB). The DB-backed model survives restarts
and tab-throttling, which is what users actually need.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from live150.db.models.chat_message import ChatMessage
from live150.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notifications"])

# How far back to look for un-acknowledged reminder messages. Long enough to
# cover a tab being backgrounded, short enough that old reminders don't
# replay when a user logs in fresh.
_LOOKBACK = timedelta(minutes=15)


@router.post("/push")
async def push_notification(request: Request):
    """Accepted for backward-compat with the scheduler's NotifyClient.

    fire_reminder already writes the reminder as a chat_message before
    calling here, so this endpoint is effectively a receipt.
    """
    body = await request.json()
    logger.info(
        "Notification received",
        extra={"user_id": body.get("user_id"), "type": body.get("type")},
    )
    return {"status": "ok"}


@router.get("")
async def poll_notifications(
    x_phone_number: str = Header(""),
    db: AsyncSession = Depends(get_db),
):
    """Return recent reminder chat_messages for the user.

    Frontend dedupes by message_id, so returning the same row across polls
    is safe — it just won't re-inject the message.
    """
    phone = x_phone_number.strip()
    if not phone:
        return {"notifications": []}

    cutoff = datetime.now(timezone.utc) - _LOOKBACK
    stmt = (
        select(ChatMessage)
        .where(
            ChatMessage.user_id == phone,
            ChatMessage.turn_context == "reminder",
            ChatMessage.created_at >= cutoff,
        )
        .order_by(ChatMessage.created_at.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "notifications": [
            {
                "type": "reminder",
                "message_id": str(r.message_id),
                "body": r.content if isinstance(r.content, str) else str(r.content),
                "title": "Reminder",
            }
            for r in rows
        ]
    }
