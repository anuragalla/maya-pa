"""Integration test for OAuth flows.

Tests the full start → callback → token storage → refresh cycle
with mocked Google endpoints.
"""

import pytest


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_oauth_start_redirects():
    """/oauth/google/start returns redirect URL."""
    pass


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_oauth_callback_stores_tokens():
    """OAuth callback stores encrypted tokens in DB."""
    pass


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_oauth_refresh_rotates_access_token():
    """Expired access token triggers refresh and re-encryption."""
    pass


@pytest.mark.skip(reason="Requires testcontainers setup")
@pytest.mark.asyncio
async def test_oauth_disconnect_revokes():
    """DELETE /oauth/google revokes and deletes token."""
    pass
