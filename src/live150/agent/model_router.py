import re

from live150.config import settings

# Verbs that suggest the user wants planning / complex reasoning → use Flash
_PLANNING_PATTERN = re.compile(
    r"\b(plan|analyze|compare|suggest|recommend|explain|why|how should|what if|help me decide|review)\b",
    re.IGNORECASE,
)


def choose_model(user_message: str, session_state: dict) -> str:
    """Decide per-turn whether to route to Flash or Flash-Lite.

    Returns the model ID string.

    Rules:
    - Reminder turns always use Flash (they need to be thoughtful).
    - Short messages (< 20 chars) with no planning verbs → Flash-Lite.
    - Messages with planning verbs → Flash.
    - If last 3 turns had tool calls → Flash (complex interaction).
    - Default → Flash-Lite for simple data queries.
    """
    turn_context = session_state.get("turn_context", "interactive")

    # Reminder turns are always Flash
    if turn_context == "reminder":
        return settings.default_model

    # Planning verbs → Flash
    if _PLANNING_PATTERN.search(user_message):
        return settings.default_model

    # Recent tool calls suggest complex interaction
    recent_tool_calls = session_state.get("recent_tool_call_count", 0)
    if recent_tool_calls > 0:
        return settings.default_model

    # Short, simple messages → Flash-Lite
    if len(user_message) < 80:
        return settings.lite_model

    # Default to Flash for longer messages
    return settings.default_model
