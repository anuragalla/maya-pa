"""Web search tool using DuckDuckGo (no API key required)."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def web_search(query: str, max_results: int = 5, tool_context: Any = None) -> dict:
    """Search the web for health-related information.

    Returns titles, URLs, and snippets for each result.
    Use this to find current real-world information: restaurants, gyms,
    nutrition facts, wellness centers, medical topics.

    Args:
        query: The search query string.
        max_results: Number of results to return (default 5, max 10).
    """
    try:
        from duckduckgo_search import DDGS

        max_results = min(max_results, 10)
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })

        logger.info("web_search", extra={"query": query, "result_count": len(results)})
        return {"query": query, "results": results}

    except Exception as e:
        logger.warning("web_search failed", extra={"query": query, "error": str(e)})
        return {"query": query, "results": [], "error": str(e)}
