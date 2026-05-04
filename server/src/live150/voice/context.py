"""Build system prompt and user context for voice sessions."""

from datetime import datetime, timezone
from pathlib import Path

_SOUL_PATH = Path(__file__).resolve().parent.parent / "agent" / "SOUL.md"

_VOICE_ADDENDUM = """
You are speaking aloud in a real-time voice conversation. Follow these voice-specific rules:

- Keep responses to 1-3 sentences. Brevity is critical — the user is listening, not reading.
- Never use markdown, bullets, numbered lists, or formatting. Speak naturally.
- Never spell out URLs, code, or structured data. Say "I'll save that" or "check your app for details."
- Use natural speech fillers sparingly ("let me check", "so") — don't be robotic.
- When you use a tool, don't narrate it. Just pause briefly and continue with the answer.
- If the answer would be long (meal plans, multi-day summaries), give a 1-sentence summary and say "I've put the details in your app" — then save a note via memory.
- Match the user's energy. Short question → short answer. Excited → match warmth.
"""


def build_system_prompt() -> str:
    soul = _SOUL_PATH.read_text()
    return f"{soul}\n\n---\n\n## Voice Mode\n{_VOICE_ADDENDUM}"


def build_user_context(
    display_name: str,
    age: int | None,
    goals: list[str],
    conditions: list[str],
    timezone_name: str,
    memories: list[str],
) -> str:
    now = datetime.now(timezone.utc)
    parts = [
        f"User: {display_name}",
    ]
    if age is not None:
        parts.append(f"Age: {age}")
    if goals:
        parts.append(f"Goals: {', '.join(goals)}")
    if conditions:
        parts.append(f"Health conditions: {', '.join(conditions)}")
    parts.append(f"Timezone: {timezone_name}")
    parts.append(f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M')}")

    if memories:
        parts.append("\nRecent context:")
        for mem in memories:
            parts.append(f"- {mem}")
    else:
        parts.append("\nNo prior context available.")

    return "\n".join(parts)
