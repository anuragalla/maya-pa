"""Pick the real or mock Live150 client based on settings."""

from live150.config import settings
from live150.live150_client.base import Live150Client
from live150.live150_client.client import Live150HttpClient
from live150.live150_client.mock_client import Live150MockClient


def get_client() -> Live150Client:
    """Return the configured Live150 dev-route client.

    `LIVE150_USE_MOCK=true` returns the in-memory mock; otherwise the real
    HTTP client is returned. In dev the caller uses the dev token to
    impersonate a user via `impersonate()`; in prod callers should skip
    `impersonate()` and reuse the bearer token already issued for the
    authenticated user (`settings.live150_bearer_token`).
    """
    if settings.live150_use_mock:
        return Live150MockClient(dev_token=settings.live150_dev_token or None)
    return Live150HttpClient()
