"""Memory tools for the agent to save and search long-term memory."""


async def search_memory(query: str, limit: int = 5, tool_context=None) -> dict:
    """Search the user's long-term memory for relevant information.

    Use this to recall facts, preferences, and past events the user has shared.
    """
    # In production, this calls MemoryService.recall()
    # For now, returns placeholder
    return {
        "placeholder": True,
        "tool": "search_memory",
        "query": query,
        "limit": limit,
        "results": [],
        "message": "Memory search — will be wired to pgvector hybrid search",
    }


async def save_memory(kind: str, content: str, tool_context=None) -> dict:
    """Save a fact, preference, event, or note to the user's long-term memory.

    Args:
        kind: One of 'fact', 'preference', 'event', 'note'.
        content: The information to remember.
    """
    # In production, this calls MemoryService.save()
    return {
        "placeholder": True,
        "tool": "save_memory",
        "kind": kind,
        "content": content,
        "message": "Memory saved — will be wired to pgvector store",
    }
