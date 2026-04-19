"""Vercel AI SDK data stream protocol endpoint.

Speaks the data stream protocol so the React frontend can use `useChat`
from @ai-sdk/react with the default `streamProtocol: 'data'`.

Protocol format — each line is TYPE_CODE:JSON_VALUE\n:
  0:"text chunk"           — text delta
  b:{toolCallId,toolName,args}  — tool call
  a:{toolCallId,result}    — tool result
  e:{finishReason,usage}   — step finish
  d:{finishReason,usage}   — message finish

Buffering: text is held until all pending tool calls resolve.
Tool call pills stream immediately so the UI shows progress.
"""

import hashlib
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from live150.agent.builder import build_agent
from live150.agent.runner import Live150Runner
from live150.auth.middleware import AuthedUser, require_user
from live150.db.models.chat_message import ChatMessage
from live150.db.models.chat_session import ChatSession
from live150.db.session import async_session_factory, get_db
from live150.live150_client import get_client

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stream"])

_SUGGEST_OPEN = "<suggestions>"
_SUGGEST_CLOSE = "</suggestions>"

_runner: Live150Runner | None = None


def _get_runner() -> Live150Runner:
    global _runner
    if _runner is None:
        _runner = Live150Runner(agent=build_agent())
    return _runner


def _deterministic_session_id(phone: str) -> uuid.UUID:
    """Same phone → same session ID. One user, one conversation."""
    return uuid.UUID(hashlib.md5(f"live150:session:{phone}".encode()).hexdigest())


