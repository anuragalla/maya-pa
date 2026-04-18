"""Live150 client factory."""

from live150.config import settings
from live150.live150_client.client import Live150HttpClient

_client: Live150HttpClient | None = None


def get_client() -> Live150HttpClient:
    """Return a cached Live150 HTTP client."""
    global _client
    if _client is None:
        _client = Live150HttpClient(
            base_url=settings.api_base,
            dev_token=settings.dev_token,
        )
    return _client
