"""Post-turn reflection: extract durable memories from a completed exchange.

After every interactive turn, a cheap Flash-Lite call scans the user message
and agent response for facts, preferences, events, or notes worth persisting
to long-term memory (pgvector). Runs as a fire-and-forget background task so
it never adds latency to the streamed response.
"""

import asyncio
import logging
from typing import Literal

from pydantic import BaseModel

from live150.agent.genai_client import get_genai_client
from live150.agent.model_router import LITE_MODEL
from live150.db.session import async_session_factory
from live150.memory.service import MemoryService

logger = logging.getLogger(__name__)

_memory_service = MemoryService()

_REFLECTION_PROMPT = """\
You are a memory extraction assistant. Read the exchange below between a user \
and a health coach AI and extract any information worth remembering long-term \
about the user.

Only extract information that is:
- A durable personal fact (e.g. "user is vegetarian", "user has diabetes")
- A stated preference (e.g. "user hates morning workouts", "prefers Indian food")
- A reported behavioural event (e.g. "user skipped dinner on Monday", "slept 5h last night")
- An agent recommendation the user acknowledged (e.g. "agent suggested 7pm dinner cutoff")

Do NOT extract:
- Information already obvious from general health knowledge
- Live telemetry (step counts, sleep scores) — that's fetched fresh from APIs
- Greetings, chit-chat, or anything ephemeral

Return a JSON array. Each item: {{"kind": "fact"|"preference"|"event"|"note", "content": "..."}}
Return an empty array [] if there is nothing worth saving.

--- USER MESSAGE ---
{user_message}

--- AGENT RESPONSE ---
{agent_response}
"""


class _MemoryItem(BaseModel):
    kind: Literal["fact", "preference", "event", "note"]
    content: str


class _ExtractionResult(BaseModel):
    items: list[_MemoryItem]


async def reflect_and_save(
    user_id: str,
    session_id: str,
    user_message: str,
    agent_response: str,
) -> None:
    """Extract memories from a completed turn and persist them.

    Designed to be called via asyncio.create_task — errors are logged, never raised.
    """
    if not user_message.strip() or not agent_response.strip():
        return

    try:
        client = get_genai_client()
        resp = await client.aio.models.generate_content(
            model=LITE_MODEL,
            contents=_REFLECTION_PROMPT.format(
                user_message=user_message[:2000],
                agent_response=agent_response[:3000],
            ),
            config={
                "response_mime_type": "application/json",
                "response_schema": list[_MemoryItem],
            },
        )
        items: list[_MemoryItem] = resp.parsed or []
    except Exception as e:
        logger.warning("Reflection LLM call failed", extra={"user_id": user_id, "error": str(e)})
        return

    if not items:
        return

    async with async_session_factory() as db:
        for item in items:
            try:
                await _memory_service.save(
                    db=db,
                    user_id=user_id,
                    kind=item.kind,
                    content=item.content,
                    source="agent",
                    source_ref=session_id,
                )
                logger.info(
                    "memory_saved_from_reflection",
                    extra={"user_id": user_id, "kind": item.kind, "content": item.content[:80]},
                )
            except Exception as e:
                logger.warning(
                    "Failed to save reflection memory",
                    extra={"user_id": user_id, "kind": item.kind, "error": str(e)},
                )


def schedule_reflection(
    user_id: str,
    session_id: str,
    user_message: str,
    agent_response: str,
) -> None:
    """Fire reflect_and_save as a background task (non-blocking)."""
    asyncio.create_task(
        reflect_and_save(user_id, session_id, user_message, agent_response),
        name=f"reflection:{user_id}",
    )
