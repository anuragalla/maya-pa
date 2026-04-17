import logging
from pathlib import Path

from google.adk.agents import LlmAgent

from live150.agent.callbacks import after_agent_cb, before_model_cb, before_tool_cb
from live150.config import settings
from live150.tools.registry import build_tool_registry

logger = logging.getLogger(__name__)

_SOUL_PATH = Path(__file__).parent / "soul.md"

_agent: LlmAgent | None = None


def _load_soul_md() -> str:
    """Load the SOUL prompt from soul.md."""
    if not _SOUL_PATH.exists():
        raise FileNotFoundError(f"SOUL file not found at {_SOUL_PATH}")
    return _SOUL_PATH.read_text(encoding="utf-8")


def build_agent() -> LlmAgent:
    """Build the singleton LlmAgent.

    Loads SOUL from agent/soul.md, registers all tools, installs callbacks.
    """
    global _agent
    if _agent is not None:
        return _agent

    soul = _load_soul_md()
    tools = build_tool_registry()

    _agent = LlmAgent(
        name="live150",
        model=settings.default_model,
        instruction=soul,
        tools=tools,
        before_model_callback=before_model_cb,
        before_tool_callback=before_tool_cb,
        after_agent_callback=after_agent_cb,
    )

    logger.info("Agent built", extra={"model": settings.default_model, "tool_count": len(tools)})
    return _agent
