"""Factory selects mock vs real client based on settings."""

from unittest.mock import patch

from live150.live150_client import Live150HttpClient, Live150MockClient, get_client


@patch("live150.live150_client.factory.settings")
def test_factory_returns_mock_when_flag_set(mock_settings):
    mock_settings.live150_use_mock = True
    mock_settings.live150_dev_token = "whatever"
    assert isinstance(get_client(), Live150MockClient)


@patch("live150.live150_client.factory.settings")
def test_factory_returns_http_client_by_default(mock_settings):
    mock_settings.live150_use_mock = False
    assert isinstance(get_client(), Live150HttpClient)
