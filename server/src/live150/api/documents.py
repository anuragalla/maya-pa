"""Document upload / list / fetch / delete endpoints."""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer
from sse_starlette.sse import EventSourceResponse
from uuid6 import uuid7

from live150.auth.middleware import AuthedUser, require_user
from live150.db.models.document import Document
from live150.db.models.memory import MemoryEntry
from live150.db.session import get_db
from live150.documents.events import publish_doc_event, subscribe_doc_events
from live150.integrations import gcs

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}

ALLOWED_SOURCES = {"app_camera", "file_upload"}

MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB

_mime_to_ext = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}


def _derive_extension(filename: str | None, mime_type: str) -> str:
    if filename:
        _, ext = os.path.splitext(filename)
        if ext:
            return ext.lstrip(".").lower()
    return _mime_to_ext.get(mime_type, "bin")


def _row_to_dict(row: Document, include_extracted: bool = False) -> dict:
    data = {
        "document_id": str(row.document_id),
        "doc_type": row.doc_type,
        "status": row.status,
        "original_filename": row.original_filename,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "source": row.source,
        "storage_uri": row.storage_uri,
        "tags": list(row.tags) if row.tags else [],
        "summary_detailed": row.summary_detailed,
        "structured": row.structured or {},
        "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
        "expiry_alert_date": row.expiry_alert_date.isoformat() if row.expiry_alert_date else None,
        "error_message": row.error_message,
    }
    if include_extracted:
        data["extracted_text"] = row.extracted_text
    return data


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    source: str = Form("file_upload"),
    note: str | None = Form(None),
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a health document (PDF or image) to GCS and enqueue processing."""
    if source not in ALLOWED_SOURCES:
        raise HTTPException(status_code=400, detail=f"source must be one of {sorted(ALLOWED_SOURCES)}")

    mime_type = (file.content_type or "").lower()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type {mime_type!r}; allowed: {sorted(ALLOWED_MIME_TYPES)}",
        )

    # Size check: prefer file.size, fall back to streaming + counting.
    size_bytes: int
    if file.size is not None:
        if file.size > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_SIZE} bytes")
        size_bytes = file.size
    else:
        data = await file.read()
        size_bytes = len(data)
        if size_bytes > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_SIZE} bytes")
        # Rewind so gcs.upload can re-read it.
        await file.seek(0)

    document_id = uuid7()
    ext = _derive_extension(file.filename, mime_type)

    try:
        gs_uri = gcs.upload(user.user_id, str(document_id), file.file, mime_type, ext)
    except Exception as e:
        logger.error(
            "gcs upload failed",
            extra={"user_id": user.user_id, "document_id": str(document_id), "error": str(e)},
        )
        raise HTTPException(status_code=502, detail=f"Upload to storage failed: {e}")

    doc = Document(
        document_id=document_id,
        user_id=user.user_id,
        doc_type="other",
        status="uploaded",
        storage_uri=gs_uri,
        original_filename=file.filename or f"{document_id}.{ext}",
        mime_type=mime_type,
        size_bytes=size_bytes,
        source=source,
        structured={},
        tags=[],
    )
    if note:
        doc.structured = {"user_note": note}

    db.add(doc)
    await db.commit()

    try:
        from live150.reminders.scheduler import get_scheduler

        get_scheduler().add_job(
            "live150.documents.processor:process_document",
            trigger="date",
            run_date=datetime.now(timezone.utc),
            args=[str(document_id)],
            id=f"doc_process:{document_id}",
            replace_existing=True,
        )
    except Exception as e:
        logger.warning(
            "failed to schedule doc processor",
            extra={"document_id": str(document_id), "error": str(e)},
        )

    return {"document_id": str(document_id), "status": "processing"}


@router.get("")
async def list_documents(
    doc_type: str | None = None,
    limit: int = 20,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """List the user's documents (newest first)."""
    limit = max(1, min(limit, 100))
    stmt = (
        select(Document)
        .options(defer(Document.extracted_text))
        .where(Document.user_id == user.user_id)
    )
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    stmt = stmt.order_by(Document.uploaded_at.desc()).limit(limit)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    docs = []
    for r in rows:
        d = _row_to_dict(r, include_extracted=False)
        d.pop("structured", None)
        docs.append(d)
    return {"documents": docs}


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    include_extracted_text: bool = False,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single document row."""
    stmt = select(Document).where(
        Document.document_id == document_id,
        Document.user_id == user.user_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return _row_to_dict(row, include_extracted=include_extracted_text)


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: uuid.UUID,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream the raw file bytes back to the client."""
    stmt = select(Document).where(
        Document.document_id == document_id,
        Document.user_id == user.user_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        data = gcs.open_read(row.storage_uri)
    except Exception as e:
        logger.error(
            "gcs read failed",
            extra={"document_id": str(document_id), "error": str(e)},
        )
        raise HTTPException(status_code=502, detail=f"Storage read failed: {e}")

    return Response(
        content=data,
        media_type=row.mime_type,
        headers={"Content-Disposition": f'inline; filename="{row.original_filename}"'},
    )


@router.get("/{document_id}/events")
async def doc_events(
    document_id: uuid.UUID,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Server-Sent Events stream of processor stage updates for one document."""
    stmt = select(Document).where(
        Document.document_id == document_id,
        Document.user_id == user.user_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    initial_status = row.status
    doc_id_str = str(document_id)

    async def event_stream():
        yield {"event": "status", "data": json.dumps({"status": initial_status})}
        if initial_status in ("ready", "failed", "cancelled"):
            return
        try:
            async for event in subscribe_doc_events(doc_id_str):
                yield {
                    "event": event.get("stage", "stage"),
                    "data": json.dumps(event),
                }
                if event.get("stage") in ("ready", "failed", "cancelled"):
                    return
        except asyncio.CancelledError:
            raise

    return EventSourceResponse(event_stream(), ping=15)


@router.delete("/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete the document row, GCS object, and related memory entries.

    If the row was mid-processing we publish a `cancelled` event first so any
    open SSE stream closes cleanly. The processor's pre-commit cancellation
    check will see the row missing and exit without persisting.
    """
    stmt = select(Document).where(
        Document.document_id == document_id,
        Document.user_id == user.user_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    was_processing = row.status == "processing"
    storage_uri = row.storage_uri

    if was_processing:
        try:
            await publish_doc_event(str(document_id), "cancelled", "Cancelled")
        except Exception:
            logger.warning(
                "publish cancelled event failed",
                extra={"document_id": str(document_id)},
            )

    try:
        gcs.delete(storage_uri)
    except Exception as e:
        logger.warning(
            "gcs delete failed; continuing with row delete",
            extra={"document_id": str(document_id), "error": str(e)},
        )

    await db.delete(row)

    await db.execute(
        delete(MemoryEntry).where(
            MemoryEntry.user_id == user.user_id,
            MemoryEntry.source == "document",
            MemoryEntry.source_ref == str(document_id),
        )
    )

    await db.commit()

    return {"deleted": True}
