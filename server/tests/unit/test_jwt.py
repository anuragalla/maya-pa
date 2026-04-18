import time
from unittest.mock import patch

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from live150.auth.jwt import verify_token


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_key, pem


@pytest.fixture
def valid_claims():
    now = int(time.time())
    return {
        "sub": "user-123",
        "iss": "https://auth.live150.example",
        "aud": "live150-agent",
        "exp": now + 3600,
        "nbf": now - 10,
        "iat": now,
    }


def _make_token(private_key, claims):
    return pyjwt.encode(claims, private_key, algorithm="RS256")


@patch("live150.auth.jwt.settings")
def test_valid_token(mock_settings, rsa_keypair, valid_claims):
    private_key, pem = rsa_keypair
    mock_settings.jwt_public_key_pem = pem
    mock_settings.jwt_jwks_url = None
    mock_settings.jwt_algorithm = "RS256"
    mock_settings.jwt_issuer = "https://auth.live150.example"
    mock_settings.jwt_audience = "live150-agent"

    token = _make_token(private_key, valid_claims)
    result = verify_token(token)
    assert result["sub"] == "user-123"


@patch("live150.auth.jwt.settings")
def test_expired_token(mock_settings, rsa_keypair, valid_claims):
    private_key, pem = rsa_keypair
    mock_settings.jwt_public_key_pem = pem
    mock_settings.jwt_jwks_url = None
    mock_settings.jwt_algorithm = "RS256"
    mock_settings.jwt_issuer = "https://auth.live150.example"
    mock_settings.jwt_audience = "live150-agent"

    valid_claims["exp"] = int(time.time()) - 100
    token = _make_token(private_key, valid_claims)

    with pytest.raises(pyjwt.exceptions.ExpiredSignatureError):
        verify_token(token)


@patch("live150.auth.jwt.settings")
def test_wrong_audience(mock_settings, rsa_keypair, valid_claims):
    private_key, pem = rsa_keypair
    mock_settings.jwt_public_key_pem = pem
    mock_settings.jwt_jwks_url = None
    mock_settings.jwt_algorithm = "RS256"
    mock_settings.jwt_issuer = "https://auth.live150.example"
    mock_settings.jwt_audience = "live150-agent"

    valid_claims["aud"] = "wrong-audience"
    token = _make_token(private_key, valid_claims)

    with pytest.raises(pyjwt.exceptions.InvalidAudienceError):
        verify_token(token)


@patch("live150.auth.jwt.settings")
def test_invalid_signature(mock_settings, rsa_keypair, valid_claims):
    private_key, pem = rsa_keypair
    mock_settings.jwt_public_key_pem = pem
    mock_settings.jwt_jwks_url = None
    mock_settings.jwt_algorithm = "RS256"
    mock_settings.jwt_issuer = "https://auth.live150.example"
    mock_settings.jwt_audience = "live150-agent"

    # Sign with a different key
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _make_token(other_key, valid_claims)

    with pytest.raises(pyjwt.exceptions.InvalidSignatureError):
        verify_token(token)


@patch("live150.auth.jwt.settings")
def test_wrong_issuer(mock_settings, rsa_keypair, valid_claims):
    private_key, pem = rsa_keypair
    mock_settings.jwt_public_key_pem = pem
    mock_settings.jwt_jwks_url = None
    mock_settings.jwt_algorithm = "RS256"
    mock_settings.jwt_issuer = "https://auth.live150.example"
    mock_settings.jwt_audience = "live150-agent"

    valid_claims["iss"] = "https://evil.example"
    token = _make_token(private_key, valid_claims)

    with pytest.raises(pyjwt.exceptions.InvalidIssuerError):
        verify_token(token)
