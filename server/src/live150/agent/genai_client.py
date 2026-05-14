"""Shared, cached `google.genai` client.

Single cached client using API key auth.
Lazy-imports `google.genai` so tests don't need credentials.
"""

import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.genai import Client


@lru_cache(maxsize=1)
def get_genai_client() -> "Client":
    """Return a cached Gemini client using API key."""
    from google import genai

    return genai.Client(
        api_key=os.environ.get("LIVE150_GEMINI_API_KEY", ""),
    )
