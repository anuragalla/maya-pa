import logging

from google.cloud import aiplatform
from google.cloud.aiplatform_v1.types import PredictRequest

from live150.config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """Vertex AI text-embedding-005 client (768-dim)."""

    def __init__(self):
        self._model_name = (
            f"projects/{settings.gcp_project}/locations/{settings.gcp_region}"
            f"/publishers/google/models/{settings.embedding_model}"
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Max 100 per call."""
        if not texts:
            return []

        # google-cloud-aiplatform doesn't have async embed natively;
        # use the sync API in a thread for now.
        import asyncio

        return await asyncio.to_thread(self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        from vertexai.language_models import TextEmbeddingModel

        model = TextEmbeddingModel.from_pretrained(settings.embedding_model)
        embeddings = model.get_embeddings(texts)
        return [e.values for e in embeddings]
