"""Happy-path tests for the documents API router.

These tests mock GCS, the scheduler, require_user, and get_db so no real
Postgres/GCS access is needed.
"""

import io
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

    def scalars(self):
        class _S:
            def __init__(self, items):
                self._items = items

            def all(self):
                return self._items

        items = self._obj if isinstance(self._obj, list) else ([self._obj] if self._obj else [])
        return _S(items)


class FakeSession:
    """Minimal AsyncSession stand-in capturing adds, deletes, and executes."""

    def __init__(self):
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.committed = 0
        self.executed: list[Any] = []
        # Values returned by successive execute() calls (FIFO).
        self.execute_results: list[Any] = []

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.committed += 1

    async def execute(self, stmt):
        self.executed.append(stmt)
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
    """Return a factory that yields a configured AsyncClient."""

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
async def test_upload_happy_path(monkeypatch, client_factory):
    client, session, user = client_factory

    upload_calls: list[dict] = []

    def fake_upload(user_id, document_id, file, mime_type, ext):
        upload_calls.append(
            {
                "user_id": user_id,
                "document_id": document_id,
                "mime_type": mime_type,
                "ext": ext,
            }
        )
        return f"gs://live150-docs-test/users/{user_id}/{document_id}.{ext}"

    monkeypatch.setattr(documents_module.gcs, "upload", fake_upload)

    class FakeScheduler:
        def __init__(self):
            self.jobs: list[dict] = []

        def add_job(self, func, **kwargs):
            self.jobs.append({"func": func, **kwargs})

    fake_sched = FakeScheduler()
    monkeypatch.setattr(
        "live150.reminders.scheduler.get_scheduler", lambda: fake_sched
    )

    pdf_bytes = b"%PDF-1.4\n%fake pdf payload\n"
    files = {"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"source": "file_upload", "note": "lab from april"}

    async with client:
        resp = await client.post(
            "/api/v1/documents",
            files=files,
            data=data,
            headers={"X-Phone-Number": user.user_id},
        )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "processing"
    assert uuid.UUID(body["document_id"])

    assert len(upload_calls) == 1
    assert upload_calls[0]["mime_type"] == "application/pdf"
    assert upload_calls[0]["ext"] == "pdf"

    assert len(session.added) == 1
    doc = session.added[0]
    assert doc.user_id == user.user_id
    assert doc.mime_type == "application/pdf"
    assert doc.status == "uploaded"
    assert doc.doc_type == "other"
    assert doc.source == "file_upload"
    assert doc.original_filename == "report.pdf"
    assert doc.size_bytes == len(pdf_bytes)
    assert doc.storage_uri.startswith("gs://live150-docs-test/")
    assert session.committed == 1

    assert len(fake_sched.jobs) == 1
    assert fake_sched.jobs[0]["id"].startswith("doc_process:")


@pytest.mark.asyncio
async def test_upload_rejects_oversized_payload(monkeypatch, client_factory):
    client, _session, user = client_factory

    # Ensure gcs.upload is never hit if size check trips first.
    def boom(*a, **kw):  # pragma: no cover
        raise AssertionError("gcs.upload should not be called for oversized payload")

    monkeypatch.setattr(documents_module.gcs, "upload", boom)
    monkeypatch.setattr(
        "live150.reminders.scheduler.get_scheduler", lambda: object()
    )

    big = b"\x00" * (documents_module.MAX_UPLOAD_SIZE + 1)
    files = {"file": ("big.pdf", io.BytesIO(big), "application/pdf")}

    async with client:
        resp = await client.post(
            "/api/v1/documents",
            files=files,
            headers={"X-Phone-Number": user.user_id},
        )

    assert resp.status_code == 413, resp.text


@pytest.mark.asyncio
async def test_upload_rejects_disallowed_mime(monkeypatch, client_factory):
    client, _session, user = client_factory

    def boom(*a, **kw):  # pragma: no cover
        raise AssertionError("gcs.upload should not be called for disallowed mime")

    monkeypatch.setattr(documents_module.gcs, "upload", boom)

    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}

    async with client:
        resp = await client.post(
            "/api/v1/documents",
            files=files,
            headers={"X-Phone-Number": user.user_id},
        )

    assert resp.status_code == 415, resp.text


@pytest.mark.asyncio
async def test_delete_document(monkeypatch, client_factory):
    client, session, user = client_factory

    document_id = uuid.uuid4()

    class FakeDoc:
        def __init__(self):
            self.document_id = document_id
            self.user_id = user.user_id
            self.status = "ready"
            self.storage_uri = f"gs://live150-docs-test/users/{user.user_id}/{document_id}.pdf"

    fake_doc = FakeDoc()
    # First execute() returns the select result; the second is the DELETE memory stmt.
    session.execute_results = [FakeResult(fake_doc), FakeResult(None)]

    delete_calls: list[str] = []

    def fake_delete(gs_uri):
        delete_calls.append(gs_uri)

    monkeypatch.setattr(documents_module.gcs, "delete", fake_delete)

    async with client:
        resp = await client.delete(
            f"/api/v1/documents/{document_id}",
            headers={"X-Phone-Number": user.user_id},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"deleted": True}

    assert delete_calls == [fake_doc.storage_uri]
    assert fake_doc in session.deleted
    assert session.committed == 1


@pytest.mark.asyncio
async def test_delete_processing_doc_publishes_cancelled(monkeypatch, client_factory):
    client, session, user = client_factory

    document_id = uuid.uuid4()

    class FakeDoc:
        def __init__(self):
            self.document_id = document_id
            self.user_id = user.user_id
            self.status = "processing"
            self.storage_uri = f"gs://live150-docs-test/users/{user.user_id}/{document_id}.pdf"

    fake_doc = FakeDoc()
    session.execute_results = [FakeResult(fake_doc), FakeResult(None)]

    monkeypatch.setattr(documents_module.gcs, "delete", lambda _u: None)

    publish_calls: list[tuple] = []

    async def fake_publish(doc_id, stage, label, payload=None):
        publish_calls.append((doc_id, stage, label, payload))

    monkeypatch.setattr(documents_module, "publish_doc_event", fake_publish)

    async with client:
        resp = await client.delete(
            f"/api/v1/documents/{document_id}",
            headers={"X-Phone-Number": user.user_id},
        )

    assert resp.status_code == 200, resp.text
    assert any(stage == "cancelled" for _id, stage, *_ in publish_calls), publish_calls
    assert fake_doc in session.deleted
