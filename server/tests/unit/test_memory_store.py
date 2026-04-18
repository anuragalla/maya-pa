"""Unit tests for memory store.

Note: Full search tests require Postgres + pgvector (integration tests).
These unit tests cover the MemoryStore interface and basic logic.
"""

import uuid

import pytest

from live150.memory.store import MemoryHit, MemoryStore


def test_memory_hit_dataclass():
    hit = MemoryHit(
        memory_id=uuid.uuid4(),
        kind="fact",
        content="User prefers morning workouts",
        source="agent",
        score=0.95,
        metadata={"key": "value"},
    )
    assert hit.kind == "fact"
    assert hit.score == 0.95
    assert hit.metadata["key"] == "value"


def test_memory_store_instantiation():
    store = MemoryStore()
    assert store is not None
