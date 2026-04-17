import logging
import time
import uuid
from typing import Any

from live150.agent.model_router import choose_model
from live150.config import settings

logger = logging.getLogger(__name__)

# Tools that require user confirmation before execution
RISKY_TOOLS = {"cancel_workout_plan", "create_calendar_event", "send_calendar_invite"}

# Tools allowed during reminder-time runs (service token only)
REMINDER_SAFE_TOOLS = {
    "get_sleep_summary",
    "get_activity_summary",
    "get_meal_log",
    "search_memory",
    "list_reminders",
}

_turn_start_times: dict[str, float] = {}


def before_model_cb(callback_context: Any, llm_request: Any) -> None:
    """Called before every LLM call.

    - Stamps turn_start in audit
    - Applies model routing
    - Injects user profile summary
    """
    state = getattr(callback_context, "state", {})
    user_id = state.get("user_id", "unknown")
    session_id = state.get("session_id", "")

    # Track turn start time
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

    logger.info(
        "turn_start",
        extra={
            "user_id": user_id,
            "session_id": session_id,
            "model": chosen_model,
            "event": "turn_start",
        },
    )


def before_tool_cb(tool: Any, args: dict, tool_context: Any) -> Any:
    """Called before every tool execution.

    - Enforces reminder-mode tool allowlist
    - Intercepts risky tools → creates pending_confirmation
    """
    state = getattr(tool_context, "state", {})
    user_id = state.get("user_id", "unknown")
    turn_context = state.get("turn_context", "interactive")
    tool_name = getattr(tool, "name", str(tool))

    logger.info(
        "tool_call",
        extra={
            "user_id": user_id,
            "tool_name": tool_name,
            "event": "tool_call",
        },
    )

    # Reminder-mode restriction
    if turn_context == "reminder" and tool_name not in REMINDER_SAFE_TOOLS:
        return {
            "error": True,
            "message": f"Tool '{tool_name}' requires an active user session. "
            "This tool cannot be used during reminder runs. "
            "Suggest the user tap to continue in the app.",
        }

    # Risky tool interception
    if tool_name in RISKY_TOOLS:
        confirmation_id = str(uuid.uuid4())
        # In a real implementation, this would write to pending_confirmation table
        # via the DB session. For now, return a structured response.
        state["_pending_confirmation"] = {
            "confirmation_id": confirmation_id,
            "tool_name": tool_name,
            "tool_args": args,
        }
        return {
            "status": "awaiting_confirmation",
            "confirmation_id": confirmation_id,
            "message": f"This action requires your approval. Please confirm in the app.",
        }

    return None  # Proceed normally


def after_agent_cb(callback_context: Any) -> None:
    """Called after the agent completes a turn.

    - Writes turn_end audit row with tokens + latency
    """
    state = getattr(callback_context, "state", {})
    user_id = state.get("user_id", "unknown")
    session_id = state.get("session_id", "")

    key = f"{user_id}:{session_id}"
    start = _turn_start_times.pop(key, None)
    latency_ms = int((time.monotonic() - start) * 1000) if start else None

    logger.info(
        "turn_end",
        extra={
            "user_id": user_id,
            "session_id": session_id,
            "latency_ms": latency_ms,
            "event": "turn_end",
        },
    )
