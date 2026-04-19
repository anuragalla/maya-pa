"""Notification endpoints — self-hosted stand-in for Live150 notify API.

POST /api/notifications/push  — receives notifications from fire_reminder via NotifyClient
GET  /api/notifications       — frontend polls for pending notifications per user

When the real Live150 notify API is ready, change LIVE150_NOTIFY_URL in .env
and this file becomes dead code. Zero changes to fire_reminder or NotifyClient.
"""

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Header, Request

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notifications"])

# In-memory store: phone -> list of {payload, timestamp}
_notifications: dict[str, list[dict]] = defaultdict(list)

# Auto-expire after 5 minutes
_TTL_SECONDS = 300


def _prune(phone: str) -> None:
    cutoff = time.time() - _TTL_SECONDS
    _notifications[phone] = [n for n in _notifications[phone] if n["ts"] > cutoff]


@router.post("/push")
async def push_notification(request: Request):
    """Receive a notification from NotifyClient (fire_reminder).

    Expects the same payload shape NotifyClient sends:
    { "user_id": "+19084329987", "type": "reminder", "title": "...", "body": "..." }
    """
    body = await request.json()
    user_id = body.get("user_id", "")
    if not user_id:
        return {"status": "ignored", "reason": "no user_id"}

    _notifications[user_id].append({
        "payload": body,
        "ts": time.time(),
    })
    _prune(user_id)

    logger.info("Notification stored", extra={"user_id": user_id, "type": body.get("type")})
    return {"status": "ok"}


@router.get("")
async def poll_notifications(x_phone_number: str = Header("")):
    """Frontend polls this to check for pending notifications.

    Returns and clears all pending notifications for the user.
    """
    phone = x_phone_number.strip()
    if not phone:
        return {"notifications": []}

    _prune(phone)
    pending = _notifications.pop(phone, [])

    return {
        "notifications": [n["payload"] for n in pending]
    }
