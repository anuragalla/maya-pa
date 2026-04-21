"""Unit tests for live150.documents.processor."""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from live150.documents import processor as processor_module


class FakeResult:
    def __init__(self, obj: Any):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class FakeSession:
    def __init__(self, execute_results: list[Any] | None = None):
        self.added: list[Any] = []
        self.committed = 0
        self.executed: list[Any] = []
        self.execute_results: list[Any] = list(execute_results or [])

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
        return None


class FakeDoc:
    def __init__(
        self,
        document_id: uuid.UUID,
        user_id: str,
        status: str = "uploaded",
        original_filename: str = "lab.pdf",
        mime_type: str = "application/pdf",
        storage_uri: str | None = None,
    ):
        self.document_id = document_id
        self.user_id = user_id
        self.status = status
        self.error_message: str | None = None
        self.storage_uri = storage_uri or f"gs://bucket/{user_id}/{document_id}.pdf"
        self.original_filename = original_filename
        self.mime_type = mime_type
        self.uploaded_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
        self.doc_type = "other"
        self.summary_detailed: str | None = None
        self.extracted_text: str | None = None
        self.tags: list[str] = []
        self.structured: dict = {}
        self.expiry_alert_date: date | None = None
        self.processed_at: datetime | None = None


class SessionFactory:
    """Stand-in for async_session_factory: each call pops the next session."""

    def __init__(self, sessions: list[FakeSession]):
        self._sessions = list(sessions)
        self.used: list[FakeSession] = []

    def __call__(self):
        if not self._sessions:
            raise AssertionError("session factory called too many times")
        sess = self._sessions.pop(0)
        self.used.append(sess)
        return sess


def _text_part(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        thought=False,
        function_call=None,
        function_response=None,
    )


def _event_with_text(text: str) -> SimpleNamespace:
    return SimpleNamespace(content=SimpleNamespace(parts=[_text_part(text)]))


class FakeRunner:
    """Minimal ADK Runner stand-in. Ignores inputs, yields canned events."""

    _events: list[Any] = []

    def __init__(self, *args, **kwargs):
        pass

    async def run_async(self, **kwargs):
        for ev in self.__class__._events:
            yield ev


class FakeSessionService:
    def __init__(self):
        self.created: list[dict] = []

    async def create_session(self, **kwargs):
        self.created.append(kwargs)


class FakeTokenResp:
    def __init__(self, token: str = "fake"):
        self.access_token = token


class FakeClient:
    def __init__(self, token: str = "fake", impersonate_exc: Exception | None = None):
        self._token = token
        self._exc = impersonate_exc
        self.impersonate_calls: list[str] = []

    async def impersonate(self, phone_number: str):
        self.impersonate_calls.append(phone_number)
        if self._exc:
            raise self._exc
        return FakeTokenResp(self._token)


def _valid_analysis_json() -> str:
    return json.dumps(
        {
            "doc_type": "lab_result",
            "summary_detailed": "Summary of lab values" * 10,
            "extracted_text": "LDL 142 mg/dL",
            "tags": ["lipid-panel", "ldl-elevated"],
            "structured": {"markers": [{"name": "LDL", "value": 142, "unit": "mg/dL"}]},
            "expiry_alert_date": None,
        }
    )


def _patch_common(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sessions: list[FakeSession],
    client: FakeClient,
    runner_events: list[Any],
    publish_calls: list[tuple],
    memory_calls: list[dict],
):
    factory = SessionFactory(sessions)
    monkeypatch.setattr(processor_module, "async_session_factory", factory)

    import live150.live150_client as live150_client_mod

    monkeypatch.setattr(live150_client_mod, "get_client", lambda: client)

    FakeRunner._events = runner_events

    import google.adk.runners as adk_runners
    import google.adk.sessions as adk_sessions
    import google.genai.types as genai_types

    monkeypatch.setattr(adk_runners, "Runner", FakeRunner)
    monkeypatch.setattr(adk_sessions, "InMemorySessionService", FakeSessionService)

    class _FakePart:
        @staticmethod
        def from_uri(file_uri: str, mime_type: str):
            return SimpleNamespace(file_uri=file_uri, mime_type=mime_type)

        @staticmethod
        def from_text(text: str):
            return SimpleNamespace(text=text)

    def _fake_content(role: str, parts: list[Any]):
        return SimpleNamespace(role=role, parts=parts)

    monkeypatch.setattr(genai_types, "Part", _FakePart)
    monkeypatch.setattr(genai_types, "Content", _fake_content)

    import live150.documents.events as events_mod

    async def _fake_publish(document_id, stage, label, payload=None):
        publish_calls.append((document_id, stage, label, payload))

    monkeypatch.setattr(events_mod, "publish_doc_event", _fake_publish)

    import live150.memory.service as memsvc_mod

    class _FakeMemoryService:
        def __init__(self):
            pass

        async def save(self, **kwargs):
            memory_calls.append(kwargs)
            return uuid.uuid4()

    monkeypatch.setattr(memsvc_mod, "MemoryService", _FakeMemoryService)

    return factory


