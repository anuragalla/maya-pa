import pytest

from live150.voice.session import VoiceSession


def test_voice_session_init():
    session = VoiceSession(
        user_phone="+1234567890",
        access_token="test-token",
        api_base="http://localhost:8001",
    )
    assert session.user_phone == "+1234567890"
    assert session.access_token == "test-token"
    assert session.is_connected is False


def test_voice_session_state_default():
    session = VoiceSession(
        user_phone="+1234567890",
        access_token="test-token",
        api_base="http://localhost:8001",
    )
    assert session.state == "idle"
