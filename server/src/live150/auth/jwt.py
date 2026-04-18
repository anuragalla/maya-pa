import logging
import time
from dataclasses import dataclass, field

import httpx
import jwt
from jwt import PyJWKClient

from live150.config import settings

logger = logging.getLogger(__name__)


@dataclass
class JWKSCache:
    client: PyJWKClient | None = None
    _raw_keys: dict | None = field(default=None, repr=False)
    _cached_at: float = 0.0

    def get_client(self) -> PyJWKClient:
        now = time.monotonic()
        if self.client is None or (now - self._cached_at) > settings.jwt_jwks_cache_seconds:
            if settings.jwt_jwks_url:
                self.client = PyJWKClient(settings.jwt_jwks_url)
                self._cached_at = now
            else:
                raise ValueError("LIVE150_JWT_JWKS_URL is required when using JWKS")
        return self.client


_jwks_cache = JWKSCache()


def _get_public_key(token: str):
    """Get the public key for verifying the JWT."""
    if settings.jwt_public_key_pem:
        return settings.jwt_public_key_pem

    if settings.jwt_jwks_url:
        client = _jwks_cache.get_client()
        signing_key = client.get_signing_key_from_jwt(token)
        return signing_key.key

    raise ValueError("Either LIVE150_JWT_JWKS_URL or LIVE150_JWT_PUBLIC_KEY_PEM must be set")


def verify_token(token: str) -> dict:
    """Verify a Live150 JWT and return its claims.

    Raises jwt.exceptions.PyJWTError on any verification failure.
    """
    public_key = _get_public_key(token)

    claims = jwt.decode(
        token,
        public_key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iss": True,
            "verify_aud": True,
            "require": ["exp", "sub", "iss", "aud"],
        },
    )
    return claims