async def test_process_document_happy_path(monkeypatch):
    doc_id = uuid.uuid4()
    doc = FakeDoc(doc_id, user_id="+19084329987", status="uploaded")

    load_session = FakeSession([FakeResult(doc)])
    persist_session = FakeSession([FakeResult(doc)])
    memory_session = FakeSession()

    client = FakeClient()
    publish_calls: list[tuple] = []
    memory_calls: list[dict] = []

    _patch_common(
        monkeypatch,
        sessions=[load_session, persist_session, memory_session],
        client=client,
        runner_events=[_event_with_text(_valid_analysis_json())],
        publish_calls=publish_calls,
        memory_calls=memory_calls,
    )

    await processor_module.process_document(str(doc_id))

    assert doc.status == "ready"
    assert doc.processed_at is not None
    assert doc.doc_type == "lab_result"
    assert doc.summary_detailed.startswith("Summary of lab values")
    assert doc.extracted_text == "LDL 142 mg/dL"
    assert doc.structured == {
        "markers": [{"name": "LDL", "value": 142, "unit": "mg/dL"}]
    }
    assert list(doc.tags) == ["lipid-panel", "ldl-elevated"]
    assert doc.error_message is None

    stages = [c[1] for c in publish_calls]
    assert "reading" in stages
    assert "summarizing" in stages or "context" in stages
    assert stages[-1] == "ready"
    assert len(publish_calls) == 4 or len(publish_calls) == 3  # reading, summarizing, ready

    assert len(memory_calls) == 1
    mc = memory_calls[0]
    assert mc["kind"] == "document"
    assert mc["source"] == "document"
    assert mc["source_ref"] == str(doc_id)
    assert mc["user_id"] == "+19084329987"

    assert client.impersonate_calls == ["+19084329987"]


async def test_process_document_skips_when_cancelled_mid_flight(monkeypatch, caplog):
    doc_id = uuid.uuid4()
    doc = FakeDoc(doc_id, user_id="+19084329987", status="uploaded")

    # Second load (after runner) returns same row but with status flipped to cancelled.
    cancelled_view = FakeDoc(doc_id, user_id="+19084329987", status="cancelled")

    load_session = FakeSession([FakeResult(doc)])
    persist_session = FakeSession([FakeResult(cancelled_view)])

    client = FakeClient()
    publish_calls: list[tuple] = []
    memory_calls: list[dict] = []

    _patch_common(
        monkeypatch,
        sessions=[load_session, persist_session],
        client=client,
        runner_events=[_event_with_text(_valid_analysis_json())],
        publish_calls=publish_calls,
        memory_calls=memory_calls,
    )

    caplog.set_level(logging.INFO, logger=processor_module.logger.name)
    await processor_module.process_document(str(doc_id))

    assert memory_calls == []
    assert cancelled_view.status == "cancelled"
    assert cancelled_view.processed_at is None
    assert persist_session.committed == 0
    assert any("cancelled mid-flight" in rec.message for rec in caplog.records)


async def test_process_document_invalid_output_marks_failed(monkeypatch):
    doc_id = uuid.uuid4()
    doc = FakeDoc(doc_id, user_id="+19084329987", status="uploaded")

    load_session = FakeSession([FakeResult(doc)])
    # _mark_failed opens a new session and re-fetches the row to flip status.
    fail_session = FakeSession([FakeResult(doc)])

    client = FakeClient()
    publish_calls: list[tuple] = []
    memory_calls: list[dict] = []

    _patch_common(
        monkeypatch,
        sessions=[load_session, fail_session],
        client=client,
        runner_events=[_event_with_text("sorry I can't read this")],
        publish_calls=publish_calls,
        memory_calls=memory_calls,
    )

    await processor_module.process_document(str(doc_id))

    assert doc.status == "failed"
    assert doc.error_message
    assert "DocAgent output invalid" in doc.error_message
    assert memory_calls == []


async def test_process_document_guards_against_nonpending_status(monkeypatch, caplog):
    doc_id = uuid.uuid4()
    doc = FakeDoc(doc_id, user_id="+19084329987", status="ready")

    load_session = FakeSession([FakeResult(doc)])
    client = FakeClient()
    publish_calls: list[tuple] = []
    memory_calls: list[dict] = []

    _patch_common(
        monkeypatch,
        sessions=[load_session],
        client=client,
        runner_events=[_event_with_text(_valid_analysis_json())],
        publish_calls=publish_calls,
        memory_calls=memory_calls,
    )

    caplog.set_level(logging.INFO, logger=processor_module.logger.name)
    await processor_module.process_document(str(doc_id))

    assert client.impersonate_calls == []
    assert load_session.committed == 0
    assert publish_calls == []
    assert memory_calls == []
    assert doc.status == "ready"
    assert any("skipping" in rec.message.lower() or "not processable" in rec.message.lower()
               for rec in caplog.records)


async def test_process_document_handles_impersonation_failure(monkeypatch):
    doc_id = uuid.uuid4()
    doc = FakeDoc(doc_id, user_id="+19084329987", status="uploaded")

    load_session = FakeSession([FakeResult(doc)])
    fail_session = FakeSession([FakeResult(doc)])

    client = FakeClient(impersonate_exc=RuntimeError("token denied"))
    publish_calls: list[tuple] = []
    memory_calls: list[dict] = []

    # Track that Runner is never instantiated.
    runner_instantiations: list[int] = []

    class _SpyRunner(FakeRunner):
        def __init__(self, *args, **kwargs):
            runner_instantiations.append(1)
            super().__init__(*args, **kwargs)

    _patch_common(
        monkeypatch,
        sessions=[load_session, fail_session],
        client=client,
        runner_events=[_event_with_text(_valid_analysis_json())],
        publish_calls=publish_calls,
        memory_calls=memory_calls,
    )
    import google.adk.runners as adk_runners
    monkeypatch.setattr(adk_runners, "Runner", _SpyRunner)

    await processor_module.process_document(str(doc_id))

    assert runner_instantiations == []
    assert doc.status == "failed"
    assert doc.error_message
    assert "token denied" in doc.error_message
    assert memory_calls == []
