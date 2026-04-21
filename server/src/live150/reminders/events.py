"""Per-user notification channel wrapper over `db.pg_pubsub`.

Channel identifier is a sha256-hash prefix of the phone number because PG
identifiers can't contain `+` or `/`.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from typing import Any

from live150.db import pg_pubsub


def _channel_for(phone: str) -> str:
    digest = hashlib.sha256(phone.encode("utf-8")).hexdigest()[:16]
    return f"notif_{digest}"


async def publish_notification(phone: str, payload: dict[str, Any]) -> None:
    await pg_pubsub.publish(_channel_for(phone), payload)


def subscribe_notifications(phone: str) -> AsyncIterator[dict[str, Any]]:
    return pg_pubsub.subscribe(_channel_for(phone))
