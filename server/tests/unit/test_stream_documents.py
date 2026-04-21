"""Unit tests for stream.py document attachment + history join behavior."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from uuid6 import uuid7

from live150.api import stream as stream_module
from live150.db.session import get_db
from live150.main import app


class FakeResult:
    def __init__(self, obj: Any):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj

    def scalars(self):
        class _S:
            def __init__(self, items):
                self._items = items

            def all(self):
                return self._items

        items = self._obj if isinstance(self._obj, list) else ([self._obj] if self._obj else [])
        return _S(items)


class FakeSession:
    def __init__(self):
        self.added: list[Any] = []
        self.committed = 0
        self.executed: list[Any] = []
        self.execute_results: list[Any] = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed += 1

    async def execute(self, stmt):
        self.executed.append(stmt)
        if self.execute_results:
            return self.execute_results.pop(0)
        return FakeResult(None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _fake_event(text="ok"):
    part = SimpleNamespace(
        text=text,
        thought=False,
        function_call=None,
        function_response=None,
    )
    return SimpleNamespace(content=SimpleNamespace(parts=[part]))


class FakeRunner:
    def __init__(self):
        self.calls: list[dict] = []

    def run_turn(self, **kwargs):
        self.calls.append(kwargs)

        async def _gen():
            yield _fake_event("hello")

        return _gen()


class FakeLive150Client:
    async def impersonate(self, phone):
        return SimpleNamespace(access_token="fake-token")


async def test_chat_with_documents_prepends_framing(monkeypatch):
    phone = "+19084329987"
    doc_uuid = uuid.uuid4()
    fake_doc = SimpleNamespace(
        document_id=doc_uuid,
        original_filename="lab.pdf",
        doc_type="lab_result",
        status="processing",
        summary_detailed=None,
        chat_message_id=None,
    )

    # Sessions consumed in order by stream_chat:
    #   1) chat_session existence check (returns existing session)
    #   2) user message persist (selects docs + adds ChatMessage)
    #   3) assistant message persist at the end
    session1 = FakeSession()
    session1.execute_results = [FakeResult(SimpleNamespace(session_id="exists"))]

    session2 = FakeSession()
    session2.execute_results = [FakeResult([fake_doc])]

    session3 = FakeSession()

    sessions = iter([session1, session2, session3])

    def fake_factory():
        return next(sessions)

    monkeypatch.setattr(stream_module, "async_session_factory", fake_factory)
    monkeypatch.setattr(stream_module, "get_client", lambda: FakeLive150Client())

    fake_runner = FakeRunner()
    monkeypatch.setattr(stream_module, "_get_runner", lambda: fake_runner)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/stream/chat",
            json={
                "messages": [{"role": "user", "content": "analyze this"}],
                "documents": [str(doc_uuid)],
            },
            headers={"X-Phone-Number": phone},
        )
        assert resp.status_code == 200
        await resp.aread()

    assert len(fake_runner.calls) == 1
    framed = fake_runner.calls[0]["message"]
    assert framed.startswith("[Attached documents:")
    assert "lab.pdf" in framed
    assert f"id={doc_uuid}" in framed
    assert "use get_document(id) to inspect" in framed
    assert framed.rstrip().endswith("analyze this")

    # chat_message_id was set on the fake doc to match the inserted ChatMessage
    chat_messages = [o for o in session2.added if hasattr(o, "message_id")]
    assert len(chat_messages) == 1
    assert fake_doc.chat_message_id == chat_messages[0].message_id


async def test_chat_history_joins_documents(monkeypatch):
    phone = "+19084329987"
    msg_with_doc_id = uuid7()
    msg_without_doc_id = uuid7()

    msg1 = SimpleNamespace(
        message_id=msg_with_doc_id,
        session_id=uuid.uuid4(),
        role="user",
        content="hi with doc",
        created_at=datetime.now(timezone.utc),
    )
    msg2 = SimpleNamespace(
        message_id=msg_without_doc_id,
        session_id=uuid.uuid4(),
        role="model",
        content="no attachment here",
        created_at=datetime.now(timezone.utc),
    )
    doc = SimpleNamespace(
        document_id=uuid.uuid4(),
        original_filename="lab.pdf",
        doc_type="lab_result",
        status="ready",
        summary_detailed="summary",
        chat_message_id=msg_with_doc_id,
    )

    fake_session = FakeSession()
    fake_session.execute_results = [FakeResult([msg1, msg2]), FakeResult([doc])]

    async def _override_db():
        yield fake_session

    app.dependency_overrides[get_db] = _override_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/stream/history",
                headers={"X-Phone-Number": phone},
            )
        assert resp.status_code == 200
        data = resp.json()
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert len(data["messages"]) == 2
    with_doc = next(m for m in data["messages"] if m["id"] == str(msg_with_doc_id))
    without_doc = next(m for m in data["messages"] if m["id"] == str(msg_without_doc_id))

    assert "documents" in with_doc
    assert len(with_doc["documents"]) == 1
    d = with_doc["documents"][0]
    assert d["document_id"] == str(doc.document_id)
    assert d["original_filename"] == "lab.pdf"
    assert d["doc_type"] == "lab_result"
    assert d["status"] == "ready"
    assert d["summary_detailed"] == "summary"

    # stream.py only sets `documents` key when attached is truthy
    assert "documents" not in without_doc


async def test_chat_with_invalid_document_ids_noops(monkeypatch):
    phone = "+19084329987"

    session1 = FakeSession()
    session1.execute_results = [FakeResult(SimpleNamespace(session_id="exists"))]
    session2 = FakeSession()
    session3 = FakeSession()
    sessions = iter([session1, session2, session3])

    def fake_factory():
        return next(sessions)

    monkeypatch.setattr(stream_module, "async_session_factory", fake_factory)
    monkeypatch.setattr(stream_module, "get_client", lambda: FakeLive150Client())

    fake_runner = FakeRunner()
    monkeypatch.setattr(stream_module, "_get_runner", lambda: fake_runner)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/stream/chat",
            json={
                "messages": [{"role": "user", "content": "plain question"}],
                "documents": ["not-a-uuid", None, 123],
            },
            headers={"X-Phone-Number": phone},
        )
        assert resp.status_code == 200
        await resp.aread()

    assert len(fake_runner.calls) == 1
    msg = fake_runner.calls[0]["message"]
    assert msg == "plain question"
    assert not msg.startswith("[Attached documents:")
