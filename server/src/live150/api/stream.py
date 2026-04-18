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

import json
import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from live150.agent.builder import build_agent
from live150.agent.runner import Live150Runner
from live150.live150_client import get_client

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stream"])

_runner: Live150Runner | None = None


def _get_runner() -> Live150Runner:
    global _runner
    if _runner is None:
        _runner = Live150Runner(agent=build_agent())
    return _runner


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


@router.post("/api/chat")
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
    session_id = uuid.uuid4()
    tool_call_counter = 0
    tool_name_to_call_id: dict[str, str] = {}
    pending_calls: set[str] = set()  # call_ids awaiting results
    text_buffer: list[str] = []  # text held until tools resolve

    async def generate():
        nonlocal tool_call_counter
        try:
            async for event in runner.run_turn(
                user_id=phone,
                session_id=session_id,
                access_token=access_token,
                message=last_msg["content"],
            ):
                if not hasattr(event, "content") or not event.content:
                    continue
                if not hasattr(event.content, "parts") or not event.content.parts:
                    continue

                for part in event.content.parts:
                    # Skip thinking/reasoning parts — don't stream internal model thoughts
                    if hasattr(part, "thought") and part.thought:
                        continue

                    # Text delta — buffer if tools are pending
                    if hasattr(part, "text") and part.text:
                        if pending_calls:
                            text_buffer.append(part.text)
                        else:
                            # Flush any buffered text first
                            for buffered in text_buffer:
                                yield f"0:{json.dumps(buffered)}\n"
                            text_buffer.clear()
                            yield f"0:{json.dumps(part.text)}\n"

                    # Tool call — stream immediately so UI shows the pill
                    elif hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        tool_call_counter += 1
                        call_id = f"call_{tool_call_counter}"
                        tool_name_to_call_id[fc.name] = call_id
                        pending_calls.add(call_id)
                        args = dict(fc.args) if fc.args else {}
                        yield f"b:{json.dumps({'toolCallId': call_id, 'toolName': fc.name, 'args': args})}\n"

                    # Tool result — stream immediately, flush text if all tools done
                    elif hasattr(part, "function_response") and part.function_response:
                        fr = part.function_response
                        fn_name = fr.name if hasattr(fr, "name") else ""
                        call_id = tool_name_to_call_id.get(fn_name, f"call_{tool_call_counter}")
                        pending_calls.discard(call_id)
                        result = fr.response if hasattr(fr, "response") else {}
                        yield f"a:{json.dumps({'toolCallId': call_id, 'result': result})}\n"

                        # All tools resolved — flush buffered text
                        if not pending_calls and text_buffer:
                            for buffered in text_buffer:
                                yield f"0:{json.dumps(buffered)}\n"
                            text_buffer.clear()

            # Flush any remaining buffered text
            for buffered in text_buffer:
                yield f"0:{json.dumps(buffered)}\n"
            text_buffer.clear()

            finish = {"finishReason": "stop", "usage": {"promptTokens": 0, "completionTokens": 0}}
            yield f"e:{json.dumps({**finish, 'isContinued': False})}\n"
            yield f"d:{json.dumps(finish)}\n"

        except Exception as e:
            logger.exception("Stream error", extra={"phone": phone})
            yield f"0:{json.dumps(f'Something went wrong: {e}')}\n"
            finish = {"finishReason": "error", "usage": {"promptTokens": 0, "completionTokens": 0}}
            yield f"e:{json.dumps({**finish, 'isContinued': False})}\n"
            yield f"d:{json.dumps(finish)}\n"

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Vercel-AI-Data-Stream": "v1"},
    )
