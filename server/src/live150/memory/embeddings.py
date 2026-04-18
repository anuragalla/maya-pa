"""Vertex AI text embeddings via google-genai SDK."""

import logging

from live150.agent.genai_client import get_genai_client

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-005"


class Embedder:
    """Vertex AI text-embedding-005 client (768-dim)."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = get_genai_client()
        resp = await client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
        )
        return [e.values for e in resp.embeddings]
