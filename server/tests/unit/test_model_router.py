from live150.agent.model_router import DEFAULT_MODEL, LITE_MODEL, choose_model


def test_reminder_always_flash():
    result = choose_model("check sleep", {"turn_context": "reminder"})
    assert result == DEFAULT_MODEL


def test_planning_verbs_use_flash():
    for msg in ["Can you analyze my sleep?", "Help me plan a workout", "Why am I tired?"]:
        result = choose_model(msg, {"turn_context": "interactive"})
        assert result == DEFAULT_MODEL, f"Failed for: {msg}"


def test_short_simple_message_uses_lite():
    result = choose_model("hi", {"turn_context": "interactive", "recent_tool_call_count": 0})
    assert result == LITE_MODEL


def test_recent_tool_calls_use_flash():
    result = choose_model("ok", {"turn_context": "interactive", "recent_tool_call_count": 2})
    assert result == DEFAULT_MODEL


def test_long_message_uses_flash():
    msg = "I've been having trouble sleeping for the past week and I want to understand what's going on with my patterns"
    result = choose_model(msg, {"turn_context": "interactive", "recent_tool_call_count": 0})
    assert result == DEFAULT_MODEL
