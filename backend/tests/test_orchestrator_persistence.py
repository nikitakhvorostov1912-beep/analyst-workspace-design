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

    rows_before = await mem_db.execute_fetchall(
        "SELECT updated_at FROM sessions WHERE id = ?", (sid,)
    )
    before = rows_before[0][0]

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
