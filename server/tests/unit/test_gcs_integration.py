"""Unit tests for the GCS integration wrapper.

These tests mock google.cloud.storage.Client and never touch real GCS.
"""

from unittest.mock import patch

import pytest

from live150.integrations import gcs


@pytest.fixture(autouse=True)
def _clear_client_cache():
    gcs._client.cache_clear()
    yield
    gcs._client.cache_clear()


def test_bucket_name_matches_env():
    with patch.object(gcs.settings, "env", "dev"):
        assert gcs.bucket_name() == "live150-docs-dev"
    with patch.object(gcs.settings, "env", "prod"):
        assert gcs.bucket_name() == "live150-docs-prod"


def test_object_path_layout():
    assert (
        gcs.object_path("user-123", "doc-abc", "pdf")
        == "users/user-123/doc-abc.pdf"
    )
    # Leading-dot extension should be normalized.
    assert (
        gcs.object_path("user-123", "doc-abc", ".png")
        == "users/user-123/doc-abc.png"
    )


def test_parse_gs_uri_ok():
    assert gcs.parse_gs_uri("gs://my-bucket/users/u/d.pdf") == (
        "my-bucket",
        "users/u/d.pdf",
    )


@pytest.mark.parametrize(
    "bad",
    ["", "http://x/y", "gs://", "gs://only-bucket", "gs:///no-bucket/path"],
)
def test_parse_gs_uri_rejects_malformed(bad):
    with pytest.raises(ValueError):
        gcs.parse_gs_uri(bad)


def test_client_is_lazy_singleton():
    with patch("google.cloud.storage.Client") as mock_client_cls:
        gcs._client()
        gcs._client()
        assert mock_client_cls.call_count == 1
