"""Shared, cached `google.genai` Vertex client.

All Gemini 3.1 models use the `global` endpoint. One cached client.
Lazy-imports `google.genai` so tests don't need GCP credentials.
"""

import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.genai import Client


@lru_cache(maxsize=1)
def get_genai_client() -> "Client":
    """Return a cached Vertex client using process env vars."""
    from google import genai

    return genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", "clawdbot-project-489814"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
    )
