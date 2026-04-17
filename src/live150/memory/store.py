import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from live150.db.models.memory import MemoryEntry

logger = logging.getLogger(__name__)


@dataclass
class MemoryHit:
    memory_id: uuid.UUID
    kind: str
    content: str
    source: str | None
    score: float
    metadata: dict


class MemoryStore:
    """pgvector + BM25 hybrid search store."""

    async def upsert(
        self,
        db: AsyncSession,
        user_id: str,
        kind: str,
        content: str,
        embedding: list[float] | None = None,
        source: str = "agent",
        source_ref: str | None = None,
        metadata: dict | None = None,
        expires_at=None,
    ) -> uuid.UUID:
        entry = MemoryEntry(
            memory_id=uuid7(),
            user_id=user_id,
            kind=kind,
            content=content,
            source=source,
            source_ref=source_ref,
            embedding=embedding,
            metadata_=metadata or {},
            expires_at=expires_at,
        )
        db.add(entry)
        await db.flush()
        return entry.memory_id

    async def search(
        self,
        db: AsyncSession,
        user_id: str,
        query_embedding: list[float],
        query_text: str,
        limit: int = 5,
        kinds: list[str] | None = None,
    ) -> list[MemoryHit]:
        # Build tsquery from words
        words = [w.strip() for w in query_text.split() if w.strip()]
        tsquery = " & ".join(words) if words else ""

        sql = text("""
            WITH q AS (
                SELECT :query_embedding::vector AS v,
                       to_tsquery('english', :tsquery) AS t
            ),
            scored AS (
                SELECT m.memory_id, m.kind, m.content, m.source, m.metadata,
                       1 - (m.embedding <=> q.v) AS vec_score,
                       ts_rank(to_tsvector('english', m.content), q.t) AS text_score
                FROM memory_entry m, q
                WHERE m.user_id = :user_id
                  AND (:kinds_filter = false OR m.kind = ANY(:kinds))
                  AND (m.expires_at IS NULL OR m.expires_at > now())
            )
            SELECT *, (0.7 * vec_score + 0.3 * text_score) AS score
            FROM scored
            ORDER BY score DESC
            LIMIT :limit
        """)

        result = await db.execute(
            sql,
            {
                "query_embedding": str(query_embedding),
                "tsquery": tsquery,
                "user_id": user_id,
                "kinds_filter": kinds is not None,
                "kinds": kinds or [],
                "limit": limit,
            },
        )

        return [
            MemoryHit(
                memory_id=row.memory_id,
                kind=row.kind,
                content=row.content,
                source=row.source,
                score=row.score,
                metadata=row.metadata,
            )
            for row in result
        ]
