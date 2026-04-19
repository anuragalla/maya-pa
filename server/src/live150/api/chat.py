"""Chat endpoint — SSE streaming via ADK agent."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from live150.agent.builder import build_agent
from live150.agent.runner import Live150Runner
from live150.auth.middleware import AuthedUser, require_user
from live150.db.models.chat_session import ChatSession
from live150.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

# Singleton runner — built on first request
_runner: Live150Runner | None = None


def _get_runner() -> Live150Runner:
    global _runner
    if _runner is None:
        agent = build_agent()
        _runner = Live150Runner(agent=agent)
    return _runner


class ChatRequest(BaseModel):
    session_id: uuid.UUID | None = None
    message: str


@router.post("")
async def chat(
    body: ChatRequest,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream agent response as SSE."""
    session_id = body.session_id
    new_session = False

    if session_id is None:
        session_id = uuid7()
        new_session = True
        session_row = ChatSession(
            session_id=session_id,
            user_id=user.user_id,
            title=body.message[:100] if body.message else None,
        )
        db.add(session_row)
        await db.commit()
    else:
        stmt = select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user.user_id,
            ChatSession.archived_at.is_(None),
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Session not found")

    runner = _get_runner()

    async def event_stream():
        if new_session:
            yield {"event": "session", "data": json.dumps({"session_id": str(session_id)})}

        try:
            async for event in runner.run_turn(
                user_id=user.user_id,
                session_id=session_id,
                access_token=user.access_token,
                message=body.message,
            ):
                # ADK events have different shapes; extract text deltas
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            yield {
                                "event": "delta",
                                "data": json.dumps({"text": part.text}),
                            }
                        elif hasattr(part, "function_call") and part.function_call:
                            yield {
                                "event": "tool_call",
                                "data": json.dumps({
                                    "name": part.function_call.name,
                                    "args": dict(part.function_call.args) if part.function_call.args else {},
                                }),
                            }
                        elif hasattr(part, "function_response") and part.function_response:
                            yield {
                                "event": "tool_result",
                                "data": json.dumps({
                                    "name": part.function_response.name,
                                    "ok": True,
                                }),
                            }

            yield {"event": "done", "data": json.dumps({"status": "complete"})}

        except Exception:
            logger.exception("Error in chat stream", extra={"user_id": user.user_id})
            yield {
                "event": "error",
                "data": json.dumps({"code": "internal_error", "message": "An error occurred"}),
            }

    return EventSourceResponse(event_stream())


@router.post("/sessions")
async def create_session(
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    session_id = uuid7()
    session_row = ChatSession(session_id=session_id, user_id=user.user_id)
    db.add(session_row)
    await db.commit()
    return {"session_id": str(session_id)}


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    before: str | None = None,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user.user_id, ChatSession.archived_at.is_(None))
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
    )
    if before:
        from datetime import datetime
        stmt = stmt.where(ChatSession.updated_at < datetime.fromisoformat(before))

    result = await db.execute(stmt)
    sessions = result.scalars().all()
    return {
        "sessions": [
            {
                "session_id": str(s.session_id),
                "title": s.title,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in sessions
        ]
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: uuid.UUID,
    limit: int = 50,
    before: str | None = None,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    from live150.db.models.chat_message import ChatMessage

    sess_stmt = select(ChatSession).where(
        ChatSession.session_id == session_id,
        ChatSession.user_id == user.user_id,
    )
    if (await db.execute(sess_stmt)).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session not found")

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    if before:
        from datetime import datetime
        stmt = stmt.where(ChatMessage.created_at < datetime.fromisoformat(before))

    result = await db.execute(stmt)
    messages = result.scalars().all()
    return {
        "messages": [
            {
                "message_id": str(m.message_id),
                "role": m.role,
                "content": m.content,
                "model": m.model,
                "created_at": m.created_at.isoformat(),
            }
            for m in reversed(messages)
        ]
    }


@router.delete("/sessions/{session_id}")
async def archive_session(
    session_id: uuid.UUID,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    stmt = select(ChatSession).where(
        ChatSession.session_id == session_id,
        ChatSession.user_id == user.user_id,
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.archived_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "archived"}
