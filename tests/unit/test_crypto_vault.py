import os

import pytest

from live150.crypto.vault import EncryptedBlob, Vault


@pytest.fixture
def vault():
    key = os.urandom(32)
    return Vault(key, key_version=1)


def test_encrypt_decrypt_roundtrip(vault):
    plaintext = "sensitive health data"
    blob = vault.encrypt(plaintext)
    result = vault.decrypt(blob)
    assert result == plaintext.encode("utf-8")


def test_encrypt_decrypt_bytes(vault):
    plaintext = b"\x00\x01\x02\xff"
    blob = vault.encrypt(plaintext)
    result = vault.decrypt(blob)
    assert result == plaintext


def test_aad_binding(vault):
    plaintext = "my-refresh-token"
    aad_user1 = b"oauth:user1:google"
    aad_user2 = b"oauth:user2:google"

    blob = vault.encrypt(plaintext, aad=aad_user1)

    # Correct AAD works
    result = vault.decrypt(blob, aad=aad_user1)
    assert result == plaintext.encode("utf-8")

    # Wrong AAD fails
    with pytest.raises(Exception):  # InvalidTag from cryptography
        vault.decrypt(blob, aad=aad_user2)


def test_aad_missing_when_expected(vault):
    plaintext = "secret"
    blob = vault.encrypt(plaintext, aad=b"context")

    with pytest.raises(Exception):
        vault.decrypt(blob, aad=None)


def test_unique_nonces(vault):
    blobs = [vault.encrypt("same") for _ in range(100)]
    nonces = {b.nonce for b in blobs}
    assert len(nonces) == 100


def test_key_version_tracked():
    key = os.urandom(32)
    v1 = Vault(key, key_version=1)
    v2 = Vault(key, key_version=2)

    blob1 = v1.encrypt("data")
    blob2 = v2.encrypt("data")

    assert blob1.key_version == 1
    assert blob2.key_version == 2


def test_key_rotation():
    old_key = os.urandom(32)
    new_key = os.urandom(32)

    old_vault = Vault(old_key, key_version=1)
    new_vault = Vault(new_key, key_version=2)

    blob = old_vault.encrypt("secret")

    # Old vault can decrypt
    assert old_vault.decrypt(blob) == b"secret"

    # New vault cannot decrypt old ciphertext
    with pytest.raises(Exception):
        new_vault.decrypt(blob)

    # Re-encrypt with new key
    plaintext = old_vault.decrypt(blob)
    new_blob = new_vault.encrypt(plaintext)
    assert new_vault.decrypt(new_blob) == b"secret"
    assert new_blob.key_version == 2


def test_invalid_key_length():
    with pytest.raises(ValueError, match="32 bytes"):
        Vault(b"short")


def test_from_env():
    import base64
    key = os.urandom(32)
    b64 = base64.b64encode(key).decode()

    vault = Vault.from_env(f"base64:{b64}", key_version=1)
    blob = vault.encrypt("test")
    assert vault.decrypt(blob) == b"test"

    # Without prefix
    vault2 = Vault.from_env(b64, key_version=1)
    blob2 = vault2.encrypt("test")
    assert vault2.decrypt(blob2) == b"test"
