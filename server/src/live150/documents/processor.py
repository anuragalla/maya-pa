"""DocAgent processor — APScheduler entry point.

Invoked as `live150.documents.processor:process_document` for each uploaded
document. Loads the row, runs the DocAgent sub-agent on the gs:// URI, parses
the emitted JSON into `DocAnalysis`, persists results to the Document row,
mirrors the detailed summary into the memory service, and optionally schedules
a renewal reminder for prescriptions.
"""

import json
import logging
import re
import uuid
from datetime import datetime, time, timezone

from sqlalchemy import select

from live150.db.models.document import Document
from live150.db.session import async_session_factory

logger = logging.getLogger(__name__)

_APP_NAME = "live150-doc"
_MAX_ERROR_LEN = 500
_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        # Drop leading fence (optionally with ```json) and trailing fence.
        stripped = _CODE_FENCE_RE.sub("", stripped).strip()
    return stripped


def _row_to_dict_for_event(document: Document) -> dict:
    """Compact dict for the SSE 'ready' payload — large fields omitted by NOTIFY guard if needed."""
    return {
        "document_id": str(document.document_id),
        "doc_type": document.doc_type,
        "status": document.status,
        "original_filename": document.original_filename,
        "mime_type": document.mime_type,
        "tags": list(document.tags) if document.tags else [],
        "summary_detailed": document.summary_detailed,
        "expiry_alert_date": document.expiry_alert_date.isoformat()
        if document.expiry_alert_date
        else None,
    }


def _build_hint_text(document: Document) -> str:
    uploaded_at = document.uploaded_at.isoformat() if document.uploaded_at else "unknown"
    return (
        "Document metadata:\n"
        f"- filename: {document.original_filename}\n"
        f"- uploaded_at: {uploaded_at}\n\n"
        "Analyze this document and emit the DocAnalysis JSON."
    )


async def _mark_failed(document_id: uuid.UUID, error_message: str) -> None:
    from live150.documents.events import publish_doc_event

    trimmed = error_message[:_MAX_ERROR_LEN]
    async with async_session_factory() as db:
        row = (
            await db.execute(select(Document).where(Document.document_id == document_id))
        ).scalar_one_or_none()
        if not row:
            return
        row.status = "failed"
        row.error_message = trimmed
        await db.commit()
    try:
        await publish_doc_event(str(document_id), "failed", trimmed)
    except Exception:
        logger.exception("publish_failed_event_failed", extra={"document_id": str(document_id)})


async def _schedule_renewal_reminder(document: Document, user_id: str) -> None:
    """Insert a one-off renewal Reminder + APScheduler job for prescriptions.

    Fires at 9am (UTC — we don't have a guaranteed user tz on the document row
    and overriding via UserProfile would double the DB work here; if we need
    per-user local time we can upgrade this path later).
    """
    from uuid6 import uuid7

    from live150.db.models.reminder import Reminder
    from live150.reminders.jobs import fire_reminder, make_trigger
    from live150.reminders.parser import validate_schedule, ParsedSchedule
    from live150.reminders.scheduler import get_scheduler

    if not document.expiry_alert_date:
        return

    fire_at = datetime.combine(document.expiry_alert_date, time(9, 0), tzinfo=timezone.utc)
    if fire_at <= datetime.now(timezone.utc):
        logger.info(
            "doc_renewal_skip_past",
            extra={"document_id": str(document.document_id), "expiry": fire_at.isoformat()},
        )
        return

    schedule = ParsedSchedule(kind="once", expr=fire_at.isoformat(), timezone="UTC")
    if not validate_schedule(schedule):
        logger.warning(
            "doc_renewal_invalid_schedule",
            extra={"document_id": str(document.document_id), "expr": schedule.expr},
        )
        return

    reminder_id = uuid7()
    job_id = f"doc_renewal:{document.document_id}"
    title = f"Prescription renewal: {document.original_filename}"
    prompt = (
        f"The user's prescription documented in file '{document.original_filename}' "
        f"(document_id={document.document_id}) is approaching its refill/expiry "
        f"window. Summarize what needs to be refilled and suggest next steps."
    )

    async with async_session_factory() as db:
        db.add(
            Reminder(
                reminder_id=reminder_id,
                user_id=user_id,
                created_by="agent",
                title=title,
                prompt_template=prompt,
                schedule_kind=schedule.kind,
                schedule_expr=schedule.expr,
                timezone=schedule.timezone,
                job_id=job_id,
                status="active",
            )
        )
        await db.commit()

    try:
        trigger = make_trigger(schedule.kind, schedule.expr, schedule.timezone)
        get_scheduler().add_job(
            fire_reminder,
            trigger=trigger,
            args=[str(reminder_id)],
            id=job_id,
            name=title,
            replace_existing=True,
        )
    except Exception:
        logger.exception(
            "doc_renewal_schedule_failed",
            extra={"document_id": str(document.document_id), "job_id": job_id},
        )


