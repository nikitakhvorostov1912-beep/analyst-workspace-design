"""Тесты endpoint POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more.

TDD: RED → GREEN → (refactor if needed).
Plan 03-04 Task 1.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import aiosqlite

from app.storage.migrations import apply_migrations
from app.orchestrator.persistence import save_card_state, get_card_state
from app.orchestrator.cards import build_card_from_tool_result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def fresh_db():
    """Чистая in-memory БД с миграциями v1..v3 для каждого теста."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)
    yield conn
    await conn.close()


async def _seed_session_and_message(db: aiosqlite.Connection) -> tuple[str, str]:
    """Создаёт session и message, возвращает (session_id, message_id)."""
    sid = "test-session-001"
    mid = "test-message-001"
    await db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, ?, ?)",
        (sid, "Test", "channel-1"),
    )
    await db.execute(
        "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, 'assistant', 'ok')",
        (mid, sid),
    )
    await db.commit()
    return sid, mid


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_v3_creates_card_states_table(fresh_db):
    """После apply_migrations таблица card_states существует."""
    rows = await fresh_db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='card_states'"
    )
    assert rows, "Таблица card_states должна существовать после миграции v3"


@pytest.mark.asyncio
async def test_migration_v3_card_states_columns(fresh_db):
    """card_states содержит ожидаемые столбцы."""
    rows = await fresh_db.execute_fetchall("PRAGMA table_info(card_states)")
    col_names = {row[1] for row in rows}
    expected = {"card_id", "session_id", "message_id", "tool_name", "original_args", "channel_id", "created_at"}
    assert expected.issubset(col_names), f"Недостающие столбцы: {expected - col_names}"


@pytest.mark.asyncio
async def test_migration_v3_idempotent(fresh_db):
    """Повторный apply_migrations не падает и не дублирует данные."""
    await apply_migrations(fresh_db)  # второй раз
    rows = await fresh_db.execute_fetchall(
        "SELECT COUNT(*) FROM schema_version WHERE version = 3"
    )
    assert rows[0][0] == 1, "Запись version=3 должна быть ровно одна"


# ---------------------------------------------------------------------------
# Persistence: save_card_state / get_card_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_card_state_persists(fresh_db):
    """save_card_state записывает строку в card_states."""
    sid, mid = await _seed_session_and_message(fresh_db)
    await save_card_state(
        fresh_db,
        card_id="card-001",
        session_id=sid,
        message_id=mid,
        tool_name="get_event_log",
        original_args={"level": "Error", "limit": 50},
        channel_id="channel-1",
    )
    rows = await fresh_db.execute_fetchall(
        "SELECT * FROM card_states WHERE card_id = ?", ("card-001",)
    )
    assert rows, "Строка должна быть вставлена"
    row = rows[0]
    assert row["card_id"] == "card-001"
    assert row["tool_name"] == "get_event_log"
    assert json.loads(row["original_args"]) == {"level": "Error", "limit": 50}


@pytest.mark.asyncio
async def test_get_card_state_returns_row(fresh_db):
    """get_card_state возвращает dict с полями."""
    sid, mid = await _seed_session_and_message(fresh_db)
    await save_card_state(
        fresh_db,
        card_id="card-002",
        session_id=sid,
        message_id=mid,
        tool_name="get_event_log",
        original_args={"level": "Warning"},
        channel_id="channel-2",
    )
    result = await get_card_state(fresh_db, "card-002")
    assert result is not None
    assert result["card_id"] == "card-002"
    assert result["session_id"] == sid
    assert result["message_id"] == mid
    assert result["channel_id"] == "channel-2"
    assert isinstance(result["original_args"], str)  # JSON-строка


@pytest.mark.asyncio
async def test_get_card_state_unknown_returns_none(fresh_db):
    """get_card_state на несуществующий card_id возвращает None."""
    result = await get_card_state(fresh_db, "missing-card-999")
    assert result is None


# ---------------------------------------------------------------------------
# cards.py: card_id генерируется в LogCard
# ---------------------------------------------------------------------------


def test_build_card_from_tool_result_returns_card_id_for_log():
    """build_card_from_tool_result для get_event_log возвращает card_id в payload."""
    mcp_result = {
        "entries": [
            {"time": "2026-05-14T10:00:00", "level": "Info", "event": "_$Session$_.Start"}
        ],
        "next_cursor": "abc123",
    }
    card = build_card_from_tool_result("get_event_log", {}, mcp_result)
    assert card is not None
    assert card["type"] == "log"
    card_id = card["payload"].get("card_id")
    assert card_id is not None, "card_id должен быть в payload"
    # Проверяем что это UUID-подобная строка (36 символов)
    assert len(card_id) == 36


def test_build_card_from_tool_result_card_id_unique():
    """Каждый вызов _build_log_card генерирует уникальный card_id."""
    mcp_result = {"entries": [], "next_cursor": None}
    card1 = build_card_from_tool_result("get_event_log", {}, mcp_result)
    card2 = build_card_from_tool_result("get_event_log", {}, mcp_result)
    assert card1 is not None and card2 is not None
    assert card1["payload"]["card_id"] != card2["payload"]["card_id"]


