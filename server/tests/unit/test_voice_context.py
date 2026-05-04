import pytest

from live150.voice.context import build_system_prompt, build_user_context


def test_build_system_prompt_contains_soul():
    prompt = build_system_prompt()
    assert "Maya" in prompt
    assert "longevity companion" in prompt


def test_build_system_prompt_contains_voice_addendum():
    prompt = build_system_prompt()
    assert "1-3 sentences" in prompt
    assert "Never use markdown" in prompt


def test_build_user_context_basic():
    ctx = build_user_context(
        display_name="Alex",
        age=34,
        goals=["reduce_inflammation", "improve_sleep"],
        conditions=["pre_diabetes"],
        timezone_name="America/New_York",
        memories=["User prefers morning workouts", "User doesn't eat pork"],
    )
    assert "Alex" in ctx
    assert "34" in ctx
    assert "reduce_inflammation" in ctx
    assert "pre_diabetes" in ctx
    assert "America/New_York" in ctx
    assert "morning workouts" in ctx


def test_build_user_context_empty_memories():
    ctx = build_user_context(
        display_name="Sam",
        age=28,
        goals=[],
        conditions=[],
        timezone_name="UTC",
        memories=[],
    )
    assert "Sam" in ctx
    assert "No prior context" in ctx
