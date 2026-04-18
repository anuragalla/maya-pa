"""Real HTTP client for the Live150 dev-route handoff.

Mirrors the endpoints documented in the handoff one-for-one. Route 2 returns
a bare string, not JSON — handled specially. Routes 3/4 write to
`maya_chat_history` as a side effect; the client does not deduplicate, so
callers should avoid hitting them in tight loops.
"""

import json

import httpx

from live150.live150_client.base import (
    Live150Conflict,
    Live150NotFound,
    Live150Unauthorized,
)
from live150.live150_client.schemas import (
    HolisticAnalysis,
    ImpersonateResponse,
    InitialContext,
    MayaWrappedResponse,
)


class Live150HttpClient:
    """Async HTTP client against a running Live150 backend.

    A single `httpx.AsyncClient` is held for the lifetime of the instance so
    connections are pooled across calls. Pass `http_client=` to inject a
    transport in tests (see `httpx.MockTransport`)."""

    def __init__(
        self,
        base_url: str | None = None,
        dev_token: str | None = None,
        timeout: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url or ""
        self._dev_token = dev_token or ""
        self._timeout = timeout or 30.0
        self._http = http_client or httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    @staticmethod
    def _auth(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _raise_for_status(r: httpx.Response) -> None:
        if r.status_code == 404:
            raise Live150NotFound(r.text)
        if r.status_code == 409:
            raise Live150Conflict(r.text)
        if r.status_code in (401, 403):
            raise Live150Unauthorized(r.text)
        r.raise_for_status()

    async def _get(
        self,
        path: str,
        access_token: str,
        params: dict[str, float | str] | None = None,
    ) -> httpx.Response:
        r = await self._http.get(path, params=params, headers=self._auth(access_token))
        self._raise_for_status(r)
        return r

    async def impersonate(self, phone_number: str) -> ImpersonateResponse:
        if not self._dev_token:
            raise Live150Unauthorized("no dev token configured (LIVE150_DEV_TOKEN)")
        r = await self._http.post(
            "/api/v1/login/developer/impersonate",
            json={"phoneNumber": phone_number},
            headers=self._auth(self._dev_token),
        )
        self._raise_for_status(r)
        return ImpersonateResponse.model_validate(r.json())

    async def get_holistic_analysis(self, access_token: str) -> HolisticAnalysis | None:
        r = await self._get("/api/v1/internal/holistic-analysis", access_token)
        payload = r.json()
        if payload is None:
            return None
        return HolisticAnalysis.model_validate(payload)

    async def get_progress_by_date(self, access_token: str, date_lookup: str) -> str:
        r = await self._get(
            "/api/v1/maya/maya/progress-by-date",
            access_token,
            params={"date_lookup": date_lookup},
        )
        # Route 2 returns plaintext; some environments wrap it in JSON quotes.
        text = r.text
        if text.startswith('"') and text.endswith('"'):
            return json.loads(text)
        return text

    async def get_my_health_goals(self, access_token: str) -> MayaWrappedResponse:
        r = await self._get("/api/v1/maya/maya/my-health-goals", access_token)
        return MayaWrappedResponse.model_validate(r.json())

    async def get_meal_plan(self, access_token: str) -> MayaWrappedResponse:
        r = await self._get("/api/v1/maya/maya/button/meal_plan", access_token)
        return MayaWrappedResponse.model_validate(r.json())

    async def get_initial_context(
        self,
        access_token: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> InitialContext:
        params: dict[str, float | str] | None = None
        if latitude is not None and longitude is not None:
            params = {"latitude": latitude, "longitude": longitude}
        r = await self._get("/api/v1/maya/maya/initial-context", access_token, params=params)
        return InitialContext.model_validate(r.json())
