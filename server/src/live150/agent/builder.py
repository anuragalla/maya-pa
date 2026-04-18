import logging
from pathlib import Path
from typing import Any

from google.adk.agents import LlmAgent

from live150.agent.callbacks import after_agent_cb, before_model_cb, before_tool_cb
from live150.agent.model_router import DEFAULT_MODEL
from live150.tools.registry import build_tool_registry

logger = logging.getLogger(__name__)

_AGENT_DIR = Path(__file__).parent
_SOUL_PATH = _AGENT_DIR / "SOUL.md"
_AGENTS_PATH = _AGENT_DIR / "AGENTS.md"

_agent: LlmAgent | None = None
_base_instruction: str | None = None


def _load_base_instruction() -> str:
    """Load SOUL.md + AGENTS.md once at startup."""
    parts = []
    for path in (_SOUL_PATH, _AGENTS_PATH):
        if not path.exists():
            raise FileNotFoundError(f"Required prompt file not found: {path}")
        parts.append(path.read_text(encoding="utf-8"))
    text = "\n\n---\n\n".join(parts)
    logger.info("SOUL loaded", extra={"files": [p.name for p in (_SOUL_PATH, _AGENTS_PATH)], "chars": len(text)})
    return text


def _dynamic_instruction(callback_context: Any) -> str:
    """Build the full instruction with live context injected from session state.

    ADK calls this on every turn so the model always sees current time and profile.
    """
    state = getattr(callback_context, "state", {})
    local_time = state.get("user_local_time", "unknown")
    timezone = state.get("user_timezone", "UTC")
    profile = state.get("user_profile_summary", "")

    context_block = (
        f"\n\n---\n\n## Current context\n\n"
        f"- **User's local time:** {local_time}\n"
        f"- **Timezone:** {timezone}\n"
    )
    if profile:
        context_block += f"\n### User profile\n\n{profile}\n"

    return _base_instruction + context_block


def build_agent() -> LlmAgent:
    """Build the singleton LlmAgent."""
    global _agent, _base_instruction
    if _agent is not None:
        return _agent

    _base_instruction = _load_base_instruction()
    tools = build_tool_registry()

    _agent = LlmAgent(
        name="live150",
        model=DEFAULT_MODEL,
        instruction=_dynamic_instruction,
        tools=tools,
        before_model_callback=before_model_cb,
        before_tool_callback=before_tool_cb,
        after_agent_callback=after_agent_cb,
    )

    logger.info("Agent built", extra={"model": DEFAULT_MODEL, "tool_count": len(tools)})
    return _agent
