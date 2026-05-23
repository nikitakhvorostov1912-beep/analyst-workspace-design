"""Unit-тесты для `_dispatch_sync_internal_tool` (P1.2 phase 2).

Helper обрабатывает memory_* и todo_* tools — pure dispatch без yield,
возвращает готовые структуры для main loop.

Использует мок MemoryManager и реальный TodoRegistry (через session_id).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.orchestrator.events import ToolResultEvent
from app.orchestrator.loop import _cap_content, _dispatch_sync_internal_tool


@pytest.fixture
def fake_memory_manager() -> MagicMock:
    """Mock MemoryManager — handle_tool_call возвращает success string."""
    mgr = MagicMock()
    mgr.handle_tool_call = MagicMock(return_value="appended 1 line")
    return mgr


class TestNonInternalTool:
    """Не-internal tools (MCP / clarify) → None, main loop пробует MCP path."""

    def test_returns_none_for_mcp_tool(self, fake_memory_manager: MagicMock) -> None:
        result = _dispatch_sync_internal_tool(
            tool_name="execute_query",
            tool_args={"query": "ВЫБРАТЬ * ИЗ Документы"},
            tool_id="call_1",
            memory_manager=fake_memory_manager,
            session_id="s1",
            start_ts=0.0,
        )
        assert result is None

    def test_returns_none_for_clarify(self, fake_memory_manager: MagicMock) -> None:
        result = _dispatch_sync_internal_tool(
            tool_name="clarify_question",
            tool_args={},
            tool_id="call_1",
            memory_manager=fake_memory_manager,
            session_id="s1",
            start_ts=0.0,
        )
        assert result is None

    def test_returns_none_for_get_metadata(self, fake_memory_manager: MagicMock) -> None:
        result = _dispatch_sync_internal_tool(
            tool_name="get_metadata",
            tool_args={"meta_type": "Документ"},
            tool_id="x",
            memory_manager=fake_memory_manager,
            session_id="s",
            start_ts=0.0,
        )
        assert result is None


class TestMemoryTools:
    """memory_append / memory_remove → MemoryManager.handle_tool_call."""

    def test_memory_append_success(self, fake_memory_manager: MagicMock) -> None:
        result = _dispatch_sync_internal_tool(
            tool_name="memory_append",
            tool_args={"namespace": "agent", "content": "Тест"},
            tool_id="call_1",
            memory_manager=fake_memory_manager,
            session_id="s1",
            start_ts=0.0,
        )
        assert result is not None
        ok, event, accum, msg = result
        assert ok is True
        fake_memory_manager.handle_tool_call.assert_called_once_with(
            "memory_append", {"namespace": "agent", "content": "Тест"}
        )

    def test_memory_event_is_tool_result(self, fake_memory_manager: MagicMock) -> None:
        result = _dispatch_sync_internal_tool(
            tool_name="memory_append",
            tool_args={},
            tool_id="call_x",
            memory_manager=fake_memory_manager,
            session_id="s1",
            start_ts=0.0,
        )
        assert result is not None
        _, event, _, _ = result
        assert isinstance(event, ToolResultEvent)
        assert event.id == "call_x"
        assert event.ok is True
        assert event.error is None

    def test_memory_accumulated_entry_has_all_fields(
        self, fake_memory_manager: MagicMock
    ) -> None:
        result = _dispatch_sync_internal_tool(
            tool_name="memory_append",
            tool_args={"namespace": "agent", "content": "X"},
            tool_id="call_42",
            memory_manager=fake_memory_manager,
            session_id="s1",
            start_ts=0.0,
        )
        assert result is not None
        _, _, accum, _ = result
        assert accum["id"] == "call_42"
        assert accum["name"] == "memory_append"
        assert accum["args"] == {"namespace": "agent", "content": "X"}
        assert accum["error"] is None
        assert accum["duration_ms"] >= 0

    def test_memory_message_entry_is_tool_role(
        self, fake_memory_manager: MagicMock
    ) -> None:
        result = _dispatch_sync_internal_tool(
            tool_name="memory_append",
            tool_args={},
            tool_id="call_x",
            memory_manager=fake_memory_manager,
            session_id="s1",
            start_ts=0.0,
        )
        assert result is not None
        _, _, _, msg = result
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "call_x"
        # content — JSON dump tool_result
        parsed = json.loads(msg["content"])
        assert parsed["status"] == "ok"

    def test_memory_disabled_manager_returns_failure(self) -> None:
        """manager=None → ok=False, error message в accum_entry и tool_content."""
        result = _dispatch_sync_internal_tool(
            tool_name="memory_append",
            tool_args={},
            tool_id="call_x",
            memory_manager=None,
            session_id="s1",
            start_ts=0.0,
        )
        assert result is not None
        ok, event, accum, msg = result
        assert ok is False
        assert event.ok is False
        assert event.error == "memory subsystem disabled"
        assert accum["error"] == "memory subsystem disabled"
        assert "disabled" in msg["content"]


class TestTodoTools:
    """todo_add / todo_list / todo_complete — обрабатываются через TodoRegistry."""

    def test_todo_list_empty_session(self, fake_memory_manager: MagicMock) -> None:
        """todo_list для свежей сессии возвращает пустой список."""
        result = _dispatch_sync_internal_tool(
            tool_name="todo_list",
            tool_args={},
            tool_id="call_1",
            memory_manager=fake_memory_manager,
            session_id="empty-session-todo-test",
            start_ts=0.0,
        )
        assert result is not None
        ok, event, accum, msg = result
        # todo_list always ok с пустым result для новой сессии
        assert ok is True
        assert event.ok is True
        # content в message — JSON tool_result
        parsed = json.loads(msg["content"])
        assert "tasks" in parsed or "items" in parsed or parsed == {} or isinstance(parsed, list)


class TestContentCapping:
    """_cap_content применяется к tool_content в message_entry."""

    def test_large_content_capped(self, fake_memory_manager: MagicMock) -> None:
        """Очень длинный tool_result обрезается до TOOL_CONTENT_CAP."""
        huge = "x" * 60_000
        fake_memory_manager.handle_tool_call = MagicMock(return_value=huge)
        result = _dispatch_sync_internal_tool(
            tool_name="memory_append",
            tool_args={},
            tool_id="call_x",
            memory_manager=fake_memory_manager,
            session_id="s1",
            start_ts=0.0,
        )
        assert result is not None
        _, _, _, msg = result
        # _cap_content cap'нет на TOOL_CONTENT_CAP=50_000 байт + маркер
        assert len(msg["content"]) <= 50_100
        assert "truncated" in msg["content"]

    def test_cap_helper_direct(self) -> None:
        """Sanity: _cap_content работает напрямую."""
        assert _cap_content("short") == "short"
        long_str = "a" * 60_000
        capped = _cap_content(long_str)
        assert len(capped) <= 50_100
        assert capped.endswith("...truncated")
