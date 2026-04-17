"""Tests for the model→Vertex-location resolver.

Gemini 3.1 preview models (and anything with `-preview` in the ID) must be
served on the global endpoint; everything else stays on the configured
regional endpoint.
"""

from unittest.mock import patch

from live150.agent.model_region import is_preview_model, location_for_model


def test_is_preview_model_flags_3_1_family():
    assert is_preview_model("gemini-3-1-flash-lite")
    assert is_preview_model("gemini-3-1-pro")
    assert is_preview_model("gemini-3-1-flash-image-preview")


def test_is_preview_model_flags_anything_with_preview_suffix():
    assert is_preview_model("gemini-3-flash-preview")
    assert is_preview_model("some-future-model-preview")


def test_is_preview_model_does_not_flag_3_ga_models():
    assert not is_preview_model("gemini-3-flash")
    assert not is_preview_model("gemini-3-pro")
    assert not is_preview_model("text-embedding-005")


@patch("live150.agent.model_region.settings")
def test_location_for_3_1_preview_is_global(mock_settings):
    mock_settings.gcp_region = "us-central1"
    mock_settings.gcp_preview_region = "global"
    assert location_for_model("gemini-3-1-flash-lite") == "global"


@patch("live150.agent.model_region.settings")
def test_location_for_ga_model_is_regional(mock_settings):
    mock_settings.gcp_region = "us-central1"
    mock_settings.gcp_preview_region = "global"
    assert location_for_model("gemini-3-flash") == "us-central1"
    assert location_for_model("text-embedding-005") == "us-central1"
