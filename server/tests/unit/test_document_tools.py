"""Unit tests for document tools."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from live150.tools import document_tools


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


def _factory_for(session: FakeSession):
    def _factory():
        return session

    return _factory


def _tool_context(user_id="+19084329987"):
    return SimpleNamespace(state={"user_id": user_id})


def _fake_doc(**overrides):
    base = {
        "document_id": uuid.uuid4(),
        "doc_type": "lab_result",
        "status": "ready",
        "original_filename": "lab.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1234,
        "tags": ["a", "b"],
        "summary_detailed": "summary text",
        "structured": {"labs": []},
        "extracted_text": "long raw OCR text",
        "uploaded_at": datetime.now(timezone.utc),
        "processed_at": None,
        "expiry_alert_date": None,
        "error_message": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


async def test_list_documents_returns_rows_newest_first(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [
        _fake_doc(original_filename="newest.pdf", uploaded_at=now),
        _fake_doc(original_filename="middle.pdf", uploaded_at=now - timedelta(days=1)),
        _fake_doc(original_filename="oldest.pdf", uploaded_at=now - timedelta(days=2)),
    ]

    session = FakeSession()
    session.execute_results = [FakeResult(rows)]
    monkeypatch.setattr(document_tools, "async_session_factory", _factory_for(session))

    result = await document_tools.list_documents(limit=10, tool_context=_tool_context())

    assert "documents" in result
    assert len(result["documents"]) == 3
    assert [d["original_filename"] for d in result["documents"]] == [
        "newest.pdf",
        "middle.pdf",
        "oldest.pdf",
    ]
    for d in result["documents"]:
        assert set(
            ["document_id", "doc_type", "status", "original_filename", "tags",
             "summary_detailed", "uploaded_at"]
        ).issubset(d.keys())
        assert "extracted_text" not in d
        assert "structured" not in d

    empty_session = FakeSession()
    empty_session.execute_results = [FakeResult([])]
    monkeypatch.setattr(document_tools, "async_session_factory", _factory_for(empty_session))
    empty_result = await document_tools.list_documents(tool_context=_tool_context())
    assert empty_result == {"documents": [], "message": "No documents found."}


async def test_list_documents_filters_by_doc_type(monkeypatch):
    session = FakeSession()
    session.execute_results = [FakeResult([])]
    monkeypatch.setattr(document_tools, "async_session_factory", _factory_for(session))

    await document_tools.list_documents(
        doc_type="lab_result", limit=500, tool_context=_tool_context()
    )

    assert len(session.executed) == 1
    stmt = session.executed[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "doc_type" in compiled
    assert "lab_result" in compiled
    assert "LIMIT 50" in compiled.upper() or " LIMIT 50" in compiled


async def test_get_document_returns_row_omits_extracted_by_default(monkeypatch):
    doc = _fake_doc()
    session = FakeSession()
    session.execute_results = [FakeResult(doc)]
    monkeypatch.setattr(document_tools, "async_session_factory", _factory_for(session))

    result = await document_tools.get_document(
        document_id=str(doc.document_id),
        include_extracted_text=False,
        tool_context=_tool_context(),
    )

    assert result["document_id"] == str(doc.document_id)
    assert result["summary_detailed"] == "summary text"
    assert result["structured"] == {"labs": []}
    assert "extracted_text" not in result

    session2 = FakeSession()
    session2.execute_results = [FakeResult(doc)]
    monkeypatch.setattr(document_tools, "async_session_factory", _factory_for(session2))

    result2 = await document_tools.get_document(
        document_id=str(doc.document_id),
        include_extracted_text=True,
        tool_context=_tool_context(),
    )
    assert result2["extracted_text"] == "long raw OCR text"


async def test_get_document_404(monkeypatch):
    session = FakeSession()
    session.execute_results = [FakeResult(None)]
    monkeypatch.setattr(document_tools, "async_session_factory", _factory_for(session))

    result = await document_tools.get_document(
        document_id=str(uuid.uuid4()),
        tool_context=_tool_context(),
    )
    assert result == {"error": True, "message": "Document not found."}

    bad = await document_tools.get_document(
        document_id="not-a-uuid",
        tool_context=_tool_context(),
    )
    assert bad.get("error") is True
    assert "Invalid" in bad["message"] or "not-a-uuid" in bad["message"]
