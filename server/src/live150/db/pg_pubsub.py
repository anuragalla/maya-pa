"""Generic Postgres LISTEN/NOTIFY helper used by the doc and reminder event streams.

Publishers share one long-lived asyncpg connection (lazy singleton) to avoid a
TCP + TLS + auth handshake per NOTIFY. Subscribers still open a dedicated
connection per stream because `add_listener` binds to the connection lifetime.

Caveat: pgbouncer in transaction-pooling mode breaks LISTEN/NOTIFY — the
connection is returned to the pool between statements. In our deploys we talk
to Postgres directly. If that changes this module needs to bypass the pooler.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import asyncpg

from live150.config import settings

logger = logging.getLogger(__name__)

MAX_NOTIFY_PAYLOAD_BYTES = 7000

_publisher_conn: asyncpg.Connection | None = None
_publisher_lock = asyncio.Lock()


def _dsn() -> str:
    return settings.db_url_async.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _get_publisher() -> asyncpg.Connection:
    global _publisher_conn
    if _publisher_conn is not None and not _publisher_conn.is_closed():
        return _publisher_conn
    async with _publisher_lock:
        if _publisher_conn is None or _publisher_conn.is_closed():
            _publisher_conn = await asyncpg.connect(_dsn())
        return _publisher_conn


async def publish(channel: str, envelope: dict[str, Any]) -> None:
    """Emit NOTIFY on the given channel with a JSON-encoded envelope."""
    body = json.dumps(envelope, default=str)
    if len(body.encode("utf-8")) > MAX_NOTIFY_PAYLOAD_BYTES:
        # Strip the `payload` field — subscribers can re-fetch on terminal events.
        trimmed = {k: (v if k != "payload" else None) for k, v in envelope.items()}
        body = json.dumps(trimmed, default=str)
    try:
        conn = await _get_publisher()
        # NOTIFY doesn't accept bind parameters in asyncpg; use pg_notify() which does.
        await conn.execute("SELECT pg_notify($1, $2)", channel, body)
    except Exception:
        logger.exception("pg_publish_failed", extra={"channel": channel})


async def subscribe(channel: str) -> AsyncIterator[dict[str, Any]]:
    """Yield parsed NOTIFY payloads on `channel` until the iterator is closed."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def _on_notify(_conn, _pid, _channel, payload: str) -> None:
        try:
            queue.put_nowait(json.loads(payload))
        except Exception:
            logger.warning("pg_subscribe_bad_payload", extra={"channel": _channel})

    conn = await asyncpg.connect(_dsn())
    try:
        await conn.add_listener(channel, _on_notify)
        while True:
            yield await queue.get()
    finally:
        try:
            await conn.remove_listener(channel, _on_notify)
        except Exception:
            pass
        try:
            await conn.close()
        except Exception:
            pass
