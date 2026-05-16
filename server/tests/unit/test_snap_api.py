"""Tests for the snap 2-pass food analysis endpoint.

Mocks the Gemini client so no real API calls are made.
"""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from live150.config import settings

SNAP_URL = "/api/v1/snap/analyze"

FAKE_JWT_SECRET = "test-secret"
FAKE_CLAIMS = {"sub": "user-123", "phone": "+19084329987"}


def _make_token(claims: dict = FAKE_CLAIMS) -> str:
    return jwt.encode(claims, FAKE_JWT_SECRET, algorithm="HS256")


def _make_image_base64() -> str:
    return base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 200).decode()


SURVEYOR_RESPONSE = {
    "items": [
        {
            "food_name": "Rice bowl",
            "estimated_volume": "1.5 cups",
            "is_anchor_item": True,
            "reasoning": "Bowl dimensions match ~375ml volume",
        },
        {
            "food_name": "Grilled chicken",
            "estimated_volume": "120 ml",
            "is_anchor_item": False,
            "reasoning": "Roughly 1/3 the volume of the anchor bowl",
        },
    ]
}

DIETITIAN_RESPONSE = {
    "meal_breakdown": [
        {
            "food_name": "Rice bowl",
            "estimated_grams": 290,
            "calories": 375,
            "macros": {"protein_g": 6.0, "carbs_g": 82.0, "fat_g": 0.6},
        },
        {
            "food_name": "Grilled chicken",
            "estimated_grams": 120,
            "calories": 198,
            "macros": {"protein_g": 37.0, "carbs_g": 0.0, "fat_g": 4.3},
        },
    ],
    "meal_totals": {
        "total_calories": 573,
        "total_protein_g": 43.0,
        "total_carbs_g": 82.0,
        "total_fat_g": 4.9,
    },
}


def _mock_genai_response(body: dict) -> MagicMock:
    resp = MagicMock()
    resp.text = json.dumps(body)
    return resp


@pytest.fixture(autouse=True)
def _patch_jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", FAKE_JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")


@pytest.fixture()
def _patch_gemini():
    """Patch the genai client so both Surveyor and Dietitian return canned responses."""
    mock_client = MagicMock()
    generate = AsyncMock(side_effect=[
        _mock_genai_response(SURVEYOR_RESPONSE),
        _mock_genai_response(DIETITIAN_RESPONSE),
    ])
    mock_client.aio.models.generate_content = generate

    with patch("live150.api.snap.get_genai_client", return_value=mock_client):
        yield generate


def _payload(image_b64: str | None = None) -> dict:
    return {
        "image_base64": image_b64 or _make_image_base64(),
        "metadata": {
            "sensor_type": "lidar",
            "camera_distance_cm": 45.0,
            "anchor_width_cm": 12.0,
            "anchor_length_cm": 10.0,
            "anchor_thickness_cm": 6.5,
            "anchor_shape_hint": "bowl-like",
            "depth_reliable": True,
        },
    }


@pytest.mark.anyio
async def test_analyze_happy_path(_patch_gemini):
    from live150.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            SNAP_URL,
            json=_payload(),
            headers={"Authorization": f"Bearer {_make_token()}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["meal_breakdown"]) == 2
    assert data["meal_totals"]["total_calories"] == 573
    assert data["meal_breakdown"][0]["macros"]["protein_g"] == 6.0

    assert _patch_gemini.call_count == 2


@pytest.mark.anyio
async def test_analyze_missing_auth():
    from live150.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(SNAP_URL, json=_payload())

    assert resp.status_code == 422  # missing Authorization header


@pytest.mark.anyio
async def test_analyze_invalid_token():
    from live150.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            SNAP_URL,
            json=_payload(),
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )

    assert resp.status_code == 401


@pytest.mark.anyio
async def test_analyze_invalid_base64():
    from live150.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _payload()
        payload["image_base64"] = "not-valid-base64!!!" * 10
        resp = await client.post(
            SNAP_URL,
            json=payload,
            headers={"Authorization": f"Bearer {_make_token()}"},
        )

    assert resp.status_code == 400
    assert "base64" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_analyze_surveyor_failure():
    """If the Surveyor Gemini call fails, return 502."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("Gemini API down")
    )

    with patch("live150.api.snap.get_genai_client", return_value=mock_client):
        from live150.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                SNAP_URL,
                json=_payload(),
                headers={"Authorization": f"Bearer {_make_token()}"},
            )

    assert resp.status_code == 502
    assert "Surveyor" in resp.json()["detail"]


@pytest.mark.anyio
async def test_analyze_dietitian_failure():
    """If the Surveyor succeeds but Dietitian fails, return 502."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=[
            _mock_genai_response(SURVEYOR_RESPONSE),
            RuntimeError("Gemini API down"),
        ]
    )

    with patch("live150.api.snap.get_genai_client", return_value=mock_client):
        from live150.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                SNAP_URL,
                json=_payload(),
                headers={"Authorization": f"Bearer {_make_token()}"},
            )

    assert resp.status_code == 502
    assert "Dietitian" in resp.json()["detail"]


@pytest.mark.anyio
async def test_analyze_sensor_type_validation():
    """sensor_type must be one of lidar/dual/rgb."""
    from live150.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _payload()
        payload["metadata"]["sensor_type"] = "infrared"
        resp = await client.post(
            SNAP_URL,
            json=payload,
            headers={"Authorization": f"Bearer {_make_token()}"},
        )

    assert resp.status_code == 422
