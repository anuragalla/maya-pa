import pytest

from live150.voice.tools import TOOL_DECLARATIONS, TOOL_HANDLERS, get_tool_config


def test_tool_declarations_count():
    assert len(TOOL_DECLARATIONS) == 8


def test_each_declaration_has_required_fields():
    for decl in TOOL_DECLARATIONS:
        assert "name" in decl, f"Missing 'name' in declaration"
        assert "description" in decl, f"Missing 'description' in {decl.get('name')}"
        assert "parameters" in decl, f"Missing 'parameters' in {decl.get('name')}"


def test_handler_exists_for_each_declaration():
    for decl in TOOL_DECLARATIONS:
        name = decl["name"]
        assert name in TOOL_HANDLERS, f"No handler for tool '{name}'"


def test_get_tool_config_format():
    config = get_tool_config()
    assert isinstance(config, list)
    assert len(config) == 1
    assert "function_declarations" in config[0]
    assert len(config[0]["function_declarations"]) == 8


def test_tool_names():
    names = {d["name"] for d in TOOL_DECLARATIONS}
    expected = {
        "search_memory", "save_memory", "log_nams",
        "get_progress_by_date", "get_health_goals",
        "create_reminder", "list_reminders", "cancel_reminder",
    }
    assert names == expected
