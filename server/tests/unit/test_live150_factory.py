"""Factory returns the HTTP client."""

from unittest.mock import patch

from live150.live150_client import Live150HttpClient, get_client


@patch("live150.live150_client.factory._client", None)
def test_factory_returns_http_client():
    client = get_client()
    assert isinstance(client, Live150HttpClient)
