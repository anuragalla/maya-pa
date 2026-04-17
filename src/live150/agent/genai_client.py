"""Shared, per-location cached `google.genai` Vertex client.

`genai.Client(vertexai=True, ...)` resolves ADC credentials and builds an HTTP
transport on construction, so rebuilding it on every reminder-parse or eval
judgement call is pure waste. Cache one client per Vertex location (regional
vs global) — this covers the only axis that actually changes at runtime.

Lazy-imports `google.genai` so importing this module (and anything that imports
it transitively) stays free of the Vertex auth stack in tests.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

from live150.agent.model_region import location_for_model
from live150.config import settings

if TYPE_CHECKING:
    from google.genai import Client


@lru_cache(maxsize=4)
def _client_for_location(location: str) -> "Client":
    from google import genai

    return genai.Client(
        vertexai=True,
        project=settings.gcp_project,
        location=location,
    )


def get_genai_client(model_id: str) -> "Client":
    """Return a cached Vertex client pinned to the correct location for this model."""
    return _client_for_location(location_for_model(model_id))