# ---------------------------------------------------------------------------
# Route: POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_load_more_returns_next_page(client, fresh_db):
    """POST load-more возвращает 200 + {entries, next_cursor}."""
    # Настраиваем БД с session + message + card_state
    sid = "s-001"
    mid = "m-001"
    cid = "c-001"
    await fresh_db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, 'T', ?)",
        (sid, "ch-1"),
    )
    await fresh_db.execute(
        "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, 'assistant', 'ok')",
        (mid, sid),
    )
    await save_card_state(
        fresh_db,
        card_id=cid,
        session_id=sid,
        message_id=mid,
        tool_name="get_event_log",
        original_args={"level": "Error"},
        channel_id="ch-1",
    )
    await fresh_db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, channel) VALUES (?, 'T', ?, ?)",
        ("ch-1", "http://localhost:6010/mcp", "ch-1"),
    )
    await fresh_db.commit()

    mock_result = {
        "entries": [{"time": "2026-05-14T11:00:00", "level": "Info", "event": "e2"}],
        "next_cursor": "next_page_cursor",
    }

    with patch("app.routes.log_cards.get_app_db", return_value=fresh_db), \
         patch("app.routes.log_cards.MCPClient") as MockMCPClient:
        mock_instance = AsyncMock()
        mock_instance.initialize = AsyncMock()
        mock_instance.call_tool = AsyncMock(return_value=mock_result)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockMCPClient.return_value = mock_instance

        response = await client.post(
            f"/sessions/{sid}/messages/{mid}/cards/{cid}/load-more",
            json={"cursor": "original_cursor"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert len(data["entries"]) == 1
    assert data["next_cursor"] == "next_page_cursor"


@pytest.mark.asyncio
async def test_post_load_more_unknown_card_returns_404(client, fresh_db):
    """load-more на несуществующий card_id → 404."""
    with patch("app.routes.log_cards.get_app_db", return_value=fresh_db):
        response = await client.post(
            "/sessions/s-999/messages/m-999/cards/c-missing/load-more",
            json={"cursor": "x"},
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_load_more_unknown_channel_returns_502(client, fresh_db):
    """card_state существует, channel не найден → 502."""
    sid = "s-002"
    mid = "m-002"
    cid = "c-002"
    await fresh_db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, 'T', 'nonexistent-ch')", (sid,)
    )
    await fresh_db.execute(
        "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, 'assistant', 'ok')",
        (mid, sid),
    )
    await save_card_state(
        fresh_db,
        card_id=cid,
        session_id=sid,
        message_id=mid,
        tool_name="get_event_log",
        original_args={},
        channel_id="nonexistent-ch",
    )
    await fresh_db.commit()

    with patch("app.routes.log_cards.get_app_db", return_value=fresh_db):
        response = await client.post(
            f"/sessions/{sid}/messages/{mid}/cards/{cid}/load-more",
            json={"cursor": "x"},
        )
    assert response.status_code == 502
    assert "недоступен" in response.json()["detail"].lower() or "channel" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_post_load_more_mcp_call_fails_returns_502(client, fresh_db):
    """MCPClient.call_tool бросает исключение → 502."""
    import httpx
    sid = "s-003"
    mid = "m-003"
    cid = "c-003"
    await fresh_db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, 'T', 'ch-3')", (sid,)
    )
    await fresh_db.execute(
        "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, 'assistant', 'ok')",
        (mid, sid),
    )
    await save_card_state(
        fresh_db,
        card_id=cid,
        session_id=sid,
        message_id=mid,
        tool_name="get_event_log",
        original_args={},
        channel_id="ch-3",
    )
    await fresh_db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, channel) VALUES (?, 'T', ?, ?)",
        ("ch-3", "http://localhost:6010/mcp", "ch-3"),
    )
    await fresh_db.commit()

    with patch("app.routes.log_cards.get_app_db", return_value=fresh_db), \
         patch("app.routes.log_cards.MCPClient") as MockMCPClient:
        mock_instance = AsyncMock()
        mock_instance.initialize = AsyncMock()
        mock_instance.call_tool = AsyncMock(side_effect=httpx.ConnectError("Timeout"))
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockMCPClient.return_value = mock_instance

        response = await client.post(
            f"/sessions/{sid}/messages/{mid}/cards/{cid}/load-more",
            json={"cursor": "x"},
        )
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_post_load_more_validates_cursor_strict(client, fresh_db):
    """POST body с cursor=123 (int) → 422 Pydantic strict."""
    with patch("app.routes.log_cards.get_app_db", return_value=fresh_db):
        response = await client.post(
            "/sessions/s/messages/m/cards/c/load-more",
            json={"cursor": 123},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_load_more_sid_mismatch_returns_404(client, fresh_db):
    """card_state.session_id != sid в URL → 404 (ownership check)."""
    sid_real = "s-real"
    mid = "m-004"
    cid = "c-004"
    await fresh_db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, 'T', 'ch-1')", (sid_real,)
    )
    await fresh_db.execute(
        "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, 'assistant', 'ok')",
        (mid, sid_real),
    )
    await save_card_state(
        fresh_db,
        card_id=cid,
        session_id=sid_real,
        message_id=mid,
        tool_name="get_event_log",
        original_args={},
        channel_id="ch-1",
    )
    await fresh_db.commit()

    # Пытаемся запросить другой sid
    with patch("app.routes.log_cards.get_app_db", return_value=fresh_db):
        response = await client.post(
            f"/sessions/s-attacker/messages/{mid}/cards/{cid}/load-more",
            json={"cursor": "x"},
        )
    assert response.status_code == 404
