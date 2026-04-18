import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass
class EncryptedBlob:
    ciphertext: bytes
    nonce: bytes
    key_version: int


class Vault:
    """AES-256-GCM envelope encryption vault.

    Master key is a 32-byte key. Each encryption generates a fresh 12-byte nonce.
    Optional AAD (additional authenticated data) binds ciphertext to context
    (e.g., user_id + provider) so moving a row across users fails decryption.
    """

    def __init__(self, master_key: bytes, key_version: int = 1):
        if len(master_key) != 32:
            raise ValueError("Master key must be exactly 32 bytes")
        self._aesgcm = AESGCM(master_key)
        self._key_version = key_version

    @classmethod
    def from_env(cls, master_key_b64: str, key_version: int = 1) -> "Vault":
        """Create from a base64-encoded master key (optionally prefixed with 'base64:')."""
        raw = master_key_b64.removeprefix("base64:")
        key_bytes = base64.b64decode(raw)
        return cls(key_bytes, key_version)

    def encrypt(self, plaintext: str | bytes, aad: bytes | None = None) -> EncryptedBlob:
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, aad)
        return EncryptedBlob(ciphertext=ciphertext, nonce=nonce, key_version=self._key_version)

    def decrypt(self, blob: EncryptedBlob, aad: bytes | None = None) -> bytes:
        return self._aesgcm.decrypt(blob.nonce, blob.ciphertext, aad)
