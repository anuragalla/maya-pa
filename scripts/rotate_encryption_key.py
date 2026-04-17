"""Rotate the encryption key for OAuth tokens.

Usage: LIVE150_OLD_MASTER_KEY=base64:... LIVE150_MASTER_KEY=base64:... python -m scripts.rotate_encryption_key

Reads all rows with old key_version, decrypts with old key, re-encrypts
with new key, updates row. Idempotent.
"""

import asyncio
import os

from sqlalchemy import select

from live150.crypto.vault import EncryptedBlob, Vault
from live150.db.models.oauth_token import OAuthToken
from live150.db.session import async_session_factory


async def main():
    old_key_b64 = os.environ["LIVE150_OLD_MASTER_KEY"]
    new_key_b64 = os.environ["LIVE150_MASTER_KEY"]

    old_vault = Vault.from_env(old_key_b64, key_version=1)
    new_vault = Vault.from_env(new_key_b64, key_version=2)

    async with async_session_factory() as db:
        stmt = select(OAuthToken).where(OAuthToken.key_version < 2)
        result = await db.execute(stmt)
        rows = result.scalars().all()

        rotated = 0
        for row in rows:
            aad = f"oauth:{row.user_id}:{row.provider}".encode()

            # Re-encrypt access token
            old_access = EncryptedBlob(row.access_token_ct, row.access_token_nonce, row.key_version)
            plaintext_access = old_vault.decrypt(old_access, aad=aad)
            new_access = new_vault.encrypt(plaintext_access, aad=aad)
            row.access_token_ct = new_access.ciphertext
            row.access_token_nonce = new_access.nonce

            # Re-encrypt refresh token if present
            if row.refresh_token_ct:
                old_refresh = EncryptedBlob(row.refresh_token_ct, row.refresh_token_nonce, row.key_version)
                plaintext_refresh = old_vault.decrypt(old_refresh, aad=aad)
                new_refresh = new_vault.encrypt(plaintext_refresh, aad=aad)
                row.refresh_token_ct = new_refresh.ciphertext
                row.refresh_token_nonce = new_refresh.nonce

            row.key_version = 2
            rotated += 1

        await db.commit()
        print(f"Rotated {rotated} token(s)")


if __name__ == "__main__":
    asyncio.run(main())
