import logging
import os
import time
import urllib.parse
import uuid

import httpx
import jwt as pyjwt
from uuid6 import uuid7

from live150.config import settings
from live150.crypto.vault import EncryptedBlob, Vault
from live150.oauth.providers import PROVIDERS, OAuthProvider

logger = logging.getLogger(__name__)

# State token signing — uses a simple HMAC via PyJWT
_STATE_SECRET = os.environ.get("LIVE150_OAUTH_STATE_SECRET", settings.master_key[:16] if settings.master_key else "dev")


def generate_auth_url(user_id: str, provider_name: str) -> str:
    """Generate the OAuth authorization URL with a signed state token."""
    provider = PROVIDERS[provider_name]
    client_id = os.environ.get(provider.client_id_env, "")

    state = pyjwt.encode(
        {
            "sub": user_id,
            "provider": provider_name,
            "nonce": uuid.uuid4().hex,
            "exp": int(time.time()) + 600,  # 10 min
        },
        _STATE_SECRET,
        algorithm="HS256",
    )

    params = {
        "client_id": client_id,
        "redirect_uri": f"{settings.oauth_redirect_base}/oauth/{provider_name}/callback",
        "response_type": "code",
        "scope": " ".join(provider.scopes),
        "state": state,
        **provider.extra_auth_params,
    }

    return f"{provider.auth_url}?{urllib.parse.urlencode(params)}"


def verify_state(state: str) -> dict:
    """Verify and decode the OAuth state token."""
    return pyjwt.decode(state, _STATE_SECRET, algorithms=["HS256"])


async def exchange_code(
    provider_name: str,
    code: str,
) -> dict:
    """Exchange authorization code for tokens."""
    provider = PROVIDERS[provider_name]
    client_id = os.environ.get(provider.client_id_env, "")
    client_secret = os.environ.get(provider.client_secret_env, "")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            provider.token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{settings.oauth_redirect_base}/oauth/{provider_name}/callback",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(provider_name: str, refresh_token: str) -> dict:
    """Refresh an expired access token."""
    provider = PROVIDERS[provider_name]
    client_id = os.environ.get(provider.client_id_env, "")
    client_secret = os.environ.get(provider.client_secret_env, "")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            provider.token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def revoke_token(provider_name: str, token: str) -> None:
    """Revoke an OAuth token if the provider supports it."""
    provider = PROVIDERS[provider_name]
    if not provider.revoke_url:
        return

    async with httpx.AsyncClient() as client:
        await client.post(provider.revoke_url, data={"token": token})
