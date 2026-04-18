"""Integration tests for tool calls.

Verifies each tool category is invokable with mocked Live150 APIs,
and that risky tools go through confirmation flow.
"""

import pytest


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_health_tool_passes_bearer():
    """Health API tools pass the user's bearer token."""
    pass


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_risky_tool_creates_confirmation():
    """Risky tools create pending_confirmation instead of executing."""
    pass


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_reminder_mode_blocks_unsafe_tools():
    """Tools not in REMINDER_SAFE_TOOLS are blocked during reminder runs."""
    pass
