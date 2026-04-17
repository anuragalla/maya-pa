"""Real HTTP client for the Live150 dev-route handoff.

Mirrors the endpoints documented in the handoff one-for-one. Route 2 returns
a bare string, not JSON — handled specially. Routes 3/4 write to
`maya_chat_history` as a side effect; the client does not deduplicate, so
callers should avoid hitting them in tight loops.
"""

import httpx

from live150.config import settings
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
    """Async HTTP client against a running Live150 backend."""

    def __init__(
        self,
        base_url: str | None = None,
        dev_token: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = base_url or settings.api_base
        self._dev_token = dev_token or settings.live150_dev_token
        self._timeout = timeout if timeout is not None else settings.live150_http_timeout_seconds

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)

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

    async def impersonate(self, phone_number: str) -> ImpersonateResponse:
        if not self._dev_token:
            raise Live150Unauthorized("no dev token configured (LIVE150_DEV_TOKEN)")
        async with self._client() as c:
            r = await c.post(
                "/api/v1/login/developer/impersonate",
                json={"phoneNumber": phone_number},
                headers=self._auth(self._dev_token),
            )
            self._raise_for_status(r)
            return ImpersonateResponse.model_validate(r.json())

    async def get_holistic_analysis(self, access_token: str) -> HolisticAnalysis | None:
        async with self._client() as c:
            r = await c.get(
                "/api/v1/internal/holistic-analysis",
                headers=self._auth(access_token),
            )
            self._raise_for_status(r)
            payload = r.json()
            if payload is None:
                return None
            return HolisticAnalysis.model_validate(payload)

    async def get_progress_by_date(self, access_token: str, date_lookup: str) -> str:
        async with self._client() as c:
            r = await c.get(
                "/api/v1/maya/maya/progress-by-date",
                params={"date_lookup": date_lookup},
                headers=self._auth(access_token),
            )
            self._raise_for_status(r)
            # Route 2 is documented as returning a plaintext string, not JSON.
            # Some environments wrap it in JSON quotes — handle both.
            text = r.text
            if text.startswith('"') and text.endswith('"'):
                return r.json()
            return text

    async def get_my_health_goals(self, access_token: str) -> MayaWrappedResponse:
        async with self._client() as c:
            r = await c.get(
                "/api/v1/maya/maya/my-health-goals",
                headers=self._auth(access_token),
            )
            self._raise_for_status(r)
            return MayaWrappedResponse.model_validate(r.json())

    async def get_meal_plan(self, access_token: str) -> MayaWrappedResponse:
        async with self._client() as c:
            r = await c.get(
                "/api/v1/maya/maya/button/meal_plan",
                headers=self._auth(access_token),
            )
            self._raise_for_status(r)
            return MayaWrappedResponse.model_validate(r.json())

    async def get_initial_context(
        self,
        access_token: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> InitialContext:
        params: dict[str, float] = {}
        if latitude is not None and longitude is not None:
            params["latitude"] = latitude
            params["longitude"] = longitude
        async with self._client() as c:
            r = await c.get(
                "/api/v1/maya/maya/initial-context",
                params=params or None,
                headers=self._auth(access_token),
            )
            self._raise_for_status(r)
            return InitialContext.model_validate(r.json())
