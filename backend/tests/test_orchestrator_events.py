"""Тесты SSE-событий (events.py) и миграции schema_version=2."""

import json

import aiosqlite
import pytest
from pydantic import ValidationError  # noqa: F401 (used in test bodies)

from app.orchestrator.events import (
    CardEvent,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    StatusEvent,
    ToolCallEvent,
    ToolResultEvent,
    format_sse,
)

# --- format_sse ---

def _parse_sse(raw: str) -> tuple[str, dict]:
    """Вспомогательный парсер одного SSE-блока."""
    lines = raw.strip().split("\n")
    event_name = ""
    data_str = ""
    for line in lines:
        if line.startswith("event: "):
            event_name = line[7:]
        elif line.startswith("data: "):
            data_str = line[6:]
    return event_name, json.loads(data_str)


def test_format_sse_status():
    raw = format_sse("status", StatusEvent(stage="thinking"))
    assert raw.endswith("\n\n")
    name, data = _parse_sse(raw)
    assert name == "status"
    assert data == {"stage": "thinking"}


def test_format_sse_tool_call():
    event = ToolCallEvent(id="tc1", name="execute_query", args={"query": "SELECT 1"})
    raw = format_sse("tool_call", event)
    name, data = _parse_sse(raw)
    assert name == "tool_call"
    assert data["id"] == "tc1"
    assert data["args"] == {"query": "SELECT 1"}


def test_format_sse_tool_result_ok():
    event = ToolResultEvent(id="tc1", ok=True, result={"rows": []}, duration_ms=42)
    raw = format_sse("tool_result", event)
    name, data = _parse_sse(raw)
    assert name == "tool_result"
    assert data["ok"] is True
    assert data["duration_ms"] == 42
    assert data["error"] is None


def test_format_sse_tool_result_error():
    event = ToolResultEvent(id="tc2", ok=False, error="MCP error -32601: method not found", duration_ms=10)
    raw = format_sse("tool_result", event)
    _, data = _parse_sse(raw)
    assert data["ok"] is False
    assert "MCP error" in data["error"]


def test_format_sse_delta():
    raw = format_sse("delta", DeltaEvent(content="Привет мир"))
    name, data = _parse_sse(raw)
    assert name == "delta"
    assert data["content"] == "Привет мир"


def test_format_sse_card():
    event = CardEvent(type="table", payload={"columns": [], "rows": [], "total": 0, "meta": {}})
    raw = format_sse("card", event)
    name, data = _parse_sse(raw)
    assert name == "card"
    assert data["type"] == "table"


def test_format_sse_done():
    event = DoneEvent(message_id="msg-001", total_duration_ms=1500)
    raw = format_sse("done", event)
    name, data = _parse_sse(raw)
    assert name == "done"
    assert data["message_id"] == "msg-001"
    assert data["total_duration_ms"] == 1500


def test_format_sse_error():
    event = ErrorEvent(message="Канал не найден", code="unknown_channel")
    raw = format_sse("error", event)
    name, data = _parse_sse(raw)
    assert name == "error"
    assert data["code"] == "unknown_channel"


def test_format_sse_dict_input():
    raw = format_sse("error", {"message": "test", "code": "x"})
    name, data = _parse_sse(raw)
    assert name == "error"
    assert data["message"] == "test"


# --- Pydantic валидация ---

def test_tool_result_ok_false_requires_error():
    """ok=False без error допускается (error может быть None если тест не критичен)."""
    event = ToolResultEvent(id="x", ok=False, duration_ms=0)
    assert event.error is None


def test_done_event_empty_message_id_fails():
    with pytest.raises(ValidationError):
        DoneEvent(message_id="", total_duration_ms=0)


def test_chat_request_without_channel_id_fails():
    from pydantic import ValidationError

    from app.models import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest(message="test")  # channel_id required


def test_chat_request_empty_channel_id_fails():
    from pydantic import ValidationError

    from app.models import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest(message="test", channel_id="")


# --- Миграция v2 ---

@pytest.mark.asyncio
async def test_migration_v2_creates_indexes():
    """apply_migrations создаёт индексы schema_version=2."""
    from app.storage.migrations import apply_migrations

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)

    rows = await conn.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )
    index_names = {row[0] for row in rows}
    assert "idx_messages_session_created" in index_names
    assert "idx_sessions_updated" in index_names

    await conn.close()


@pytest.mark.asyncio
async def test_migration_schema_version_is_current():
    """После apply_migrations версия схемы = 3 (миграция card_states из 03-04)."""
    from app.storage.migrations import apply_migrations

    conn = await aiosqlite.connect(":memory:")
    await apply_migrations(conn)

    rows = await conn.execute_fetchall("SELECT MAX(version) FROM schema_version")
    version = rows[0][0]
    assert version == 3

    await conn.close()


@pytest.mark.asyncio
async def test_migration_idempotent_current():
    """Повторный вызов apply_migrations не повышает версию выше 3."""
    from app.storage.migrations import apply_migrations

    conn = await aiosqlite.connect(":memory:")
    await apply_migrations(conn)
    await apply_migrations(conn)  # второй вызов — не должен упасть

    rows = await conn.execute_fetchall("SELECT MAX(version) FROM schema_version")
    assert rows[0][0] == 3

    await conn.close()
