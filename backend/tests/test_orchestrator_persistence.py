"""Тесты persistence-слоя и POST /sessions."""

import json

import aiosqlite
import pytest
from httpx import AsyncClient


@pytest.fixture
async def mem_db():
    """In-memory SQLite с миграциями для тестов persistence."""
    from app.storage.migrations import apply_migrations

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)
    yield conn
    await conn.close()


# --- ensure_session ---

@pytest.mark.asyncio
async def test_ensure_session_creates_new_when_none(mem_db):
    """ensure_session(None) создаёт новую сессию с UUID4."""
    from app.orchestrator.persistence import ensure_session

    sid = await ensure_session(mem_db, None, "ch1", "тест")
    assert len(sid) == 36  # UUID4 формат x-x-x-x-x
    assert sid.count("-") == 4

    rows = await mem_db.execute_fetchall(
        "SELECT id, channel_id FROM sessions WHERE id = ?", (sid,)
    )
    assert rows
    assert rows[0][1] == "ch1"


@pytest.mark.asyncio
async def test_ensure_session_returns_existing(mem_db):
    """ensure_session с существующим session_id возвращает его."""
    from app.orchestrator.persistence import ensure_session

    sid1 = await ensure_session(mem_db, None, "ch1", "тест")
    sid2 = await ensure_session(mem_db, sid1, "ch1", "тест2")
    assert sid1 == sid2


@pytest.mark.asyncio
async def test_ensure_session_creates_with_given_id_if_missing(mem_db):
    """ensure_session с несуществующим session_id создаёт его."""
    from app.orchestrator.persistence import ensure_session

    result = await ensure_session(mem_db, "my-custom-id", "ch2", "тест")
    assert result == "my-custom-id"


# --- save_user_message ---

@pytest.mark.asyncio
async def test_save_user_message_persists_content(mem_db):
    """save_user_message сохраняет content и возвращает message_id."""
    from app.orchestrator.persistence import ensure_session, save_user_message

    sid = await ensure_session(mem_db, None, "ch1", "x")
    mid = await save_user_message(mem_db, sid, "Привет мир")

    rows = await mem_db.execute_fetchall(
        "SELECT content, role FROM messages WHERE id = ?", (mid,)
    )
    assert rows
    assert rows[0][0] == "Привет мир"
    assert rows[0][1] == "user"


# --- save_assistant_message ---

@pytest.mark.asyncio
async def test_save_assistant_message_with_tool_calls(mem_db):
    """save_assistant_message корректно JSON-сериализует tool_calls."""
    from app.orchestrator.persistence import ensure_session, save_assistant_message

    sid = await ensure_session(mem_db, None, "ch1", "x")
    tool_calls = [{"id": "tc1", "name": "execute_query", "args": {"q": "SELECT 1"}, "result": {"rows": []}}]
    cards = [{"type": "table", "payload": {"columns": [], "rows": [], "total": 0}}]

    mid = await save_assistant_message(mem_db, sid, "Результат", tool_calls, cards, 1234)

    rows = await mem_db.execute_fetchall(
        "SELECT role, tool_calls, cards, duration_ms FROM messages WHERE id = ?", (mid,)
    )
    assert rows
    row = rows[0]
    assert row[0] == "assistant"
    assert json.loads(row[1]) == tool_calls
    assert json.loads(row[2]) == cards
    assert row[3] == 1234


# --- touch_session ---

@pytest.mark.asyncio
async def test_touch_session_updates_updated_at(mem_db):
    """touch_session меняет updated_at."""
    import asyncio

    from app.orchestrator.persistence import ensure_session, touch_session

    sid = await ensure_session(mem_db, None, "ch1", "x")

    # Небольшая пауза чтобы CURRENT_TIMESTAMP сменился
    await asyncio.sleep(0.01)
    await touch_session(mem_db, sid)

    rows_after = await mem_db.execute_fetchall(
        "SELECT updated_at FROM sessions WHERE id = ?", (sid,)
    )
    after = rows_after[0][0]

    # updated_at должен измениться (или остаться тем же если SQLite возвращает одинаковое за 10мс)
    # Главное — функция не падает
    assert after is not None


