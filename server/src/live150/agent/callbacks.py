import logging
import time
from typing import Any

from google.genai import types

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
    - Sets thinking level to high
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

    # Reminders don't need deep reasoning — disable thinking to keep them fast
    thinking_budget = 0 if state.get("turn_context") == "reminder" else 8192
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

    logger.info("turn_start", extra={"user_id": user_id, "model": chosen_model, "event": "turn_start"})


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


def after_agent_cb(callback_context: Any) -> None:
    """Called after the agent completes a turn."""
    state = getattr(callback_context, "state", {})
    user_id = state.get("user_id", "unknown")
    session_id = state.get("session_id", "")

    key = f"{user_id}:{session_id}"
    start = _turn_start_times.pop(key, None)
    latency_ms = int((time.monotonic() - start) * 1000) if start else None

    logger.info("turn_end", extra={"user_id": user_id, "latency_ms": latency_ms, "event": "turn_end"})
