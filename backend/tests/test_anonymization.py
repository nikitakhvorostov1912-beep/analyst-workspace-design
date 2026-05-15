"""Тесты анонимизации: forwarding заголовка + extraction токенов + миграция v4.

Plan 04-01 Task 1.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
import pytest_asyncio

from app.orchestrator.cards import (
    TableCardPayload,
    ObjectCardPayload,
    _extract_anon_tokens_from_payload,
    build_card_from_tool_result,
)
from app.orchestrator.persistence import get_card_anon_tokens, save_card_state
from app.storage.migrations import apply_migrations


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def fresh_db():
    """Чистая in-memory БД с миграциями v1..v4 для каждого теста."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)
    yield conn
    await conn.close()


# ---------------------------------------------------------------------------
# Migration v4
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_v4_adds_anon_tokens_column():
    """Миграция v4 добавляет колонку anon_tokens в card_states."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)
    rows = await conn.execute_fetchall("PRAGMA table_info(card_states)")
    col_names = [row[1] for row in rows]
    await conn.close()
    assert "anon_tokens" in col_names


@pytest.mark.asyncio
async def test_migration_v4_idempotent():
    """Повторная миграция v4 не падает."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)
    # Второй вызов не должен упасть
    await apply_migrations(conn)
    await conn.close()


# ---------------------------------------------------------------------------
# save_card_state with anon_tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_card_state_with_anon_tokens_persists_json(fresh_db):
    """save_card_state сохраняет anon_tokens как JSON."""
    await fresh_db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, ?, ?)",
        ("s1", "Test", "ch1"),
    )
    await fresh_db.commit()
    await fresh_db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint) VALUES (?, ?, ?)",
        ("ch1", "Test MCP", "http://localhost:6010/mcp"),
    )
    await fresh_db.commit()

    tokens = ["[ORG-001]", "[INN-001]"]
    await save_card_state(
        fresh_db,
        card_id="card-001",
        session_id="s1",
        message_id="m1",
        tool_name="execute_query",
        original_args={"query": "..."},
        channel_id="ch1",
        anon_tokens=tokens,
    )

    rows = await fresh_db.execute_fetchall(
        "SELECT anon_tokens FROM card_states WHERE card_id = ?", ("card-001",)
    )
    assert rows
    stored = json.loads(rows[0][0])
    assert stored == tokens


@pytest.mark.asyncio
async def test_save_card_state_without_anon_tokens_null(fresh_db):
    """save_card_state с anon_tokens=None → NULL в БД (backward compat)."""
    await fresh_db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, ?, ?)",
        ("s2", "Test", "ch2"),
    )
    await fresh_db.commit()
    await fresh_db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint) VALUES (?, ?, ?)",
        ("ch2", "Test MCP", "http://localhost:6010/mcp"),
    )
    await fresh_db.commit()

    await save_card_state(
        fresh_db,
        card_id="card-002",
        session_id="s2",
        message_id="m2",
        tool_name="get_event_log",
        original_args={},
        channel_id="ch2",
    )

    rows = await fresh_db.execute_fetchall(
        "SELECT anon_tokens FROM card_states WHERE card_id = ?", ("card-002",)
    )
    assert rows
    assert rows[0][0] is None


@pytest.mark.asyncio
async def test_get_card_anon_tokens_returns_list(fresh_db):
    """get_card_anon_tokens возвращает список токенов."""
    await fresh_db.execute(
        "INSERT INTO sessions (id, title, channel_id) VALUES (?, ?, ?)",
        ("s3", "Test", "ch3"),
    )
    await fresh_db.commit()
    await fresh_db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint) VALUES (?, ?, ?)",
        ("ch3", "Test MCP", "http://localhost:6010/mcp"),
    )
    await fresh_db.commit()

    tokens = ["[FIO-001]", "[ORG-002]"]
    await save_card_state(
        fresh_db,
        card_id="card-003",
        session_id="s3",
        message_id="m3",
        tool_name="execute_query",
        original_args={},
        channel_id="ch3",
        anon_tokens=tokens,
    )

    result = await get_card_anon_tokens(fresh_db, "card-003")
    assert result == tokens


# ---------------------------------------------------------------------------
# _extract_anon_tokens_from_payload
# ---------------------------------------------------------------------------


def test_extract_anon_tokens_from_table_payload():
    """Токены в строках таблицы извлекаются."""
    payload = {
        "columns": [{"name": "Имя", "type": "String"}],
        "rows": [["[ORG-001]"], ["[INN-001]"]],
        "total": 2,
        "meta": {},
    }
    result = _extract_anon_tokens_from_payload(payload)
    assert "[ORG-001]" in result
    assert "[INN-001]" in result


def test_extract_anon_tokens_unique_sorted():
    """Токены дедуплицируются и сортируются."""
    payload = {
        "rows": [["[ORG-001]", "[ORG-001]", "[INN-001]"]],
    }
    result = _extract_anon_tokens_from_payload(payload)
    assert result == ["[INN-001]", "[ORG-001]"]


def test_extract_anon_tokens_nested_object():
    """Токены в nested dict/list находятся."""
    payload = {
        "header": {"name": "[FIO-001]"},
        "attributes": [{"name": "ИНН", "value": "[INN-001]"}],
    }
    result = _extract_anon_tokens_from_payload(payload)
    assert "[FIO-001]" in result
    assert "[INN-001]" in result


def test_extract_anon_tokens_empty():
    """Нет токенов → пустой список."""
    payload = {"rows": [["ООО Ромашка", "7707123456"]]}
    result = _extract_anon_tokens_from_payload(payload)
    assert result == []


