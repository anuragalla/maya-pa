import re

# Only using Gemini 3.1 models — both default and lite
DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
LITE_MODEL = "gemini-3.1-flash-lite-preview"

_PLANNING_PATTERN = re.compile(
    r"\b(plan|analyze|compare|suggest|recommend|explain|why|how should|what if|help me decide|review)\b",
    re.IGNORECASE,
)


def choose_model(user_message: str, session_state: dict) -> str:
    """Decide per-turn whether to route to Flash or Flash-Lite."""
    turn_context = session_state.get("turn_context", "interactive")

    # Reminder turns always use Flash
    if turn_context == "reminder":
        return DEFAULT_MODEL

    # Planning verbs → Flash
    if user_message and _PLANNING_PATTERN.search(user_message):
        return DEFAULT_MODEL

    # Recent tool calls suggest complex interaction
    if session_state.get("recent_tool_call_count", 0) > 0:
        return DEFAULT_MODEL

    # Short, simple messages → Flash-Lite
    if not user_message or len(user_message) < 80:
        return LITE_MODEL

    return DEFAULT_MODEL
