import asyncio
import logging
import time
import uuid
from typing import Any

from google.genai import types

from live150.agent import caching
from live150.agent.model_router import choose_model

logger = logging.getLogger(__name__)

# Tools allowed during reminder-time runs (service token only)
REMINDER_SAFE_TOOLS = {
    "get_holistic_analysis",
    "get_progress_by_date",
    "get_health_goals",
    "search_memory",
    "list_reminders",
    "skill_search",
    "skill_load",
    "get_calendar_schedule",
    "check_calendar_connection",
    "find_free_slots",
    "list_available_integrations",
}

_turn_start_times: dict[str, float] = {}


def before_model_cb(callback_context: Any, llm_request: Any) -> None:
    """Called before every LLM call.

    - Applies model routing
    - Sets thinking budget (flat 512 on interactive, 0 on reminders)
    - Stashes the chosen model in state for after_model_cb to read
    """
    state = getattr(callback_context, "state", {})
    user_id = state.get("user_id", "unknown")
    session_id = state.get("session_id", "")

    _turn_start_times[f"{user_id}:{session_id}"] = time.monotonic()

    # Model routing
    user_message = ""
    if hasattr(llm_request, "contents") and llm_request.contents:
        last_content = llm_request.contents[-1]
        if hasattr(last_content, "parts"):
            for part in last_content.parts:
                if hasattr(part, "text"):
                    user_message = part.text
                    break

    chosen_model = choose_model(user_message, state)
    if hasattr(llm_request, "model"):
        llm_request.model = chosen_model

    # Stash for after_model_cb — llm_response doesn't carry the model name reliably
    try:
        state["_last_model"] = chosen_model
    except TypeError:
        pass  # read-only mapping in some ADK versions

    # Flat thinking budget: 0 on background reminder turns, 512 on interactive.
    # Reduced from 8192 on 2026-04-19 — see docs/spec/cost-reduction-plan.md §Step 2.
    thinking_budget = 0 if state.get("turn_context") == "reminder" else 512
    if hasattr(llm_request, "config") and llm_request.config is not None:
        llm_request.config.thinking_config = types.ThinkingConfig(
            thinking_budget=thinking_budget,
        )
    elif hasattr(llm_request, "config"):
        llm_request.config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=thinking_budget,
            ),
        )

    # Explicit context caching — swap the static prefix for a cache reference
    # and move the dynamic context into the user message.
    cache_name = caching.get_cache_name()
    if cache_name and hasattr(llm_request, "config") and llm_request.config is not None:
        try:
            # Clear any system_instruction — cache provides it; sending both is a conflict.
            if hasattr(llm_request.config, "system_instruction"):
                llm_request.config.system_instruction = None
            llm_request.config.cached_content = cache_name

            # Prepend dynamic context (local time, profile, etc.) to the last user message.
            dynamic = caching.build_dynamic_context(state)
            if dynamic and hasattr(llm_request, "contents") and llm_request.contents:
                last = llm_request.contents[-1]
                if getattr(last, "role", None) == "user" and getattr(last, "parts", None):
                    first_part = last.parts[0]
                    existing = getattr(first_part, "text", "") or ""
                    first_part.text = f"<context>\n{dynamic}\n</context>\n\n{existing}"
        except Exception as e:
            logger.warning("Cache wiring failed; falling back to inline", extra={"error": str(e)})

    logger.info("turn_start", extra={"user_id": user_id, "model": chosen_model, "event": "turn_start"})


