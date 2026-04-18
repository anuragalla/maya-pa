import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from live150.config import settings
from live150.crypto.vault import EncryptedBlob, Vault
from live150.db.models.oauth_token import OAuthToken
from live150.oauth.flow import refresh_access_token

logger = logging.getLogger(__name__)


async def get_fresh_credentials(
    db: AsyncSession,
    vault: Vault,
    user_id: str,
    provider: str = "google",
) -> str:
    """Load, refresh if needed, and return a decrypted access token."""
    stmt = select(OAuthToken).where(
        OAuthToken.user_id == user_id,
        OAuthToken.provider == provider,
    )
    result = await db.execute(stmt)
    token_row = result.scalar_one_or_none()

    if token_row is None:
        raise ValueError(f"No OAuth token found for user={user_id} provider={provider}")

    aad = f"oauth:{user_id}:{provider}".encode()

    # Check if access token is still valid
    if token_row.access_expires_at and token_row.access_expires_at > datetime.now(timezone.utc):
        blob = EncryptedBlob(
            ciphertext=token_row.access_token_ct,
            nonce=token_row.access_token_nonce,
            key_version=token_row.key_version,
        )
        return vault.decrypt(blob, aad=aad).decode()

    # Need to refresh
    if not token_row.refresh_token_ct:
        raise ValueError("Access token expired and no refresh token available")

    refresh_blob = EncryptedBlob(
        ciphertext=token_row.refresh_token_ct,
        nonce=token_row.refresh_token_nonce,
        key_version=token_row.key_version,
    )
    refresh_token = vault.decrypt(refresh_blob, aad=aad).decode()

    token_data = await refresh_access_token(provider, refresh_token)

    # Re-encrypt new access token
    new_access_blob = vault.encrypt(token_data["access_token"], aad=aad)
    token_row.access_token_ct = new_access_blob.ciphertext
    token_row.access_token_nonce = new_access_blob.nonce
    token_row.key_version = new_access_blob.key_version

    if "expires_in" in token_data:
        from datetime import timedelta
        token_row.access_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])

    # If a new refresh token was issued, update it
    if "refresh_token" in token_data:
        new_refresh_blob = vault.encrypt(token_data["refresh_token"], aad=aad)
        token_row.refresh_token_ct = new_refresh_blob.ciphertext
        token_row.refresh_token_nonce = new_refresh_blob.nonce

    await db.commit()

    return token_data["access_token"]
