"""Tests for tool_result_storage (Sprint 5 — Hermes D7)."""

from __future__ import annotations

import json

from app.orchestrator.tool_result_storage import (
    PER_TOOL_BYTE_CAP,
    SUMMARY_KEEP_BYTES,
    ToolResultStorage,
)


def test_should_persist_below_cap(tmp_path) -> None:
    storage = ToolResultStorage(tmp_path)
    assert storage.should_persist("short") is False


def test_should_persist_above_cap(tmp_path) -> None:
    storage = ToolResultStorage(tmp_path, per_tool_cap=100)
    assert storage.should_persist("x" * 200) is True


def test_persist_creates_file(tmp_path) -> None:
    storage = ToolResultStorage(tmp_path)
    stored = storage.persist(
        session_id="sess-1",
        tool_call_id="t1",
        content=json.dumps({"data": ["a", "b", "c"]}),
    )
    assert stored.file_path.exists()
    # File contains valid JSON wrapper
    loaded = json.loads(stored.file_path.read_text(encoding="utf-8"))
    assert loaded["kind"] == "json"
    assert loaded["tool_call_id"] == "t1"


def test_persist_text_content(tmp_path) -> None:
    storage = ToolResultStorage(tmp_path)
    stored = storage.persist(
        session_id="s1", tool_call_id="t1", content="plain text not json",
    )
    loaded = json.loads(stored.file_path.read_text(encoding="utf-8"))
    assert loaded["kind"] == "text"


def test_summary_contains_marker(tmp_path) -> None:
    storage = ToolResultStorage(tmp_path)
    content = "x" * 5_000
    stored = storage.persist(session_id="s", tool_call_id="t", content=content)
    summary = storage.make_summary(content, stored)
    assert "[tool_output_stored:" in summary
    # Контент усечён
    assert len(summary) < len(content)


def test_unsafe_session_id_sanitized(tmp_path) -> None:
    storage = ToolResultStorage(tmp_path)
    stored = storage.persist(
        session_id="../etc/passwd", tool_call_id="t1", content="x",
    )
    # File создан внутри tmp_path (sandbox)
    assert tmp_path in stored.file_path.parents
    # Sanitized session_id не содержит slash / path-traversal segments
    session_part = stored.file_path.parent.name
    assert "/" not in session_part
    assert "\\" not in session_part
    # Точки заменены на _ кроме точек в имени файла (расширение)
    # path components не равны ".." после sanitize
    for part in stored.file_path.relative_to(tmp_path).parts:
        assert part != ".."


def test_load_existing(tmp_path) -> None:
    storage = ToolResultStorage(tmp_path)
    storage.persist(session_id="s", tool_call_id="t1", content='{"x": 1}')
    loaded = storage.load("s", "t1")
    assert loaded is not None
    assert loaded["data"] == {"x": 1}


def test_load_missing(tmp_path) -> None:
    storage = ToolResultStorage(tmp_path)
    assert storage.load("s", "missing") is None


def test_per_turn_budget(tmp_path) -> None:
    storage = ToolResultStorage(tmp_path, per_turn_budget=1000)
    assert storage.remaining_budget() == 1000
    storage.persist(session_id="s", tool_call_id="t1", content="x" * 300)
    assert storage.remaining_budget() == 700
    storage.reset_turn()
    assert storage.remaining_budget() == 1000


def test_persist_empty_ids_raises(tmp_path) -> None:
    storage = ToolResultStorage(tmp_path)
    import pytest
    with pytest.raises(ValueError):
        storage.persist(session_id="", tool_call_id="t", content="x")
    with pytest.raises(ValueError):
        storage.persist(session_id="s", tool_call_id="", content="x")