def _text_response(text: str):
    """Return a complete data-stream response with just a text message."""
    finish = {"finishReason": "stop", "usage": {"promptTokens": 0, "completionTokens": 0}}

    def gen():
        yield f"0:{json.dumps(text)}\n"
        yield f"e:{json.dumps({**finish, 'isContinued': False})}\n"
        yield f"d:{json.dumps(finish)}\n"

    return StreamingResponse(
        gen(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Vercel-AI-Data-Stream": "v1"},
    )


@router.get("/history")
async def get_history(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return past messages for the user's single persistent session."""
    phone = request.headers.get("x-phone-number", "")
    if not phone:
        return {"messages": []}

    session_id = _deterministic_session_id(phone)

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(100)
    )
    rows = (await db.execute(stmt)).scalars().all()

    messages = []
    for m in rows:
        content = m.content
        created_at = m.created_at.isoformat() if m.created_at else None
        if isinstance(content, str):
            msg = {"id": str(m.message_id), "role": m.role, "content": content, "createdAt": created_at}
        elif isinstance(content, dict):
            msg = {"id": str(m.message_id), "role": m.role, **content, "createdAt": created_at}
        else:
            msg = {"id": str(m.message_id), "role": m.role, "content": str(content), "createdAt": created_at}
        messages.append(msg)

    return {"messages": messages}


@router.post("/chat")
async def stream_chat(request: Request):
    """Vercel AI SDK compatible streaming chat endpoint."""
    body = await request.json()
    messages = body.get("messages", [])
    phone = request.headers.get("x-phone-number", "")

    if not phone:
        return _text_response("No phone number provided. Please select a user from the dropdown.")

    last_msg = next((m for m in reversed(messages) if m["role"] == "user"), None)
    if not last_msg:
        return _text_response("I didn't receive a message. Try again?")

    # Impersonate user
    try:
        client = get_client()
        token_resp = await client.impersonate(phone)
        access_token = token_resp.access_token
    except Exception as e:
        error_str = str(e)
        logger.error("Impersonation failed", extra={"phone": phone, "error": error_str})
        if "409" in error_str or "refresh token" in error_str.lower():
            return _text_response(
                "I can't connect to this user's account right now — "
                "they need to log in on the Live150 app first to generate a session token. "
                "Try Nigel (+19084329987) who has an active session."
            )
        return _text_response(f"I couldn't authenticate this user. Error: {error_str}")

    runner = _get_runner()
    session_id = _deterministic_session_id(phone)
    tool_call_counter = 0
    tool_name_to_call_id: dict[str, str] = {}
    pending_calls: set[str] = set()
    text_buffer: list[str] = []
    assistant_text_parts: list[str] = []

    # Ensure chat_session row exists
    async with async_session_factory() as db:
        existing = (await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )).scalar_one_or_none()
        if not existing:
            db.add(ChatSession(session_id=session_id, user_id=phone))
            await db.commit()

    # Persist the user message
    user_msg_content = last_msg["content"]
    async with async_session_factory() as db:
        db.add(ChatMessage(
            message_id=uuid7(),
            session_id=session_id,
            user_id=phone,
            role="user",
            content=user_msg_content,
        ))
        await db.commit()

    def _flush_text(chunk: str) -> list[str]:
        """Append chunk to assistant text, emit or buffer depending on pending tool calls."""
        assistant_text_parts.append(chunk)
        if pending_calls:
            text_buffer.append(chunk)
            return []
        lines = [f"0:{json.dumps(b)}\n" for b in text_buffer]
        text_buffer.clear()
        lines.append(f"0:{json.dumps(chunk)}\n")
        return lines

    async def generate():
        nonlocal tool_call_counter

        in_suggestions = False
        suggestions_parts: list[str] = []
        pending_tail = ""  # chars held back in case they start the <suggestions> tag

        try:
            async for event in runner.run_turn(
                user_id=phone,
                session_id=session_id,
                access_token=access_token,
                message=user_msg_content,
            ):
                if not hasattr(event, "content") or not event.content:
                    continue
                if not hasattr(event.content, "parts") or not event.content.parts:
                    continue

                for part in event.content.parts:
                    # Skip thinking/reasoning parts — don't stream internal model thoughts
                    if hasattr(part, "thought") and part.thought:
                        continue

                    # Text delta — buffer if tools are pending, strip suggestions tag
                    if hasattr(part, "text") and part.text:
                        if in_suggestions:
                            suggestions_parts.append(part.text)
                            continue

                        text = pending_tail + part.text
                        pending_tail = ""

                        if _SUGGEST_OPEN in text:
                            pre, _, post = text.partition(_SUGGEST_OPEN)
                            if pre.strip():
                                for line in _flush_text(pre):
                                    yield line
                            in_suggestions = True
                            suggestions_parts.append(post)
                        else:
                            # Hold back chars that could be the start of the tag
                            tail_idx = text.rfind("<")
                            if tail_idx != -1 and _SUGGEST_OPEN.startswith(text[tail_idx:]):
                                pending_tail = text[tail_idx:]
                                safe = text[:tail_idx]
                            else:
                                safe = text
                            if safe:
                                for line in _flush_text(safe):
                                    yield line

                    # Tool call — stream immediately so UI shows the pill
                    elif hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        tool_call_counter += 1
                        call_id = f"call_{tool_call_counter}"
                        tool_name_to_call_id[fc.name] = call_id
                        pending_calls.add(call_id)
                        args = dict(fc.args) if fc.args else {}
                        yield f"b:{json.dumps({'toolCallId': call_id, 'toolName': fc.name, 'args': args})}\n"

                    # Tool result — flush buffered text once all tools resolve
                    elif hasattr(part, "function_response") and part.function_response:
                        fr = part.function_response
                        fn_name = fr.name if hasattr(fr, "name") else ""
                        call_id = tool_name_to_call_id.get(fn_name, f"call_{tool_call_counter}")
                        pending_calls.discard(call_id)
                        result = fr.response if hasattr(fr, "response") else {}
                        yield f"a:{json.dumps({'toolCallId': call_id, 'result': result})}\n"

                        if not pending_calls and text_buffer:
                            for buffered in text_buffer:
                                yield f"0:{json.dumps(buffered)}\n"
                            text_buffer.clear()

            # Flush any pending tail that never became a suggestions tag
            if pending_tail:
                for line in _flush_text(pending_tail):
                    yield line

            # Flush remaining text buffer
            for buffered in text_buffer:
                yield f"0:{json.dumps(buffered)}\n"
            text_buffer.clear()

            # Emit suggestions as Vercel AI data chunk
            if suggestions_parts:
                raw = "".join(suggestions_parts).replace(_SUGGEST_CLOSE, "").strip()
                try:
                    items = json.loads(raw)
                    if isinstance(items, list):
                        yield f"2:{json.dumps([{'type': 'suggestions', 'items': items}])}\n"
                except Exception:
                    logger.debug("Failed to parse suggestions JSON: %s", raw[:200])

            finish = {"finishReason": "stop", "usage": {"promptTokens": 0, "completionTokens": 0}}
            yield f"e:{json.dumps({**finish, 'isContinued': False})}\n"
            yield f"d:{json.dumps(finish)}\n"

        except Exception as e:
            logger.exception("Stream error", extra={"phone": phone})
            error_text = f"Something went wrong: {e}"
            assistant_text_parts.append(error_text)
            yield f"0:{json.dumps(error_text)}\n"
            finish = {"finishReason": "error", "usage": {"promptTokens": 0, "completionTokens": 0}}
            yield f"e:{json.dumps({**finish, 'isContinued': False})}\n"
            yield f"d:{json.dumps(finish)}\n"

        # Persist assistant response after stream completes
        full_text = "".join(assistant_text_parts)
        if full_text.strip():
            try:
                async with async_session_factory() as db:
                    db.add(ChatMessage(
                        message_id=uuid7(),
                        session_id=session_id,
                        user_id=phone,
                        role="model",
                        content=full_text,
                    ))
                    await db.commit()
            except Exception:
                logger.warning("Failed to persist assistant message", exc_info=True)

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Vercel-AI-Data-Stream": "v1"},
    )
