"""Backfill embeddings for memory entries that don't have them.

Usage: python -m scripts.backfill_embeddings
"""

import asyncio

from sqlalchemy import select

from live150.db.models.memory import MemoryEntry
from live150.db.session import async_session_factory
from live150.memory.embeddings import Embedder


async def main():
    embedder = Embedder()

    async with async_session_factory() as db:
        stmt = select(MemoryEntry).where(MemoryEntry.embedding.is_(None))
        result = await db.execute(stmt)
        entries = result.scalars().all()

        if not entries:
            print("No entries need embeddings")
            return

        print(f"Backfilling {len(entries)} entries...")

        # Batch in groups of 100
        for i in range(0, len(entries), 100):
            batch = entries[i : i + 100]
            texts = [e.content for e in batch]
            embeddings = await embedder.embed(texts)

            for entry, emb in zip(batch, embeddings):
                entry.embedding = emb

            await db.commit()
            print(f"  Processed {min(i + 100, len(entries))}/{len(entries)}")

        print("Done")


if __name__ == "__main__":
    asyncio.run(main())
