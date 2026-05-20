"""Tests for TodoTool (Sprint 3 — Hermes D3)."""

from __future__ import annotations

import pytest

from app.orchestrator.todo import (
    MAX_TODOS_PER_SESSION,
    TODOS,
    dispatch_todo_tool,
    is_todo_tool,
    render_todos_for_prompt,
)


@pytest.fixture(autouse=True)
def clear_todos():
    TODOS._items.clear()  # noqa: SLF001
    yield
    TODOS._items.clear()  # noqa: SLF001


def test_is_todo_tool() -> None:
    assert is_todo_tool("todo_add") is True
    assert is_todo_tool("todo_complete") is True
    assert is_todo_tool("todo_list") is True
    assert is_todo_tool("memory_append") is False
    assert is_todo_tool("execute_query") is False


def test_add_creates_items() -> None:
    items = TODOS.add("sess-1", ["Купить хлеб", "Помыть посуду"])
    assert len(items) == 2
    assert all(i.status == "pending" for i in items)


def test_add_filters_empty_strings() -> None:
    items = TODOS.add("sess-1", ["", "  ", "ok"])
    assert len(items) == 1
    assert items[0].text == "ok"


def test_add_respects_limit() -> None:
    big = [f"t{i}" for i in range(MAX_TODOS_PER_SESSION + 10)]
    added = TODOS.add("sess-1", big)
    assert len(added) == MAX_TODOS_PER_SESSION


def test_complete_changes_status() -> None:
    items = TODOS.add("sess-1", ["task1", "task2"])
    completed = TODOS.complete("sess-1", [items[0].id])
    assert completed == [items[0].id]
    assert TODOS.list("sess-1")[0].status == "completed"
    assert TODOS.list("sess-1")[0].completed_at is not None


def test_session_isolation() -> None:
    TODOS.add("sess-a", ["t1"])
    TODOS.add("sess-b", ["t2"])
    assert len(TODOS.list("sess-a")) == 1
    assert len(TODOS.list("sess-b")) == 1
    assert TODOS.list("sess-a")[0].text == "t1"


def test_clear() -> None:
    TODOS.add("sess-1", ["t1", "t2"])
    cleared = TODOS.clear("sess-1")
    assert cleared == 2
    assert TODOS.list("sess-1") == []


def test_active_count() -> None:
    items = TODOS.add("sess-1", ["a", "b", "c"])
    TODOS.complete("sess-1", [items[0].id])
    # Один completed, два pending — active_count = 2
    assert TODOS.active_count("sess-1") == 2


def test_dispatch_todo_add() -> None:
    ok, result, err = dispatch_todo_tool("sess-1", "todo_add", {"items": ["t1", "t2"]})
    assert ok is True
    assert err is None
    assert len(result["added"]) == 2


def test_dispatch_todo_add_invalid_items() -> None:
    ok, _, err = dispatch_todo_tool("sess-1", "todo_add", {"items": "not a list"})
    assert ok is False
    assert err is not None


def test_dispatch_todo_complete() -> None:
    items = TODOS.add("sess-1", ["t1"])
    ok, result, err = dispatch_todo_tool(
        "sess-1", "todo_complete", {"ids": [items[0].id]}
    )
    assert ok is True
    assert items[0].id in result["completed"]


def test_dispatch_todo_list() -> None:
    TODOS.add("sess-1", ["x"])
    ok, result, err = dispatch_todo_tool("sess-1", "todo_list", {})
    assert ok is True
    assert len(result["items"]) == 1


def test_dispatch_unknown_tool() -> None:
    ok, _, err = dispatch_todo_tool("sess-1", "todo_unknown", {})
    assert ok is False
    assert err is not None


def test_dispatch_empty_session_id() -> None:
    ok, _, err = dispatch_todo_tool("", "todo_add", {"items": ["x"]})
    assert ok is False


def test_render_for_prompt_empty() -> None:
    assert render_todos_for_prompt("sess-1") == ""


def test_render_for_prompt_with_items() -> None:
    TODOS.add("sess-1", ["Задача 1", "Задача 2"])
    block = render_todos_for_prompt("sess-1")
    assert "todo" in block.lower()
    assert "Задача 1" in block
    assert "[ ]" in block  # pending marker


def test_render_for_prompt_skips_when_all_completed() -> None:
    items = TODOS.add("sess-1", ["t1"])
    TODOS.complete("sess-1", [items[0].id])
    # Если активных нет — render возвращает ""
    assert render_todos_for_prompt("sess-1") == ""
