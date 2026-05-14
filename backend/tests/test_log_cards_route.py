"""Тесты endpoint POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more.

TDD: RED → GREEN.
Plan 03-04 Task 1.
"""

import json
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.storage.migrations import apply_migrations
from app.orchestrator.persistence import save_card_state, get_card_state
from app.orchestrator.cards import build_card_from_tool_result
from app.routes.log_cards import get_app_db


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


@pytest_asyncio.fixture
async def client_with_db(fresh_db):
    """AsyncClient с ASGI-транспортом и переопределённой DB dependency."""
    from app.main import app

    async def override_db():
        yield fresh_db

    app.dependency_overrides[get_app_db] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        async with app.router.lifespan_context(app):
            yield ac, fresh_db

    app.dependency_overrides.pop(get_app_db, None)


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
# Loop: card_state сохраняется после save_assistant_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_saves_card_state_on_log_card(fresh_db):
    """После вызова get_event_log loop сохраняет card_state в БД."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.models import ChatRequest
    from app.orchestrator.loop import run_chat_loop

    # Настраиваем БД: сессия + MCP connection
    await fresh_db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES ('s-loop', 'T', 'ch-loop')"
    )
    await fresh_db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, channel) VALUES ('ch-loop', 'T', 'http://localhost:6010/mcp', 'ch-loop')"
    )
    await fresh_db.commit()

    log_tool_result = {
        "entries": [{"time": "2026-05-14T10:00:00", "level": "Info", "event": "start"}],
        "next_cursor": "cursor-next",
    }

    # Мокаем LLM: первый вызов → tool_call get_event_log; второй → финальный ответ
    chunk_tool = {
        "delta": {"tool_calls": [{"index": 0, "id": "tc-1", "function": {"name": "get_event_log", "arguments": "{}"}}]},
        "finish_reason": "tool_calls",
    }
    chunk_done = {"delta": {"content": "Журнал загружен."}, "finish_reason": "stop"}

    call_count = 0

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield chunk_tool
        else:
            yield chunk_done

    with patch("app.orchestrator.loop.LLMClient") as MockLLM, \
         patch("app.orchestrator.loop.MCPClient") as MockMCP:

        llm_inst = MagicMock()
        llm_inst.stream_chat_completion = mock_stream
        llm_inst.aclose = AsyncMock()
        MockLLM.return_value = llm_inst

        mcp_inst = AsyncMock()
        mcp_inst.initialize = AsyncMock()
        mcp_inst.list_tools = AsyncMock(return_value=[])
        mcp_inst.call_tool = AsyncMock(return_value=log_tool_result)
        mcp_inst.aclose = AsyncMock()
        MockMCP.return_value = mcp_inst

        request = ChatRequest(message="Покажи журнал", session_id="s-loop", channel_id="ch-loop")

        events = []
        async for ev in run_chat_loop(
            db=fresh_db,
            request=request,
            api_key="test-key",
            llm_endpoint="http://localhost/v1",
            llm_model="test-model",
        ):
            events.append(ev)

    # Проверяем что в БД есть card_state с card_id
    rows = await fresh_db.execute_fetchall("SELECT * FROM card_states WHERE session_id = 's-loop'")
    assert rows, "card_state должен быть сохранён для LogCard"
    assert rows[0]["tool_name"] == "get_event_log"


# ---------------------------------------------------------------------------
# Route: POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_load_more_returns_next_page(client_with_db):
    """POST load-more возвращает 200 + {entries, next_cursor}."""
    client, db = client_with_db

    sid = "s-001"
    mid = "m-001"
    cid = "c-001"
    await db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, 'T', ?)",
        (sid, "ch-1"),
    )
    await db.execute(
        "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, 'assistant', 'ok')",
        (mid, sid),
    )
    await save_card_state(
        db,
        card_id=cid,
        session_id=sid,
        message_id=mid,
        tool_name="get_event_log",
        original_args={"level": "Error"},
        channel_id="ch-1",
    )
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, channel) VALUES (?, 'T', ?, ?)",
        ("ch-1", "http://localhost:6010/mcp", "ch-1"),
    )
    await db.commit()

    mock_result = {
        "entries": [{"time": "2026-05-14T11:00:00", "level": "Info", "event": "e2"}],
        "next_cursor": "next_page_cursor",
    }

    with patch("app.routes.log_cards.MCPClient") as MockMCPClient:
        mock_instance = AsyncMock()
        mock_instance.initialize = AsyncMock()
        mock_instance.call_tool = AsyncMock(return_value=mock_result)
        mock_instance.aclose = AsyncMock()
        MockMCPClient.return_value = mock_instance

        response = await client.post(
            f"/sessions/{sid}/messages/{mid}/cards/{cid}/load-more",
            json={"cursor": "original_cursor"},
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "entries" in data
    assert len(data["entries"]) == 1
    assert data["next_cursor"] == "next_page_cursor"


@pytest.mark.asyncio
async def test_post_load_more_unknown_card_returns_404(client_with_db):
    """load-more на несуществующий card_id → 404."""
    client, db = client_with_db
    response = await client.post(
        "/sessions/s-999/messages/m-999/cards/c-missing/load-more",
        json={"cursor": "x"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_load_more_unknown_channel_returns_502(client_with_db):
    """card_state существует, channel не найден → 502."""
    client, db = client_with_db

    sid = "s-002"
    mid = "m-002"
    cid = "c-002"
    await db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, 'T', 'nonexistent-ch')", (sid,)
    )
    await db.execute(
        "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, 'assistant', 'ok')",
        (mid, sid),
    )
    await save_card_state(
        db,
        card_id=cid,
        session_id=sid,
        message_id=mid,
        tool_name="get_event_log",
        original_args={},
        channel_id="nonexistent-ch",
    )
    await db.commit()

    response = await client.post(
        f"/sessions/{sid}/messages/{mid}/cards/{cid}/load-more",
        json={"cursor": "x"},
    )
    assert response.status_code == 502
    detail = response.json()["detail"].lower()
    assert "недоступен" in detail or "channel" in detail


@pytest.mark.asyncio
async def test_post_load_more_mcp_call_fails_returns_502(client_with_db):
    """MCPClient.call_tool бросает исключение → 502."""
    import httpx
    client, db = client_with_db

    sid = "s-003"
    mid = "m-003"
    cid = "c-003"
    await db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, 'T', 'ch-3')", (sid,)
    )
    await db.execute(
        "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, 'assistant', 'ok')",
        (mid, sid),
    )
    await save_card_state(
        db,
        card_id=cid,
        session_id=sid,
        message_id=mid,
        tool_name="get_event_log",
        original_args={},
        channel_id="ch-3",
    )
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, channel) VALUES (?, 'T', ?, ?)",
        ("ch-3", "http://localhost:6010/mcp", "ch-3"),
    )
    await db.commit()

    with patch("app.routes.log_cards.MCPClient") as MockMCPClient:
        mock_instance = AsyncMock()
        mock_instance.initialize = AsyncMock()
        mock_instance.call_tool = AsyncMock(side_effect=httpx.ConnectError("Timeout"))
        mock_instance.aclose = AsyncMock()
        MockMCPClient.return_value = mock_instance

        response = await client.post(
            f"/sessions/{sid}/messages/{mid}/cards/{cid}/load-more",
            json={"cursor": "x"},
        )
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_post_load_more_validates_cursor_strict(client_with_db):
    """POST body с cursor=123 (int) → 422 Pydantic strict."""
    client, db = client_with_db
    response = await client.post(
        "/sessions/s/messages/m/cards/c/load-more",
        json={"cursor": 123},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_load_more_sid_mismatch_returns_404(client_with_db):
    """card_state.session_id != sid в URL → 404 (ownership check)."""
    client, db = client_with_db

    sid_real = "s-real"
    mid = "m-004"
    cid = "c-004"
    await db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, 'T', 'ch-1')", (sid_real,)
    )
    await db.execute(
        "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, 'assistant', 'ok')",
        (mid, sid_real),
    )
    await save_card_state(
        db,
        card_id=cid,
        session_id=sid_real,
        message_id=mid,
        tool_name="get_event_log",
        original_args={},
        channel_id="ch-1",
    )
    await db.commit()

    # Пытаемся запросить другой sid
    response = await client.post(
        f"/sessions/s-attacker/messages/{mid}/cards/{cid}/load-more",
        json={"cursor": "x"},
    )
    assert response.status_code == 404
