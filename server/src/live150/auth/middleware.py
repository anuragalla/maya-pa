"""Auth middleware for dev: phone number → impersonate → access token.

The mobile app sends the user's phone number in X-Phone-Number header.
We use the dev token to impersonate that user via Live150's API and get
an access token for calling user-scoped routes.

In production this will be replaced with proper JWT verification.
"""

import logging

from fastapi import Header, HTTPException
from pydantic import BaseModel

from live150.config import settings
from live150.live150_client import get_client

logger = logging.getLogger(__name__)

# Cache impersonated tokens to avoid re-impersonating on every request.
# phone_number -> access_token
_token_cache: dict[str, str] = {}


class AuthedUser(BaseModel):
    user_id: str  # phone number for now
    access_token: str  # Live150 access token from impersonation


async def require_user(x_phone_number: str = Header(...)) -> AuthedUser:
    """FastAPI dependency: impersonate the user by phone number.

    Expects: X-Phone-Number: +19084329987
    Returns: AuthedUser with phone as user_id and a Live150 access token.
    """
    phone = x_phone_number.strip()
    if not phone or not phone.startswith("+"):
        raise HTTPException(status_code=400, detail="X-Phone-Number must be E.164 format (e.g. +19084329987)")

    # Return cached token if we have one
    if phone in _token_cache:
        return AuthedUser(user_id=phone, access_token=_token_cache[phone])

    if not settings.dev_token:
        raise HTTPException(status_code=500, detail="LIVE150_DEV_TOKEN not configured")

    client = get_client()
    try:
        resp = await client.impersonate(phone)
    except Exception as e:
        logger.error("Impersonation failed", extra={"phone": phone, "error": str(e)})
        raise HTTPException(status_code=401, detail=f"Could not impersonate user: {e}")

    _token_cache[phone] = resp.access_token
    return AuthedUser(user_id=phone, access_token=resp.access_token)