# ---------------------------------------------------------------------------
# card_id generated for table and object
# ---------------------------------------------------------------------------


def test_card_id_generated_for_table():
    """build_card_from_tool_result для execute_query возвращает card_id."""
    result = {
        "columns": [{"name": "Наименование", "type": "String"}],
        "rows": [["ООО Ромашка"]],
        "total": 1,
    }
    card = build_card_from_tool_result("execute_query", {}, result)
    assert card is not None
    assert card["payload"]["card_id"] is not None
    assert len(card["payload"]["card_id"]) == 36  # UUID4 format


def test_card_id_generated_for_object():
    """build_card_from_tool_result для get_object_by_link возвращает card_id."""
    result = {
        "header": {"name": "TestObj", "type": "Справочник", "path": "/"},
        "attributes": [],
        "tabular_sections": [],
        "forms": [],
        "templates": [],
    }
    card = build_card_from_tool_result("get_object_by_link", {}, result)
    assert card is not None
    assert card["payload"]["card_id"] is not None


# ---------------------------------------------------------------------------
# run_chat_loop passes anon header to MCPClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_chat_loop_passes_anon_header_to_mcp():
    """run_chat_loop с x_anon_enabled=True создаёт MCPClient с X-Anon-Enabled заголовком."""
    from app.models import ChatRequest

    captured_headers = {}

    class FakeMCPClient:
        def __init__(self, endpoint, headers=None, timeout=30.0):
            captured_headers.update(headers or {})
            self.session_id = "fake-session"
            self._tools_cache = []

        async def initialize(self):
            from app.clients.mcp import MCPSession
            return MCPSession(session_id="fake", mcp_version="2025-03-26", server_name="test")

        async def list_tools(self):
            return []

        async def aclose(self):
            pass

    with patch("app.orchestrator.loop.MCPClient", FakeMCPClient), \
         patch("app.orchestrator.loop.LLMClient") as MockLLM, \
         patch("app.orchestrator.loop.ensure_session", return_value="sid-1"), \
         patch("app.orchestrator.loop.count_session_messages", return_value=1), \
         patch("app.orchestrator.loop.save_user_message", return_value="mid-1"), \
         patch("app.orchestrator.loop.lookup_mcp_endpoint", return_value="http://localhost:6010/mcp"), \
         patch("app.orchestrator.loop.save_assistant_message", return_value="msg-1"), \
         patch("app.orchestrator.loop.touch_session"):

        mock_llm_instance = AsyncMock()
        mock_llm_instance.stream_chat_completion.return_value = _async_gen([
            {"delta": {"content": "Ответ"}, "finish_reason": "stop"}
        ])
        mock_llm_instance.aclose = AsyncMock()
        MockLLM.return_value = mock_llm_instance

        from app.orchestrator.loop import run_chat_loop
        import aiosqlite

        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        from app.storage.migrations import apply_migrations
        await apply_migrations(db)

        request = ChatRequest(message="test", channel_id="ch1")
        events = []
        async for event in run_chat_loop(
            db, request, "key", "http://llm/v1", "model", x_anon_enabled=True
        ):
            events.append(event)

        await db.close()

    assert captured_headers.get("X-Anon-Enabled") == "true"


@pytest.mark.asyncio
async def test_run_chat_loop_without_anon_no_header():
    """run_chat_loop без x_anon_enabled не передаёт X-Anon-Enabled заголовок."""
    from app.models import ChatRequest

    captured_headers = {}

    class FakeMCPClientNoAnon:
        def __init__(self, endpoint, headers=None, timeout=30.0):
            if headers:
                captured_headers.update(headers)
            self.session_id = "fake-session"
            self._tools_cache = []

        async def initialize(self):
            from app.clients.mcp import MCPSession
            return MCPSession(session_id="fake", mcp_version="2025-03-26", server_name="test")

        async def list_tools(self):
            return []

        async def aclose(self):
            pass

    with patch("app.orchestrator.loop.MCPClient", FakeMCPClientNoAnon), \
         patch("app.orchestrator.loop.LLMClient") as MockLLM, \
         patch("app.orchestrator.loop.ensure_session", return_value="sid-1"), \
         patch("app.orchestrator.loop.count_session_messages", return_value=1), \
         patch("app.orchestrator.loop.save_user_message", return_value="mid-1"), \
         patch("app.orchestrator.loop.lookup_mcp_endpoint", return_value="http://localhost:6010/mcp"), \
         patch("app.orchestrator.loop.save_assistant_message", return_value="msg-1"), \
         patch("app.orchestrator.loop.touch_session"):

        mock_llm_instance = AsyncMock()
        mock_llm_instance.stream_chat_completion.return_value = _async_gen([
            {"delta": {"content": "Ответ"}, "finish_reason": "stop"}
        ])
        mock_llm_instance.aclose = AsyncMock()
        MockLLM.return_value = mock_llm_instance

        from app.orchestrator.loop import run_chat_loop
        import aiosqlite

        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        from app.storage.migrations import apply_migrations
        await apply_migrations(db)

        request = ChatRequest(message="test", channel_id="ch1")
        async for _ in run_chat_loop(
            db, request, "key", "http://llm/v1", "model"
        ):
            pass

        await db.close()

    assert "X-Anon-Enabled" not in captured_headers


# ---------------------------------------------------------------------------
# Helper: async generator for mock streaming
# ---------------------------------------------------------------------------


async def _async_gen(items):
    for item in items:
        yield item
