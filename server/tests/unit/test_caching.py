import os
from unittest.mock import patch

from live150.agent import caching


def test_is_enabled_default_off():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LIVE150_USE_EXPLICIT_CACHE", None)
        assert caching.is_enabled() is False


def test_is_enabled_recognizes_truthy_values():
    for val in ("1", "true", "True", "YES", "yes"):
        with patch.dict(os.environ, {"LIVE150_USE_EXPLICIT_CACHE": val}):
            assert caching.is_enabled() is True, f"expected truthy for {val!r}"


def test_is_enabled_rejects_falsy_values():
    for val in ("0", "false", "", "no", "off"):
        with patch.dict(os.environ, {"LIVE150_USE_EXPLICIT_CACHE": val}):
            assert caching.is_enabled() is False, f"expected falsy for {val!r}"


def test_build_dynamic_context_full():
    state = {
        "user_local_time": "Monday, April 20 2026, 09:00 AM EDT",
        "user_timezone": "America/New_York",
        "user_profile_summary": "- Preferred name: Nigel\n- Age: 58",
    }
    out = caching.build_dynamic_context(state)
    assert "## Current context" in out
    assert "Monday, April 20 2026, 09:00 AM EDT" in out
    assert "America/New_York" in out
    assert "### User profile" in out
    assert "Nigel" in out


def test_build_dynamic_context_omits_profile_when_empty():
    state = {
        "user_local_time": "Monday 9am",
        "user_timezone": "UTC",
        "user_profile_summary": "",
    }
    out = caching.build_dynamic_context(state)
    assert "## Current context" in out
    assert "### User profile" not in out
