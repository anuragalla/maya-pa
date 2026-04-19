"""CalendarProviderRegistry — resolves user_id → active CalendarProvider.

Reads oauth_token + user_calendar, decrypts credentials, and builds the
correct provider client. When Microsoft is added, this is the only file
that needs a new import.
"""

import logging

from google.oauth2.credentials import Credentials as GoogleCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from live150.calendar.provider import CalendarProvider, ProviderAuthError
from live150.calendar.providers.google import GoogleCalendarClient
from live150.crypto.vault import EncryptedBlob, Vault
from live150.db.models.oauth_token import OAuthToken
from live150.db.models.user_calendar import UserCalendar
from live150.oauth.flow import refresh_access_token

logger = logging.getLogger(__name__)


class CalendarProviderRegistry:
    """Given a user_id, returns the right CalendarProvider implementation."""

    def __init__(self, vault: Vault) -> None:
        self._vault = vault

    async def get_active_provider(
        self, user_id: str, db: AsyncSession
    ) -> CalendarProvider:
        """Return the provider for the user's preferred calendar connection."""
        stmt = select(UserCalendar).where(
            UserCalendar.user_id == user_id,
            UserCalendar.preferred == True,  # noqa: E712
        )
        uc = (await db.execute(stmt)).scalar_one_or_none()
        if uc is None:
            raise ValueError(f"No calendar provider connected for user={user_id}")
        return await self.get_provider(user_id, uc.provider, db)

    async def get_provider(
        self, user_id: str, provider_name: str, db: AsyncSession
    ) -> CalendarProvider:
        """Build the CalendarProvider for a specific provider."""
        if provider_name == "google":
            return await self._build_google(user_id, db)
        raise ValueError(f"Unsupported calendar provider: {provider_name}")

    async def list_connected_providers(
        self, user_id: str, db: AsyncSession
    ) -> list[str]:
        """Return provider names with active calendar connections."""
        stmt = select(UserCalendar.provider).where(UserCalendar.user_id == user_id)
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)

    async def _build_google(
        self, user_id: str, db: AsyncSession
    ) -> GoogleCalendarClient:
        """Decrypt Google OAuth token, refresh if needed, build client."""
        stmt = select(OAuthToken).where(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == "google",
        )
        token_row = (await db.execute(stmt)).scalar_one_or_none()
        if token_row is None:
            raise ProviderAuthError("No Google OAuth token for this user")

        aad = f"oauth:{user_id}:google".encode()

        # Decrypt access token
        from datetime import datetime, timedelta, timezone

        access_token: str
        if token_row.access_expires_at and token_row.access_expires_at > datetime.now(timezone.utc):
            blob = EncryptedBlob(
                ciphertext=token_row.access_token_ct,
                nonce=token_row.access_token_nonce,
                key_version=token_row.key_version,
            )
            access_token = self._vault.decrypt(blob, aad=aad).decode()
        else:
            # Refresh
            if not token_row.refresh_token_ct:
                raise ProviderAuthError("Access token expired and no refresh token")

            refresh_blob = EncryptedBlob(
                ciphertext=token_row.refresh_token_ct,
                nonce=token_row.refresh_token_nonce,
                key_version=token_row.key_version,
            )
            refresh_tok = self._vault.decrypt(refresh_blob, aad=aad).decode()
            token_data = await refresh_access_token("google", refresh_tok)

            # Re-encrypt
            new_blob = self._vault.encrypt(token_data["access_token"], aad=aad)
            token_row.access_token_ct = new_blob.ciphertext
            token_row.access_token_nonce = new_blob.nonce
            token_row.key_version = new_blob.key_version
            if "expires_in" in token_data:
                token_row.access_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=token_data["expires_in"]
                )
            if "refresh_token" in token_data:
                new_refresh = self._vault.encrypt(token_data["refresh_token"], aad=aad)
                token_row.refresh_token_ct = new_refresh.ciphertext
                token_row.refresh_token_nonce = new_refresh.nonce
            await db.commit()

            access_token = token_data["access_token"]

        creds = GoogleCredentials(token=access_token)
        return GoogleCalendarClient(creds)