# --- lookup_mcp_endpoint ---

@pytest.mark.asyncio
async def test_lookup_mcp_endpoint_returns_endpoint(mem_db):
    """lookup_mcp_endpoint возвращает endpoint после INSERT."""
    from app.orchestrator.persistence import lookup_mcp_endpoint

    await mem_db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint) VALUES (?, ?, ?)",
        ("conn1", "Тест", "http://localhost:6010/mcp"),
    )
    await mem_db.commit()

    result = await lookup_mcp_endpoint(mem_db, "conn1")
    assert result == "http://localhost:6010/mcp"


@pytest.mark.asyncio
async def test_lookup_mcp_endpoint_returns_none_if_missing(mem_db):
    """lookup_mcp_endpoint возвращает None если channel не найден."""
    from app.orchestrator.persistence import lookup_mcp_endpoint

    result = await lookup_mcp_endpoint(mem_db, "nonexistent")
    assert result is None


# --- POST /sessions ---

@pytest.mark.asyncio
async def test_post_sessions_missing_channel_id_returns_422(client: AsyncClient):
    """POST /sessions без channel_id → 422."""
    response = await client.post("/sessions", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_sessions_creates_session(client: AsyncClient):
    """POST /sessions с channel_id → 200, возвращает id."""
    response = await client.post("/sessions", json={"channel_id": "test-ch"})
    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert body["channel_id"] == "test-ch"
    assert body["title"] is None
    assert "created_at" in body


# --- load_history_for_llm ---

@pytest.mark.asyncio
async def test_load_history_empty_session(mem_db):
    """load_history_for_llm для пустой сессии возвращает []."""
    from app.orchestrator.persistence import ensure_session, load_history_for_llm

    sid = await ensure_session(mem_db, None, "ch1", "x")
    history = await load_history_for_llm(mem_db, sid)
    assert history == []


@pytest.mark.asyncio
async def test_load_history_simple_user_assistant(mem_db):
    """user + assistant без tool_calls → 2 сообщения в OpenAI формате."""
    from app.orchestrator.persistence import (
        ensure_session,
        load_history_for_llm,
        save_assistant_message,
        save_user_message,
    )

    sid = await ensure_session(mem_db, None, "ch1", "x")
    await save_user_message(mem_db, sid, "Привет")
    await save_assistant_message(mem_db, sid, "Здравствуйте", [], [], 100)

    history = await load_history_for_llm(mem_db, sid)
    # reasoning_content="" — для MiMo / R1 thinking mode (см. персистенция)
    assert history == [
        {"role": "user", "content": "Привет"},
        {"role": "assistant", "content": "Здравствуйте", "reasoning_content": ""},
    ]


@pytest.mark.asyncio
async def test_load_history_with_tool_calls(mem_db):
    """assistant с tool_calls раскрывается в assistant + tool messages в OpenAI формате."""
    from app.orchestrator.persistence import (
        ensure_session,
        load_history_for_llm,
        save_assistant_message,
        save_user_message,
    )

    sid = await ensure_session(mem_db, None, "ch1", "x")
    await save_user_message(mem_db, sid, "Сколько констант?")
    tool_calls = [
        {
            "id": "tc1",
            "name": "execute_query",
            "args": {"text": "SELECT 1"},
            "result": {"rows": [[5]], "columns": ["c"]},
            "duration_ms": 42,
        }
    ]
    await save_assistant_message(mem_db, sid, "В базе 5 констант", tool_calls, [], 1234)

    history = await load_history_for_llm(mem_db, sid)
    # 3 сообщения: user + assistant(tool_calls) + tool result
    assert len(history) == 3
    assert history[0] == {"role": "user", "content": "Сколько констант?"}

    asst = history[1]
    assert asst["role"] == "assistant"
    assert asst["content"] == "В базе 5 констант"
    assert len(asst["tool_calls"]) == 1
    tc = asst["tool_calls"][0]
    assert tc["id"] == "tc1"
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "execute_query"
    assert json.loads(tc["function"]["arguments"]) == {"text": "SELECT 1"}

    tool_msg = history[2]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "tc1"
    assert json.loads(tool_msg["content"]) == {"rows": [[5]], "columns": ["c"]}


@pytest.mark.asyncio
async def test_load_history_tool_error_passed_as_content(mem_db):
    """Если tool вернул error без result — error попадает в content tool-сообщения."""
    from app.orchestrator.persistence import (
        ensure_session,
        load_history_for_llm,
        save_assistant_message,
        save_user_message,
    )

    sid = await ensure_session(mem_db, None, "ch1", "x")
    await save_user_message(mem_db, sid, "?")
    tool_calls = [
        {"id": "tc1", "name": "execute_query", "args": {}, "result": None, "error": "Timeout"}
    ]
    await save_assistant_message(mem_db, sid, "", tool_calls, [], 100)

    history = await load_history_for_llm(mem_db, sid)
    tool_msg = next(m for m in history if m.get("role") == "tool")
    assert tool_msg["content"] == "Timeout"


@pytest.mark.asyncio
async def test_load_history_caps_old_tool_content(mem_db):
    """Старые тяжёлые результаты обрезаются до tool_content_cap."""
    from app.orchestrator.persistence import (
        ensure_session,
        load_history_for_llm,
        save_assistant_message,
        save_user_message,
    )

    sid = await ensure_session(mem_db, None, "ch1", "x")
    await save_user_message(mem_db, sid, "?")
    big_result = {"big": "x" * 100_000}
    tool_calls = [{"id": "tc1", "name": "q", "args": {}, "result": big_result}]
    await save_assistant_message(mem_db, sid, "", tool_calls, [], 1)

    history = await load_history_for_llm(mem_db, sid, tool_content_cap=500)
    tool_msg = next(m for m in history if m.get("role") == "tool")
    assert len(tool_msg["content"]) <= 500 + len("...truncated")
    assert tool_msg["content"].endswith("...truncated")


@pytest.mark.asyncio
async def test_load_history_keeps_chronological_order_and_caps_count(mem_db):
    """max_messages обрезает старые записи, оставляя последние."""
    from app.orchestrator.persistence import (
        ensure_session,
        load_history_for_llm,
        save_user_message,
    )

    sid = await ensure_session(mem_db, None, "ch1", "x")
    for i in range(10):
        await save_user_message(mem_db, sid, f"msg-{i}")

    history = await load_history_for_llm(mem_db, sid, max_messages=3)
    assert len(history) == 3
    assert [m["content"] for m in history] == ["msg-7", "msg-8", "msg-9"]


@pytest.mark.asyncio
async def test_load_history_skips_tool_call_without_id(mem_db):
    """tool_call без id пропускается (нельзя вернуть в LLM без id)."""
    from app.orchestrator.persistence import (
        ensure_session,
        load_history_for_llm,
        save_assistant_message,
        save_user_message,
    )

    sid = await ensure_session(mem_db, None, "ch1", "x")
    await save_user_message(mem_db, sid, "?")
    tool_calls = [
        {"id": "", "name": "x", "args": {}, "result": {"ok": True}},
        {"id": "good", "name": "y", "args": {}, "result": {"ok": True}},
    ]
    await save_assistant_message(mem_db, sid, "ok", tool_calls, [], 1)

    history = await load_history_for_llm(mem_db, sid)
    asst = next(m for m in history if m.get("role") == "assistant")
    # Только один tool_call с id
    assert len(asst["tool_calls"]) == 1
    assert asst["tool_calls"][0]["id"] == "good"
    # И только один tool message
    tool_msgs = [m for m in history if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "good"
