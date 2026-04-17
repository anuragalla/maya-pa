"""Resolve the correct Vertex AI location for a given Gemini model ID.

Gemini 3.1 preview models (and any `*-preview` model) are only served on the
`global` endpoint — regional endpoints like us-central1 return model-not-found.
Non-preview models stay on the configured regional endpoint (e.g. embeddings
use text-embedding-005 which is GA on regional).

Refs:
- https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations
- https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash
"""

from live150.config import settings


def is_preview_model(model_id: str) -> bool:
    """True for Gemini 3.1 preview models and anything with `-preview` in the ID."""
    return model_id.startswith("gemini-3-1-") or "-preview" in model_id


def location_for_model(model_id: str) -> str:
    """Return the Vertex AI location that serves this model."""
    if is_preview_model(model_id):
        return settings.gcp_preview_region
    return settings.gcp_region
