"""Tests for the real Live150 HTTP client.

Verifies that each method hits the documented path, sends the documented
Authorization header, and maps 404/409/401 onto typed exceptions. Uses
`httpx.MockTransport` so no real network calls are made.
"""

import httpx
import pytest

from live150.live150_client import Live150HttpClient
from live150.live150_client.base import Live150Conflict, Live150NotFound, Live150Unauthorized


def _make_client(handler) -> Live150HttpClient:
    http = httpx.AsyncClient(base_url="https://api.test", transport=httpx.MockTransport(handler))
    return Live150HttpClient(base_url="https://api.test", dev_token="dev-abc", http_client=http)


@pytest.mark.asyncio
async def test_impersonate_posts_dev_token_and_phone():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = request.content
        return httpx.Response(200, json={"accessToken": "user-jwt", "tokenType": "bearer"})

    client = _make_client(handler)
    resp = await client.impersonate("+19084329987")

    assert resp.access_token == "user-jwt"
    assert seen["method"] == "POST"
    assert seen["path"] == "/api/v1/login/developer/impersonate"
    assert seen["auth"] == "Bearer dev-abc"
    assert b"+19084329987" in seen["body"]


@pytest.mark.asyncio
async def test_impersonate_404_raises_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="no such user")

    client = _make_client(handler)
    with pytest.raises(Live150NotFound):
        await client.impersonate("+10000000000")


@pytest.mark.asyncio
async def test_impersonate_409_raises_conflict():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, text="no active refresh token")

    client = _make_client(handler)
    with pytest.raises(Live150Conflict):
        await client.impersonate("+19084329987")


@pytest.mark.asyncio
async def test_impersonate_without_dev_token_raises_unauthorized():
    client = Live150HttpClient(base_url="https://api.test", dev_token="")
    with pytest.raises(Live150Unauthorized):
        await client.impersonate("+19084329987")


@pytest.mark.asyncio
async def test_get_holistic_analysis_returns_none_for_null_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/internal/holistic-analysis"
        assert request.headers["Authorization"] == "Bearer user-jwt"
        return httpx.Response(
            200,
            text="null",
            headers={"Content-Type": "application/json"},
        )

    client = _make_client(handler)
    assert await client.get_holistic_analysis("user-jwt") is None


@pytest.mark.asyncio
async def test_get_progress_by_date_sends_query_and_returns_text():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/maya/maya/progress-by-date"
        assert request.url.params["date_lookup"] == "2026-04-17"
        return httpx.Response(200, text="**Nutrition**:\n- Breakfast: eggs")

    client = _make_client(handler)
    result = await client.get_progress_by_date("user-jwt", "2026-04-17")
    assert result.startswith("**Nutrition**")


@pytest.mark.asyncio
async def test_get_progress_by_date_handles_json_wrapped_string():
    """Some environments return the plaintext wrapped in JSON quotes."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='"wrapped string"',
            headers={"Content-Type": "application/json"},
        )

    client = _make_client(handler)
    result = await client.get_progress_by_date("user-jwt", "2026-04-17")
    assert result == "wrapped string"


@pytest.mark.asyncio
async def test_get_initial_context_omits_coords_when_either_missing():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"time_offset": 0, "user_data": {}})

    client = _make_client(handler)
    await client.get_initial_context("user-jwt", latitude=1.0, longitude=None)
    assert "latitude" not in seen["params"]
    assert "longitude" not in seen["params"]


@pytest.mark.asyncio
async def test_get_initial_context_sends_both_coords():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"time_offset": 0, "user_data": {}})

    client = _make_client(handler)
    await client.get_initial_context("user-jwt", latitude=40.7, longitude=-74.0)
    assert seen["params"]["latitude"] == "40.7"
    assert seen["params"]["longitude"] == "-74.0"
