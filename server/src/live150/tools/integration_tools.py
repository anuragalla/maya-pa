"""Integration tools — agent-driven connect flow.

Two tools that let the agent discover available integrations and
generate signed connect URLs for the user.
"""

import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from uuid6 import uuid7

from live150.config import settings
from live150.db.models.connect_state import ConnectState
from live150.db.models.oauth_token import OAuthToken
from live150.db.models.user_calendar import UserCalendar
from live150.db.session import async_session_factory
from live150.integrations.registry import get_integration, list_integrations

logger = logging.getLogger(__name__)

# Rate limit: 5 connect URLs per integration per hour per user
_connect_counts: dict[str, list[float]] = defaultdict(list)
_CONNECT_RATE_LIMIT = 5
_CONNECT_RATE_WINDOW = 3600  # 1 hour


def _check_rate_limit(user_id: str, integration_name: str) -> bool:
    """Returns True if the request is within rate limit."""
    key = f"{user_id}:{integration_name}"
    now = time.monotonic()

    # Prune old entries
    _connect_counts[key] = [t for t in _connect_counts[key] if now - t < _CONNECT_RATE_WINDOW]

    if len(_connect_counts[key]) >= _CONNECT_RATE_LIMIT:
        return False

    _connect_counts[key].append(now)
    return True


def _generate_state_token(user_id: str, provider: str) -> str:
    """Generate an HMAC-signed state token for the connect flow."""
    app_secret = (settings.master_key or "dev-secret").encode()
    nonce = secrets.token_urlsafe(32)
    payload = f"{user_id}:{provider}:{nonce}".encode()
    sig = hmac.new(app_secret, payload, hashlib.sha256).hexdigest()[:16]
    return f"{nonce}.{sig}"


def verify_state_token(state_token: str, user_id: str, provider: str) -> bool:
    """Verify the HMAC signature on a connect state token."""
    parts = state_token.rsplit(".", 1)
    if len(parts) != 2:
        return False
    nonce, sig = parts
    app_secret = (settings.master_key or "dev-secret").encode()
    payload = f"{user_id}:{provider}:{nonce}".encode()
    expected = hmac.new(app_secret, payload, hashlib.sha256).hexdigest()[:16]
    return hmac.compare_digest(sig, expected)


async def list_available_integrations(category: str | None = None, tool_context=None) -> list[dict]:
    """List integrations the user can connect.

    Returns available integrations with their connection status.

    Args:
        category: Optional filter by category (e.g., "calendar").
    """
    user_id = tool_context.state["user_id"]
    integrations = list_integrations(category)

    async with async_session_factory() as db:
        # Check which providers are connected
        stmt = select(OAuthToken.provider).where(OAuthToken.user_id == user_id)
        connected_providers = set((await db.execute(stmt)).scalars().all())

        # Check calendar-specific status
        stmt = select(UserCalendar).where(UserCalendar.user_id == user_id)
        uc_rows = {row.provider: row for row in (await db.execute(stmt)).scalars().all()}

    result = []
    for integration in integrations:
        connected = integration.provider in connected_providers
        needs_reconnect = False
        if connected and integration.provider in uc_rows:
            needs_reconnect = uc_rows[integration.provider].last_sync_status == "auth_failed"

        result.append({
            "name": integration.name,
            "display_name": integration.display_name,
            "category": integration.category,
            "connected": connected,
            "needs_reconnect": needs_reconnect,
            "description": integration.description,
        })

    return result


async def request_integration_connect(name: str, tool_context=None) -> dict:
    """Generate a signed connect URL for an integration.

    The URL is returned as a markdown-safe link that expires in 15 minutes.
    The agent should embed it in its response for the user to click.

    Args:
        name: Integration name (e.g., "google_calendar").
    """
    user_id = tool_context.state["user_id"]
    session_id = tool_context.state.get("session_id")

    integration = get_integration(name)
    if integration is None:
        return {"error": "unknown_integration"}
    if not integration.available:
        return {"error": "integration_unavailable"}

    if not _check_rate_limit(user_id, name):
        return {"error": "connect_rate_limited"}

    # Generate signed state token
    state_token = _generate_state_token(user_id, integration.provider)

    async with async_session_factory() as db:
        # Store connect_state row
        now = datetime.now(timezone.utc)
        cs = ConnectState(
            state_token=state_token,
            user_id=user_id,
            provider=integration.provider,
            scopes=integration.scopes_required,
            origin_session=session_id,
            expires_at=now + timedelta(minutes=15),
        )
        db.add(cs)
        await db.commit()

    # Build the OAuth authorize URL using the state token
    import os
    import urllib.parse

    from live150.oauth.providers import PROVIDERS

    provider = PROVIDERS[integration.provider]
    client_id = os.environ.get(provider.client_id_env, "")

    params = {
        "client_id": client_id,
        "redirect_uri": f"{settings.oauth_redirect_base}/oauth/{integration.provider}/callback",
        "response_type": "code",
        "scope": " ".join(integration.scopes_required + ["openid", "email"]),
        "state": state_token,
        **provider.extra_auth_params,
    }
    connect_url = f"{provider.auth_url}?{urllib.parse.urlencode(params)}"

    return {
        "integration": name,
        "display_name": integration.display_name,
        "connect_url": connect_url,
        "expires_in_seconds": 900,
        "description": integration.description,
    }
