"""Notification endpoints — durable, DB-backed, SSE delivery.

POST /api/v1/notifications/push     — receipt for the scheduler's NotifyClient.
GET  /api/v1/notifications/catchup  — one-shot backlog for tabs opened after a
                                      reminder fired. Returns reminder messages
                                      in the lookback window.
GET  /api/v1/notifications/events   — SSE stream. Frontend subscribes on mount;
                                      new reminders are pushed via Postgres
                                      LISTEN/NOTIFY. No polling.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, Request
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from live150.db.models.chat_message import ChatMessage
from live150.db.session import async_session_factory

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notifications"])

_LOOKBACK = timedelta(minutes=15)


@router.post("/push")
async def push_notification(request: Request):
    body = await request.json()
    logger.info(
        "Notification received",
        extra={"user_id": body.get("user_id"), "type": body.get("type")},
    )
    return {"status": "ok"}


@router.get("/catchup")
async def notifications_catchup(x_phone_number: str = Header("")):
    """Backlog of recent reminder messages — called once on tab open."""
    phone = x_phone_number.strip()
    if not phone:
        return {"notifications": []}

    cutoff = datetime.now(timezone.utc) - _LOOKBACK
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.user_id == phone,
                    ChatMessage.turn_context == "reminder",
                    ChatMessage.created_at >= cutoff,
                )
                .order_by(ChatMessage.created_at.asc())
            )
        ).scalars().all()

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


@router.get("/events")
async def notifications_events(x_phone_number: str = Header("")):
    """SSE stream of reminder notifications for this user."""
    phone = x_phone_number.strip()
    if not phone:
        # Empty stream — client will retry on reconnect.
        async def empty():
            return
            yield  # pragma: no cover

        return EventSourceResponse(empty(), ping=15)

    async def stream():
        from live150.reminders.events import subscribe_notifications

        yield {"event": "ready", "data": json.dumps({"phone": phone})}
        try:
            async for notif in subscribe_notifications(phone):
                yield {"event": "notification", "data": json.dumps(notif)}
        except Exception:
            logger.exception("notifications_sse_failed", extra={"phone": phone})

    return EventSourceResponse(stream(), ping=15)
