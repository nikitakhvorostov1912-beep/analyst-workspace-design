"""Тесты card-детектора (cards.py)."""

import pytest

from app.orchestrator.cards import build_card_from_tool_result


# --- execute_query → TableCard ---

def test_execute_query_direct_format():
    """execute_query с {columns, rows} напрямую → TableCard."""
    result = {
        "columns": [{"name": "Code", "type": "String"}, {"name": "Count", "type": "Number"}],
        "rows": [["A1", 5], ["A2", 3]],
    }
    card = build_card_from_tool_result("execute_query", {"query": "SELECT 1"}, result)
    assert card is not None
    assert card["type"] == "table"
    assert card["payload"]["total"] == 2
    assert card["payload"]["columns"][0]["name"] == "Code"
    assert card["payload"]["rows"][0] == ["A1", 5]
    assert card["payload"]["meta"]["query"] == "SELECT 1"


def test_execute_query_mcp_content_format():
    """execute_query в MCP content-формате → TableCard."""
    import json
    data = {"columns": [{"name": "Номер", "type": "String"}], "rows": [["ОПП-001"]]}
    result = {"content": [{"type": "text", "text": json.dumps(data)}]}
    card = build_card_from_tool_result("execute_query", {}, result)
    assert card is not None
    assert card["type"] == "table"
    assert card["payload"]["total"] == 1


def test_execute_query_empty_rows():
    """execute_query с пустым rows → TableCard с total=0."""
    result = {"columns": [], "rows": []}
    card = build_card_from_tool_result("execute_query", {}, result)
    assert card is not None
    assert card["payload"]["total"] == 0


# --- get_event_log → LogCard ---

def test_get_event_log_direct_format():
    """get_event_log с {entries} → LogCard."""
    result = {
        "entries": [
            {"time": "2026-05-13T10:00:00", "level": "Error", "user": "admin", "event": "_$Data$_.Update", "comment": "test"},
        ]
    }
    card = build_card_from_tool_result("get_event_log", {}, result)
    assert card is not None
    assert card["type"] == "log"
    assert len(card["payload"]["entries"]) == 1
    assert card["payload"]["entries"][0]["level"] == "Error"


def test_get_event_log_mcp_content_format():
    """get_event_log в MCP content-формате → LogCard."""
    import json
    data = {"entries": [{"time": "T", "level": "Info", "event": "Start"}]}
    result = {"content": [{"type": "text", "text": json.dumps(data)}]}
    card = build_card_from_tool_result("get_event_log", {}, result)
    assert card is not None
    assert card["type"] == "log"


def test_get_event_log_next_cursor():
    """get_event_log с next_cursor → LogCard.next_cursor."""
    result = {
        "entries": [{"time": "T", "level": "Warning", "event": "X"}],
        "next_cursor": "cursor_abc",
    }
    card = build_card_from_tool_result("get_event_log", {}, result)
    assert card["payload"]["next_cursor"] == "cursor_abc"


# --- get_object_by_link → ObjectCard ---

def test_get_object_by_link():
    """get_object_by_link → ObjectCard."""
    result = {
        "header": {"name": "Контрагент001", "type": "Справочник.Контрагенты", "path": "Catalogs.Counterparties"},
        "attributes": [{"name": "ИНН", "type": "String", "value": "7701234567"}],
        "tabular_sections": [],
        "forms": [],
        "templates": [],
    }
    card = build_card_from_tool_result("get_object_by_link", {}, result)
    assert card is not None
    assert card["type"] == "object"
    assert card["payload"]["header"]["name"] == "Контрагент001"


# --- get_metadata ---

def test_get_metadata_no_detail_returns_none():
    """get_metadata без detail → None (краткая сводка, карточка не нужна)."""
    result = {"summary": {"catalogs": 265}}
    card = build_card_from_tool_result("get_metadata", {}, result)
    assert card is None


def test_get_metadata_with_detail_true():
    """get_metadata с detail=True → ObjectCard."""
    result = {
        "header": {"name": "Справочник.Контрагенты", "type": "Catalog", "path": ""},
        "attributes": [],
        "tabular_sections": [],
        "forms": [],
        "templates": [],
    }
    card = build_card_from_tool_result("get_metadata", {"detail": True}, result)
    assert card is not None
    assert card["type"] == "object"


# --- Неизвестный tool ---

def test_unknown_tool_returns_none():
    """Неизвестный tool → None."""
    card = build_card_from_tool_result("unknown_tool", {}, {})
    assert card is None


# --- Malformed result ---

def test_malformed_result_returns_none():
    """Неразбираемый result → None (без исключения)."""
    card = build_card_from_tool_result("execute_query", {}, {"garbage": "data"})
    assert card is None


def test_non_json_mcp_content_returns_none():
    """MCP content с невалидным JSON → None."""
    result = {"content": [{"type": "text", "text": "not json {{{"}]}
    card = build_card_from_tool_result("execute_query", {}, result)
    assert card is None
