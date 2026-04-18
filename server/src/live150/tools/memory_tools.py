"""Memory tools — wired to pgvector hybrid search via MemoryService."""

import logging

from live150.db.session import async_session_factory
from live150.memory.service import MemoryService

logger = logging.getLogger(__name__)

_memory_service = MemoryService()


async def search_memory(query: str, limit: int = 5, tool_context=None) -> dict:
    """Search the user's long-term memory for relevant information.

    Use this to recall facts, preferences, and past events the user has shared.
    Returns the most relevant memories ranked by hybrid vector + text search.

    Args:
        query: What to search for (e.g., "dietary restrictions", "sleep preferences").
        limit: Maximum number of results to return (default 5).
    """
    user_id = tool_context.state["user_id"]

    async with async_session_factory() as db:
        try:
            hits = await _memory_service.recall(
                db=db,
                user_id=user_id,
                query=query,
                limit=limit,
            )
        except Exception as e:
            logger.warning("Memory search failed", extra={"user_id": user_id, "error": str(e)})
            return {"results": [], "message": "Memory search unavailable — database may not be initialized yet."}

    if not hits:
        return {"results": [], "message": "No matching memories found."}

    return {
        "results": [
            {
                "kind": hit.kind,
                "content": hit.content,
                "source": hit.source,
                "score": round(hit.score, 3),
            }
            for hit in hits
        ]
    }


async def save_memory(kind: str, content: str, tool_context=None) -> dict:
    """Save a fact, preference, event, or note to the user's long-term memory.

    Use this when the user shares something worth remembering across sessions:
    dietary preferences, health conditions, personal goals, life events, etc.

    Args:
        kind: One of 'fact', 'preference', 'event', 'note'.
        content: The information to remember. Be specific and concise.
    """
    user_id = tool_context.state["user_id"]
    session_id = tool_context.state.get("session_id")

    if kind not in ("fact", "preference", "event", "note"):
        return {"error": True, "message": f"Invalid kind '{kind}'. Must be one of: fact, preference, event, note."}

    async with async_session_factory() as db:
        try:
            memory_id = await _memory_service.save(
                db=db,
                user_id=user_id,
                kind=kind,
                content=content,
                source="agent",
                source_ref=session_id,
            )
        except Exception as e:
            logger.warning("Memory save failed", extra={"user_id": user_id, "error": str(e)})
            return {"saved": False, "message": "Memory save unavailable — database may not be initialized yet."}

    return {"saved": True, "memory_id": str(memory_id), "kind": kind, "content": content}
