"""Vertex AI text embeddings via the Google Gen AI SDK (`google-genai`).

text-embedding-005 is a regional (GA) model, so `get_genai_client` pins it to
`settings.gcp_region` rather than whatever `GOOGLE_CLOUD_LOCATION` the process
env happens to be set to (which may be "global" for Gemini 3.1 preview).
"""

import logging

from live150.agent.genai_client import get_genai_client
from live150.config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """Vertex AI text-embedding-005 client (768-dim by default)."""

    def __init__(self) -> None:
        self._model = settings.embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Max 250 inputs per call (Vertex limit)."""
        if not texts:
            return []
        client = get_genai_client(self._model)
        resp = await client.aio.models.embed_content(
            model=self._model,
            contents=texts,
        )
        return [e.values for e in resp.embeddings]
