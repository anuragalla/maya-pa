"""Unit tests for live150.db.pg_pubsub."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import pytest

from live150.db import pg_pubsub


class FakeAsyncpgConnection:
    def __init__(self):
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.listener: tuple[str, Any] | None = None
        self.closed: bool = False

    def is_closed(self) -> bool:
        return self.closed

    async def execute(self, query: str, *args: Any) -> None:
        self.executed.append((query, args))

    async def add_listener(self, channel: str, cb) -> None:
        self.listener = (channel, cb)

    async def remove_listener(self, channel: str, cb) -> None:
        if self.listener and self.listener == (channel, cb):
            self.listener = None

    async def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def reset_publisher(monkeypatch):
    monkeypatch.setattr(pg_pubsub, "_publisher_conn", None)
    yield
    monkeypatch.setattr(pg_pubsub, "_publisher_conn", None)


async def test_publish_emits_notify_with_json_body(monkeypatch):
    conn = FakeAsyncpgConnection()
    connect_calls: list[str] = []

    async def fake_connect(dsn: str):
        connect_calls.append(dsn)
        return conn

    monkeypatch.setattr(pg_pubsub.asyncpg, "connect", fake_connect)

    envelope = {"stage": "reading", "label": "hi", "payload": {"x": 1}}
    await pg_pubsub.publish("test_chan", envelope)

    assert len(conn.executed) == 1
    query, args = conn.executed[0]
    assert query == "NOTIFY test_chan, $1"
    assert len(args) == 1
    assert json.loads(args[0]) == envelope

    # Second publish reuses the cached connection.
    await pg_pubsub.publish("test_chan", {"stage": "ready", "label": "done", "payload": None})

    assert len(connect_calls) == 1
    assert len(conn.executed) == 2


async def test_publish_trims_oversized_payload(monkeypatch):
    conn = FakeAsyncpgConnection()

    async def fake_connect(dsn: str):
        return conn

    monkeypatch.setattr(pg_pubsub.asyncpg, "connect", fake_connect)

    big_payload = {"blob": "x" * (pg_pubsub.MAX_NOTIFY_PAYLOAD_BYTES + 100)}
    envelope = {"stage": "ready", "label": "ready-label", "payload": big_payload}

    await pg_pubsub.publish("test_chan", envelope)

    assert len(conn.executed) == 1
    _query, args = conn.executed[0]
    sent = json.loads(args[0])
    assert sent["payload"] is None
    assert sent["stage"] == "ready"
    assert sent["label"] == "ready-label"


async def test_subscribe_yields_parsed_events(monkeypatch):
    conn = FakeAsyncpgConnection()

    async def fake_connect(dsn: str):
        return conn

    monkeypatch.setattr(pg_pubsub.asyncpg, "connect", fake_connect)

    iterator = pg_pubsub.subscribe("test_chan")

    async def _next():
        return await iterator.__anext__()

    next_task = asyncio.create_task(_next())

    # Yield control so the iterator can register the listener.
    for _ in range(5):
        await asyncio.sleep(0)
        if conn.listener is not None:
            break

    assert conn.listener is not None
    channel, cb = conn.listener
    assert channel == "test_chan"

    cb(None, 0, "test_chan", json.dumps({"stage": "reading", "label": "hi"}))

    result = await asyncio.wait_for(next_task, timeout=1.0)
    assert result == {"stage": "reading", "label": "hi"}

    await iterator.aclose()

    assert conn.listener is None
    assert conn.closed is True


async def test_publish_swallows_db_errors(monkeypatch, caplog):
    async def fake_connect(dsn: str):
        raise ConnectionError("db down")

    monkeypatch.setattr(pg_pubsub.asyncpg, "connect", fake_connect)

    caplog.set_level(logging.WARNING, logger=pg_pubsub.logger.name)

    await pg_pubsub.publish("test_chan", {"stage": "reading", "label": "hi", "payload": None})

    matching = [r for r in caplog.records if "pg_publish_failed" in r.message]
    assert matching, f"expected pg_publish_failed log, got {[r.message for r in caplog.records]}"
    assert matching[0].levelno >= logging.WARNING
