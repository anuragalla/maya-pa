from unittest.mock import patch

from live150.agent.model_router import choose_model


@patch("live150.agent.model_router.settings")
def test_reminder_always_flash(mock_settings):
    mock_settings.default_model = "gemini-3-flash"
    mock_settings.lite_model = "gemini-3-1-flash-lite"

    result = choose_model("check sleep", {"turn_context": "reminder"})
    assert result == "gemini-3-flash"


@patch("live150.agent.model_router.settings")
def test_planning_verbs_use_flash(mock_settings):
    mock_settings.default_model = "gemini-3-flash"
    mock_settings.lite_model = "gemini-3-1-flash-lite"

    for msg in ["Can you analyze my sleep?", "Help me plan a workout", "Why am I tired?"]:
        result = choose_model(msg, {"turn_context": "interactive"})
        assert result == "gemini-3-flash", f"Failed for: {msg}"


@patch("live150.agent.model_router.settings")
def test_short_simple_message_uses_lite(mock_settings):
    mock_settings.default_model = "gemini-3-flash"
    mock_settings.lite_model = "gemini-3-1-flash-lite"

    result = choose_model("hi", {"turn_context": "interactive", "recent_tool_call_count": 0})
    assert result == "gemini-3-1-flash-lite"


@patch("live150.agent.model_router.settings")
def test_recent_tool_calls_use_flash(mock_settings):
    mock_settings.default_model = "gemini-3-flash"
    mock_settings.lite_model = "gemini-3-1-flash-lite"

    result = choose_model("ok", {"turn_context": "interactive", "recent_tool_call_count": 2})
    assert result == "gemini-3-flash"


@patch("live150.agent.model_router.settings")
def test_long_message_uses_flash(mock_settings):
    mock_settings.default_model = "gemini-3-flash"
    mock_settings.lite_model = "gemini-3-1-flash-lite"

    msg = "I've been having trouble sleeping for the past week and I want to understand what's going on with my patterns"
    result = choose_model(msg, {"turn_context": "interactive", "recent_tool_call_count": 0})
    assert result == "gemini-3-flash"
