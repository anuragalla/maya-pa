"""Integration test for the /chat endpoint.

Requires running Postgres (via testcontainers).
Stubs Vertex AI with canned responses.
"""

import pytest

# TODO: Implement with testcontainers-python
# - Spin up Postgres with pgvector
# - Run Alembic migrations
# - Create test user
# - POST /chat with mocked Vertex responses
# - Verify SSE frames, audit_log rows, chat_message rows


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_chat_hello():
    """POST /chat with a hello message returns SSE stream."""
    pass


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_chat_creates_session():
    """POST /chat with null session_id creates a new session."""
    pass


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_chat_invalid_session():
    """POST /chat with non-existent session_id returns 404."""
    pass