async def process_document(document_id: str) -> None:
    """APScheduler entry point for analyzing an uploaded document."""
    # Function-local heavy imports so APScheduler can load this module cheaply.
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from live150.agent.doc_agent import DocAnalysis, build_doc_agent
    from live150.documents.events import publish_doc_event
    from live150.live150_client import get_client
    from live150.memory.service import MemoryService

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        logger.error("process_document: invalid document_id", extra={"document_id": document_id})
        return

    try:
        # 1. Load + transition to processing.
        async with async_session_factory() as db:
            document = (
                await db.execute(select(Document).where(Document.document_id == doc_uuid))
            ).scalar_one_or_none()

            if not document:
                logger.warning("process_document: not found", extra={"document_id": document_id})
                return
            if document.status not in ("uploaded", "failed"):
                logger.info(
                    "process_document: skipping, wrong status",
                    extra={"document_id": document_id, "status": document.status},
                )
                return

            document.status = "processing"
            document.error_message = None
            await db.commit()

            # Snapshot needed fields; session will close before the Gemini call.
            user_id = document.user_id
            gs_uri = document.storage_uri
            mime_type = document.mime_type
            hint_text = _build_hint_text(document)

        try:
            await publish_doc_event(document_id, "reading", "Maya is reading…")
        except Exception:
            logger.debug("publish reading event failed", exc_info=True)

        # 2. Impersonate to get access token for the sub-agent's tools.
        try:
            client = get_client()
            token_resp = await client.impersonate(user_id)
            access_token = token_resp.access_token
        except Exception as exc:
            logger.exception(
                "doc_impersonation_failed",
                extra={"document_id": document_id, "user_id": user_id},
            )
            await _mark_failed(doc_uuid, f"Impersonation failed: {exc}")
            return

        # 3. Build a throwaway ADK runner + session for the DocAgent.
        session_service = InMemorySessionService()
        session_id = f"doc_process:{document_id}"
        await session_service.create_session(
            app_name=_APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state={"access_token": access_token, "user_id": user_id},
        )
        runner = Runner(
            app_name=_APP_NAME,
            agent=build_doc_agent(),
            session_service=session_service,
        )

        content = types.Content(
            role="user",
            parts=[
                types.Part.from_uri(file_uri=gs_uri, mime_type=mime_type),
                types.Part.from_text(text=hint_text),
            ],
        )

        text_parts: list[str] = []
        seen_function_call = False
        pending_calls: set[str] = set()
        published_summarizing = False
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            if not getattr(event, "content", None):
                continue
            if not getattr(event.content, "parts", None):
                continue
            for part in event.content.parts:
                if getattr(part, "thought", None):
                    continue
                fc = getattr(part, "function_call", None)
                fr = getattr(part, "function_response", None)
                if fc:
                    if not seen_function_call:
                        seen_function_call = True
                        try:
                            await publish_doc_event(
                                document_id, "context", "Pulling your goals…"
                            )
                        except Exception:
                            logger.debug("publish context event failed", exc_info=True)
                    pending_calls.add(getattr(fc, "name", "") or f"call_{len(pending_calls)}")
                    continue
                if fr:
                    pending_calls.discard(getattr(fr, "name", "") or "")
                    if (
                        seen_function_call
                        and not pending_calls
                        and not published_summarizing
                    ):
                        published_summarizing = True
                        try:
                            await publish_doc_event(
                                document_id, "summarizing", "Summarizing…"
                            )
                        except Exception:
                            logger.debug("publish summarizing event failed", exc_info=True)
                    continue
                text = getattr(part, "text", None)
                if text:
                    if not published_summarizing:
                        published_summarizing = True
                        try:
                            await publish_doc_event(
                                document_id, "summarizing", "Summarizing…"
                            )
                        except Exception:
                            logger.debug("publish summarizing event failed", exc_info=True)
                    text_parts.append(text)

        raw = "".join(text_parts).strip()
        if not raw:
            logger.error(
                "doc_agent_empty_output",
                extra={"document_id": document_id},
            )
            await _mark_failed(doc_uuid, "DocAgent output invalid: empty response")
            return

        # 4. Parse + validate.
        cleaned = _strip_code_fences(raw)
        try:
            payload = json.loads(cleaned)
            analysis = DocAnalysis.model_validate(payload)
        except Exception as exc:
            logger.error(
                "doc_agent_parse_failed",
                extra={
                    "document_id": document_id,
                    "raw_preview": raw[:1000],
                    "error": str(exc),
                },
            )
            await _mark_failed(doc_uuid, f"DocAgent output invalid: {exc}")
            return

        # 5. Persist results to the Document row.
        now = datetime.now(timezone.utc)
        async with async_session_factory() as db:
            document = (
                await db.execute(select(Document).where(Document.document_id == doc_uuid))
            ).scalar_one_or_none()
            if not document:
                logger.warning(
                    "process_document: vanished mid-run", extra={"document_id": document_id}
                )
                return
            if document.status == "cancelled":
                logger.info(
                    "doc processing cancelled mid-flight",
                    extra={"document_id": document_id},
                )
                return
            document.doc_type = analysis.doc_type
            document.summary_detailed = analysis.summary_detailed
            document.extracted_text = analysis.extracted_text
            document.tags = list(analysis.tags)
            document.structured = analysis.structured or {}
            document.expiry_alert_date = analysis.expiry_alert_date
            document.status = "ready"
            document.processed_at = now
            document.error_message = None
            await db.commit()

            # Re-read for the renewal scheduler below (after commit, still bound).
            renewal_snapshot = document if document.expiry_alert_date else None
            ready_payload = _row_to_dict_for_event(document)

        try:
            await publish_doc_event(document_id, "ready", "Ready", payload=ready_payload)
        except Exception:
            logger.debug("publish ready event failed", exc_info=True)

        # 6. Mirror summary into memory.
        try:
            async with async_session_factory() as db:
                svc = MemoryService()
                await svc.save(
                    db=db,
                    user_id=user_id,
                    kind="document",
                    content=analysis.summary_detailed,
                    source="document",
                    source_ref=str(doc_uuid),
                    metadata={
                        "doc_type": analysis.doc_type,
                        "filename": renewal_snapshot.original_filename
                        if renewal_snapshot
                        else None,
                        "tags": list(analysis.tags),
                    },
                )
        except Exception:
            logger.exception(
                "doc_memory_save_failed",
                extra={"document_id": document_id, "user_id": user_id},
            )

        # 7. Renewal reminder (best-effort).
        if renewal_snapshot:
            try:
                await _schedule_renewal_reminder(renewal_snapshot, user_id)
            except Exception:
                logger.exception(
                    "doc_renewal_unexpected_failure",
                    extra={"document_id": document_id},
                )

        logger.info(
            "doc_processed",
            extra={
                "document_id": document_id,
                "user_id": user_id,
                "doc_type": analysis.doc_type,
                "has_expiry": analysis.expiry_alert_date is not None,
            },
        )

    except Exception as exc:
        logger.exception(
            "process_document_unhandled",
            extra={"document_id": document_id},
        )
        try:
            await _mark_failed(doc_uuid, str(exc))
        except Exception:
            logger.exception(
                "process_document_mark_failed_failed",
                extra={"document_id": document_id},
            )
