"""Vertex AI text embeddings via the Google Gen AI SDK (`google-genai`).

text-embedding-005 is a regional (GA) model — it does not require the global
endpoint. We therefore explicitly pin the client to `settings.gcp_region`
rather than reading whatever `GOOGLE_CLOUD_LOCATION` happens to be set to in
the process (which may be "global" to serve Gemini 3.1 preview models).

`google.genai` is lazy-imported so importing `live150.memory` does not drag
in the Vertex auth stack in test environments.
"""

import logging
from typing import TYPE_CHECKING

from live150.config import settings

if TYPE_CHECKING:
    from google.genai import Client

logger = logging.getLogger(__name__)


class Embedder:
    """Vertex AI text-embedding-005 client (768-dim by default)."""

    def __init__(self) -> None:
        self._client: Client | None = None
        self._model = settings.embedding_model

    def _ensure_client(self) -> "Client":
        if self._client is None:
            from google import genai

            self._client = genai.Client(
                vertexai=True,
                project=settings.gcp_project,
                location=settings.gcp_region,
            )
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Max 250 inputs per call (Vertex limit)."""
        if not texts:
            return []
        client = self._ensure_client()
        resp = await client.aio.models.embed_content(
            model=self._model,
            contents=texts,
        )
        return [e.values for e in resp.embeddings]
