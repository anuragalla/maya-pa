"""Document tools — list and fetch uploaded health documents."""

import logging
import uuid

from sqlalchemy import select

from live150.db.models.document import Document
from live150.db.session import async_session_factory

logger = logging.getLogger(__name__)


async def list_documents(
    doc_type: str | None = None,
    limit: int = 10,
    tool_context=None,
) -> dict:
    """List the user's uploaded health documents (labs, prescriptions, visit notes, etc).

    Returns processed documents newest first with a detailed summary suitable
    for reasoning about findings. Raw transcriptions are not included.

    Args:
        doc_type: Optional filter — one of lab_result, prescription, insurance,
                  imaging, visit_note, vaccine, other.
        limit: Max rows (default 10, max 50).
    """
    user_id = tool_context.state["user_id"]
    limit = max(1, min(limit, 50))

    async with async_session_factory() as db:
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.uploaded_at.desc())
            .limit(limit)
        )
        if doc_type:
            stmt = stmt.where(Document.doc_type == doc_type)
        rows = (await db.execute(stmt)).scalars().all()

    if not rows:
        return {"documents": [], "message": "No documents found."}

    return {
        "documents": [
            {
                "document_id": str(r.document_id),
                "doc_type": r.doc_type,
                "status": r.status,
                "original_filename": r.original_filename,
                "tags": r.tags or [],
                "summary_detailed": r.summary_detailed,
                "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                "expiry_alert_date": r.expiry_alert_date.isoformat() if r.expiry_alert_date else None,
            }
            for r in rows
        ]
    }


async def get_document(
    document_id: str,
    include_extracted_text: bool = False,
    tool_context=None,
) -> dict:
    """Fetch one document by id, including its structured extraction payload.

    Args:
        document_id: The document's UUID.
        include_extracted_text: If true, also return the full raw transcription.
                                Default false (keeps responses compact).
    """
    user_id = tool_context.state["user_id"]

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        return {"error": True, "message": f"Invalid document_id: {document_id}"}

    async with async_session_factory() as db:
        row = (await db.execute(
            select(Document).where(
                Document.document_id == doc_uuid,
                Document.user_id == user_id,
            )
        )).scalar_one_or_none()

    if row is None:
        return {"error": True, "message": "Document not found."}

    payload = {
        "document_id": str(row.document_id),
        "doc_type": row.doc_type,
        "status": row.status,
        "original_filename": row.original_filename,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "tags": row.tags or [],
        "summary_detailed": row.summary_detailed,
        "structured": row.structured or {},
        "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
        "expiry_alert_date": row.expiry_alert_date.isoformat() if row.expiry_alert_date else None,
        "error_message": row.error_message,
    }
    if include_extracted_text:
        payload["extracted_text"] = row.extracted_text
    return payload