def after_model_cb(callback_context: Any, llm_response: Any) -> None:
    """Called after every LLM call — captures token telemetry.

    Fires a fire-and-forget task to write the audit row so we never block the
    stream. Errors are logged and swallowed.
    """
    usage = getattr(llm_response, "usage_metadata", None)
    if usage is None:
        return

    state = getattr(callback_context, "state", {})
    user_id = state.get("user_id", "unknown")
    session_id_str = state.get("session_id", "")
    model = state.get("_last_model")
    turn_context = state.get("turn_context", "interactive")

    # Pull counts defensively — the SDK names vary across preview versions.
    tokens_in = getattr(usage, "prompt_token_count", None)
    tokens_out = getattr(usage, "candidates_token_count", None)
    cached_tokens = getattr(usage, "cached_content_token_count", None) or 0
    thoughts_tokens = getattr(usage, "thoughts_token_count", None) or 0

    asyncio.create_task(
        _persist_llm_audit(
            user_id=user_id,
            session_id_str=session_id_str,
            model=model,
            turn_context=turn_context,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cached_tokens=cached_tokens,
            thoughts_tokens=thoughts_tokens,
        ),
        name=f"audit:{user_id}",
    )


async def _persist_llm_audit(
    *,
    user_id: str,
    session_id_str: str,
    model: str | None,
    turn_context: str,
    tokens_in: int | None,
    tokens_out: int | None,
    cached_tokens: int,
    thoughts_tokens: int,
) -> None:
    """Write one llm_call audit row. Never raises."""
    try:
        from live150.audit.logger import write_audit
        from live150.db.session import async_session_factory

        session_uuid: uuid.UUID | None = None
        if session_id_str:
            try:
                session_uuid = uuid.UUID(session_id_str)
            except ValueError:
                session_uuid = None

        payload = {
            "turn_context": turn_context,
            "cache_hit_ratio": (
                round(cached_tokens / tokens_in, 3) if tokens_in else 0.0
            ),
        }

        async with async_session_factory() as db:
            await write_audit(
                db=db,
                user_id=user_id,
                event_type="llm_call",
                event_payload=payload,
                session_id=session_uuid,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cached_tokens=cached_tokens,
                thoughts_tokens=thoughts_tokens,
            )
            await db.commit()
    except Exception as e:
        logger.warning(
            "Failed to persist llm_call audit",
            extra={"user_id": user_id, "error": str(e)},
        )


def before_tool_cb(tool: Any, args: dict, tool_context: Any) -> Any:
    """Called before every tool execution."""
    state = getattr(tool_context, "state", {})
    user_id = state.get("user_id", "unknown")
    turn_context = state.get("turn_context", "interactive")
    tool_name = getattr(tool, "name", str(tool))

    logger.info("tool_call", extra={"user_id": user_id, "tool_name": tool_name, "event": "tool_call"})

    # Reminder-mode restriction
    if turn_context == "reminder" and tool_name not in REMINDER_SAFE_TOOLS:
        return {
            "error": True,
            "message": f"Tool '{tool_name}' requires an active user session. "
            "Suggest the user tap to continue in the app.",
        }

    return None


def after_tool_cb(tool: Any, args: dict, tool_context: Any, tool_response: Any) -> None:
    """Called after every tool execution.

    When the health_search sub-agent completes, stores (query, summary) in
    session state under _search_log so the main agent has a record without
    holding the raw search data in its context.
    """
    tool_name = getattr(tool, "name", str(tool))

    if tool_name != "health_search":
        return None

    state = getattr(tool_context, "state", {})
    user_id = state.get("user_id", "unknown")
    query = args.get("request", "")
    summary = tool_response if isinstance(tool_response, str) else str(tool_response)

    search_log = list(state.get("_search_log", []))
    search_log.append({"query": query, "summary": summary})
    state["_search_log"] = search_log[-5:]  # keep last 5

    logger.info(
        "search_complete",
        extra={"user_id": user_id, "query": query, "event": "search_complete"},
    )
    return None


def after_agent_cb(callback_context: Any) -> None:
    """Called after the agent completes a turn."""
    state = getattr(callback_context, "state", {})
    user_id = state.get("user_id", "unknown")
    session_id = state.get("session_id", "")

    key = f"{user_id}:{session_id}"
    start = _turn_start_times.pop(key, None)
    latency_ms = int((time.monotonic() - start) * 1000) if start else None

    logger.info("turn_end", extra={"user_id": user_id, "latency_ms": latency_ms, "event": "turn_end"})
