"""Chat endpoint — SSE streaming."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from live150.auth.middleware import AuthedUser, require_user, get_api_token
from live150.db.models.chat_session import ChatSession
from live150.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: uuid.UUID | None = None
    message: str


class SessionCreate(BaseModel):
    pass


class SessionListParams(BaseModel):
    limit: int = 20
    before: str | None = None


@router.post("")
async def chat(
    body: ChatRequest,
    user: AuthedUser = Depends(require_user),
    api_token: str = Depends(get_api_token),
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
        # Verify session belongs to user
        stmt = select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user.user_id,
            ChatSession.archived_at.is_(None),
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Session not found")

    async def event_stream():
        # Send session info first if new
        if new_session:
            yield {"event": "session", "data": json.dumps({"session_id": str(session_id)})}

        try:
            # In production, this would use the Live150Runner to stream agent events
            # For now, return a placeholder response
            yield {
                "event": "delta",
                "data": json.dumps({"text": f"Hello! I received your message: '{body.message}'. "
                                    "The agent is not yet wired to Vertex AI. "
                                    "This is a placeholder response."}),
            }
            yield {
                "event": "done",
                "data": json.dumps({"tokens_in": 0, "tokens_out": 0, "model": "placeholder"}),
            }
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
    """Create an empty chat session."""
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
    """List user's chat sessions (paginated)."""
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
    """Get message history for a session (paginated)."""
    from live150.db.models.chat_message import ChatMessage

    # Verify session ownership
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
            for m in reversed(messages)  # Return in chronological order
        ]
    }


@router.delete("/sessions/{session_id}")
async def archive_session(
    session_id: uuid.UUID,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Archive (soft-delete) a chat session."""
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
