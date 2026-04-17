import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from live150.memory.embeddings import Embedder
from live150.memory.store import MemoryHit, MemoryStore

logger = logging.getLogger(__name__)

# Chunk limit: 400 tokens ~ 1600 chars (rough estimate)
MAX_CHUNK_CHARS = 1600


class MemoryService:
    """High-level memory API: wraps store + embedder, handles chunking."""

    def __init__(self):
        self.store = MemoryStore()
        self.embedder = Embedder()

    async def save(
        self,
        db: AsyncSession,
        user_id: str,
        kind: str,
        content: str,
        source: str = "agent",
        source_ref: str | None = None,
        metadata: dict | None = None,
    ) -> uuid.UUID:
        # Chunk if needed
        if len(content) > MAX_CHUNK_CHARS:
            chunks = [content[i : i + MAX_CHUNK_CHARS] for i in range(0, len(content), MAX_CHUNK_CHARS)]
        else:
            chunks = [content]

        embeddings = await self.embedder.embed(chunks)

        last_id = None
        for chunk, emb in zip(chunks, embeddings):
            last_id = await self.store.upsert(
                db=db,
                user_id=user_id,
                kind=kind,
                content=chunk,
                embedding=emb,
                source=source,
                source_ref=source_ref,
                metadata=metadata,
            )

        await db.commit()
        return last_id  # type: ignore[return-value]

    async def recall(
        self,
        db: AsyncSession,
        user_id: str,
        query: str,
        limit: int = 5,
        kinds: list[str] | None = None,
    ) -> list[MemoryHit]:
        embeddings = await self.embedder.embed([query])
        if not embeddings:
            return []

        return await self.store.search(
            db=db,
            user_id=user_id,
            query_embedding=embeddings[0],
            query_text=query,
            limit=limit,
            kinds=kinds,
        )
