"""Tests for the SSE /documents/{id}/events endpoint.

The LISTEN/NOTIFY layer is patched out — we never touch a real Postgres.
"""

import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from live150.api import documents as documents_module
from live150.auth.middleware import AuthedUser, require_user
from live150.db.session import get_db
from live150.main import app


class FakeResult:
    def __init__(self, obj: Any):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class FakeSession:
    def __init__(self):
        self.execute_results: list[Any] = []

    def add(self, obj):
        pass

    async def delete(self, obj):
        pass

    async def commit(self):
        pass

    async def execute(self, stmt):
        if self.execute_results:
            return self.execute_results.pop(0)
        return FakeResult(None)


@pytest.fixture
def fake_user():
    return AuthedUser(user_id="+19084329987", access_token="fake")


@pytest.fixture
def fake_session():
    return FakeSession()


@pytest.fixture
def client_factory(fake_user, fake_session):
    async def _override_user():
        return fake_user

    async def _override_db():
        yield fake_session

    app.dependency_overrides[require_user] = _override_user
    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    yield client, fake_session, fake_user

    app.dependency_overrides.pop(require_user, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_events_streams_stages(monkeypatch, client_factory):
    client, session, user = client_factory
    document_id = uuid.uuid4()

    class FakeDoc:
        def __init__(self):
            self.document_id = document_id
            self.user_id = user.user_id
            self.status = "processing"

    session.execute_results = [FakeResult(FakeDoc())]

    async def fake_subscribe(_doc_id):
        for ev in [
            {"stage": "reading", "label": "Maya is reading…"},
            {"stage": "summarizing", "label": "Summarizing…"},
            {"stage": "ready", "label": "Ready"},
        ]:
            yield ev

    monkeypatch.setattr(documents_module, "subscribe_doc_events", fake_subscribe)

    async with client:
        async with client.stream(
            "GET",
            f"/api/v1/documents/{document_id}/events",
            headers={"X-Phone-Number": user.user_id},
        ) as resp:
            assert resp.status_code == 200
            chunks: list[str] = []
            async for chunk in resp.aiter_text():
                chunks.append(chunk)
                if "ready" in chunk:
                    break

    blob = "".join(chunks)
    assert "event: status" in blob
    assert "event: reading" in blob
    assert "event: summarizing" in blob
    assert "event: ready" in blob


@pytest.mark.asyncio
async def test_events_404_for_missing_doc(monkeypatch, client_factory):
    client, session, user = client_factory
    document_id = uuid.uuid4()
    session.execute_results = [FakeResult(None)]

    async with client:
        resp = await client.get(
            f"/api/v1/documents/{document_id}/events",
            headers={"X-Phone-Number": user.user_id},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_events_enforces_ownership(monkeypatch, client_factory):
    client, session, user = client_factory
    document_id = uuid.uuid4()
    # Ownership filter is in the WHERE clause; missing row simulates someone
    # else's doc returning None for this user.
    session.execute_results = [FakeResult(None)]

    async with client:
        resp = await client.get(
            f"/api/v1/documents/{document_id}/events",
            headers={"X-Phone-Number": user.user_id},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_events_terminal_status_returns_immediately(monkeypatch, client_factory):
    client, session, user = client_factory
    document_id = uuid.uuid4()

    class FakeDoc:
        def __init__(self):
            self.document_id = document_id
            self.user_id = user.user_id
            self.status = "ready"

    session.execute_results = [FakeResult(FakeDoc())]

    sub_called = False

    async def fake_subscribe(_doc_id):  # pragma: no cover
        nonlocal sub_called
        sub_called = True
        if False:
            yield  # type: ignore[unreachable]

    monkeypatch.setattr(documents_module, "subscribe_doc_events", fake_subscribe)

    async with client:
        async with client.stream(
            "GET",
            f"/api/v1/documents/{document_id}/events",
            headers={"X-Phone-Number": user.user_id},
        ) as resp:
            assert resp.status_code == 200
            text = ""
            async for chunk in resp.aiter_text():
                text += chunk
                # Terminal status closes after first message; break promptly.
                break

    assert "ready" in text
    assert sub_called is False
