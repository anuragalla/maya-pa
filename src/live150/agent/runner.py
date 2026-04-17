"""Thin wrapper around ADK Runner for Live150.

Design choice: We use ADK's built-in Runner and session management rather than
a custom DatabaseSessionService. ADK handles session persistence internally.
We write to chat_message and audit_log tables via callbacks for observability
and querying, but ADK's session state is the source of truth for the agent's
conversation context.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from live150.memory.service import MemoryService

logger = logging.getLogger(__name__)


class Live150Runner:
    def __init__(
        self,
        agent: LlmAgent,
        session_service: Any | None = None,
        memory_service: MemoryService | None = None,
    ):
        self.agent = agent
        self.session_service = session_service or InMemorySessionService()
        self.memory_service = memory_service
        self.runner = Runner(
            agent=self.agent,
            app_name="live150",
            session_service=self.session_service,
        )

    async def run_turn(
        self,
        user_id: str,
        session_id: uuid.UUID,
        api_token: str,
        message: str,
        turn_context: Literal["interactive", "reminder"] = "interactive",
    ) -> AsyncIterator[Any]:
        """Run a single agent turn, yielding ADK events.

        The HTTP layer transforms these into SSE frames.
        """
        from google.genai import types

        session = await self.session_service.get_session(
            app_name="live150",
            user_id=user_id,
            session_id=str(session_id),
        )

        if session is None:
            session = await self.session_service.create_session(
                app_name="live150",
                user_id=user_id,
                session_id=str(session_id),
                state={
                    "user_id": user_id,
                    "api_token": api_token,
                    "turn_context": turn_context,
                    "session_id": str(session_id),
                    "recent_tool_call_count": 0,
                },
            )
        else:
            # Update per-turn state
            session.state["api_token"] = api_token
            session.state["turn_context"] = turn_context

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)],
        )

        async for event in self.runner.run_async(
            user_id=user_id,
            session_id=str(session_id),
            new_message=content,
        ):
            yield event
