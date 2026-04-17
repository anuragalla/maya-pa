import logging

import jwt as pyjwt
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from live150.auth.jwt import verify_token

logger = logging.getLogger(__name__)


class AuthedUser(BaseModel):
    user_id: str
    claims: dict


async def require_user(authorization: str = Header(...)) -> AuthedUser:
    """FastAPI dependency that extracts and verifies the Live150 JWT.

    Expects: Authorization: Bearer <token>
    Returns: AuthedUser with user_id from 'sub' claim.
    Raises: 401 on any auth failure.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        claims = verify_token(token)
    except pyjwt.exceptions.PyJWTError:
        logger.debug("JWT verification failed", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return AuthedUser(user_id=user_id, claims=claims)


async def get_api_token(x_live150_api_token: str = Header(...)) -> str:
    """Extract the per-request Live150 API bearer token."""
    if not x_live150_api_token:
        raise HTTPException(status_code=401, detail="Missing API token")
    return x_live150_api_token
