"""Abstract protocol shared by the real and mock Live150 dev-route clients."""

from typing import Protocol

from live150.live150_client.schemas import (
    HolisticAnalysis,
    ImpersonateResponse,
    InitialContext,
    MayaWrappedResponse,
)


class Live150Client(Protocol):
    """Contract for the five dev-facing GETs plus the impersonation exchange.

    Callers hold an access token for the target user and pass it into each
    route call. In dev the token comes from `impersonate()`; in prod it
    comes from `settings.live150_bearer_token` (already minted for the
    authenticated user by the main Live150 backend).
    """

    async def impersonate(self, phone_number: str) -> ImpersonateResponse:
        """Exchange the dev token for a user access token.

        Raises:
            Live150NotFound: 404 — no user with that phone number.
            Live150Conflict: 409 — user exists but has no active refresh token.
        """
        ...

    async def get_holistic_analysis(self, access_token: str) -> HolisticAnalysis | None:
        """Route 1. Returns None when no analysis has been generated today."""
        ...

    async def get_progress_by_date(self, access_token: str, date_lookup: str) -> str:
        """Route 2. `date_lookup` must be YYYY-MM-DD in the user's local timezone.
        Returns the pre-formatted plaintext summary as a bare string."""
        ...

    async def get_my_health_goals(self, access_token: str) -> MayaWrappedResponse:
        """Route 3. Side effect: inserts a row into `maya_chat_history`."""
        ...

    async def get_meal_plan(self, access_token: str) -> MayaWrappedResponse:
        """Route 4. Side effect: inserts a row into `maya_chat_history`."""
        ...

    async def get_initial_context(
        self,
        access_token: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> InitialContext:
        """Route 5. Both lat/long must be supplied together; otherwise the
        profile's stored location is used."""
        ...


class Live150Error(Exception):
    """Base error for dev-route client failures."""


class Live150NotFoundError(Live150Error):
    """404 — the requested resource (or user) does not exist."""


class Live150ConflictError(Live150Error):
    """409 — user exists but has no active refresh token yet."""


class Live150UnauthorizedError(Live150Error):
    """401/403 — token rejected."""


# Compatibility aliases so callers can write `except Live150NotFound` naturally.
Live150NotFound = Live150NotFoundError
Live150Conflict = Live150ConflictError
Live150Unauthorized = Live150UnauthorizedError
