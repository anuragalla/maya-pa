"""Per-document event channel wrapper over `db.pg_pubsub`."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from live150.db import pg_pubsub


def _channel_for(document_id: str) -> str:
    try:
        canonical = uuid.UUID(document_id).hex
    except ValueError:
        canonical = document_id.replace("-", "_")
    return f"doc_{canonical}"


async def publish_doc_event(
    document_id: str,
    stage: str,
    label: str,
    payload: dict[str, Any] | None = None,
) -> None:
    await pg_pubsub.publish(
        _channel_for(document_id),
        {"stage": stage, "label": label, "payload": payload},
    )


def subscribe_doc_events(document_id: str) -> AsyncIterator[dict[str, Any]]:
    return pg_pubsub.subscribe(_channel_for(document_id))
