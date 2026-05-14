"""Тесты покрытия оркестратора — uncovered branches loop.py.

Покрывает:
- MAX_TOOL_ITERATIONS exit (code=tool_loop_limit)
- init_error при ошибке save_user_message
- finish_reason="length" завершает loop без ошибки
- finish_reason="content_filter" аналогично
- unknown_channel эмитит error ДО initialize MCP
- tool_args с непарсируемым JSON → пустой dict
- _cap_content обрезает при >50k байт
"""

import json

import aiosqlite
import pytest

from app.models import ChatRequest
from app.orchestrator.loop import TOOL_CONTENT_CAP, _cap_content

from .fixtures.mcp_responses import (
    FakeMCPClient,
    make_text_chunk,
    make_tool_call_chunk,
    make_tool_calls_finish_chunk,
    stub_llm_stream,
)


@pytest.fixture
async def mem_db():
    """In-memory SQLite с миграциями и тестовым каналом."""
    from app.storage.migrations import apply_migrations

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)
    await conn.execute(
        "INSERT INTO mcp_connections (id, name, endpoint) VALUES (?, ?, ?)",
        ("test-ch", "Тест", "http://fake-mcp/mcp"),
    )
    await conn.commit()
    yield conn
    await conn.close()


async def collect_sse(gen) -> list[dict]:
    """Собирает все SSE-события из генератора в список {event, data}."""
    events = []
    async for raw in gen:
        lines = raw.strip().split("\n")
        event_name = ""
        data_str = ""
        for line in lines:
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data_str = line[6:]
        if event_name and data_str:
            events.append({"event": event_name, "data": json.loads(data_str)})
    return events


def make_request(message: str = "тест", channel_id: str = "test-ch", session_id=None) -> ChatRequest:
    return ChatRequest(message=message, channel_id=channel_id, session_id=session_id)


# ---------------------------------------------------------------------------
# 1. MAX_TOOL_ITERATIONS exit → code=tool_loop_limit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_max_iterations_exit(mem_db, monkeypatch):
    """LLM бесконечно возвращает tool_calls — loop останавливается после MAX_TOOL_ITERATIONS."""
    import app.orchestrator.loop as loop_module

    # Каждый вызов LLM возвращает один tool_call + finish_reason=tool_calls
    tool_chunks = [
        make_tool_call_chunk(0, "tc1", "execute_query", '{"query":"SELECT 1"}'),
        make_tool_calls_finish_chunk(),
    ]

    class InfiniteLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            return stub_llm_stream(*tool_chunks)

        async def aclose(self): pass

    # FakeMCPClient возвращает успешный результат на каждый вызов
    fake_mcp = FakeMCPClient(
        tool_map={"execute_query": {"content": [{"type": "text", "text": '{"rows":[]}'  }]}}
    )

    monkeypatch.setattr(loop_module, "LLMClient", InfiniteLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: fake_mcp)

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "tool_loop_limit"
    assert "10" in error_events[0]["data"]["message"]


# ---------------------------------------------------------------------------
# 2. init_error при ошибке save_user_message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_init_error_on_save_user_message_failure(mem_db, monkeypatch):
    """save_user_message бросает OperationalError → code=init_error."""
    import aiosqlite as aiosqlite_mod

    import app.orchestrator.loop as loop_module

    # Патчим в пространстве имён loop_module (где имя импортировано)
    async def failing_save(*a, **kw):
        raise aiosqlite_mod.OperationalError("DB locked")

    monkeypatch.setattr(loop_module, "save_user_message", failing_save)

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "init_error"


# ---------------------------------------------------------------------------
# 3. finish_reason="length" — loop завершает с done, без ошибки
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_finish_reason_length(mem_db, monkeypatch):
    """finish_reason='length' → loop завершает, эмитит done (не error)."""
    import app.orchestrator.loop as loop_module

    class LengthLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            return stub_llm_stream(
                make_text_chunk("Вот частичный ответ"),
                make_text_chunk("", finish_reason="length"),
            )

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", LengthLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    # Нет ошибки — только done
    error_events = [e for e in events if e["event"] == "error"]
    done_events = [e for e in events if e["event"] == "done"]
    assert len(error_events) == 0
    assert len(done_events) == 1


# ---------------------------------------------------------------------------
# 4. finish_reason="content_filter" — аналогично
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_finish_reason_content_filter(mem_db, monkeypatch):
    """finish_reason='content_filter' → loop завершает с done, без ошибки."""
    import app.orchestrator.loop as loop_module

    class ContentFilterLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            return stub_llm_stream(
                make_text_chunk("Частичный", finish_reason="content_filter"),
            )

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", ContentFilterLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    done_events = [e for e in events if e["event"] == "done"]
    assert len(error_events) == 0
    assert len(done_events) == 1


# ---------------------------------------------------------------------------
# 5. unknown_channel → error ДО попытки initialize MCP
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_unknown_channel_emits_error_before_mcp(mem_db, monkeypatch):
    """lookup_mcp_endpoint возвращает None → error code=unknown_channel, MCP.initialize() не вызывается."""
    import app.orchestrator.loop as loop_module

    initialize_called = []

    class SpyMCPClient:
        def __init__(self, *a, **kw): pass

        async def initialize(self):
            initialize_called.append(True)

        async def list_tools(self):
            return []

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: SpyMCPClient())

    # Используем несуществующий channel_id
    req = ChatRequest(message="тест", channel_id="nonexistent-channel")
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, req, "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "unknown_channel"
    # MCP initialize не должен был вызываться
    assert len(initialize_called) == 0


# ---------------------------------------------------------------------------
# 6. tool_args с непарсируемым JSON → empty dict, вызов продолжается
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_tool_args_unparseable_json_uses_empty_dict(mem_db, monkeypatch):
    """tool_call с arguments='{invalid json' → loop парсит как {} и вызывает MCP."""
    import app.orchestrator.loop as loop_module

    call_args_received = []

    class SpyMCPClient:
        def __init__(self, *a, **kw): pass

        async def initialize(self): pass

        async def list_tools(self):
            return [{"name": "execute_query", "description": "q", "inputSchema": {"type": "object", "properties": {}}}]

        async def call_tool(self, name: str, arguments: dict):
            call_args_received.append(arguments)
            return {"content": [{"type": "text", "text": "ok"}]}

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: SpyMCPClient())

    call_count = [0]

    class OneShotLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, messages, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                # Первый вызов — возвращаем tool_call с невалидным JSON
                return stub_llm_stream(
                    make_tool_call_chunk(0, "tc-bad", "execute_query", "{invalid json"),
                    make_tool_calls_finish_chunk(),
                )
            # Второй вызов — финальный текстовый ответ
            return stub_llm_stream(make_text_chunk("Готово", finish_reason="stop"))

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", OneShotLLM)

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    # MCP был вызван с пустым dict (не упал)
    assert len(call_args_received) >= 1
    assert call_args_received[0] == {}

    # Loop завершился успешно с done
    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) == 1


# ---------------------------------------------------------------------------
# 7. _cap_content обрезает при >50k символов
# ---------------------------------------------------------------------------

def test_cap_content_truncates_at_50k():
    """_cap_content обрезает строку >50k с суффиксом '...truncated'."""
    long_str = "A" * (TOOL_CONTENT_CAP + 100)
    result = _cap_content(long_str)
    assert result.endswith("...truncated")
    assert len(result) == TOOL_CONTENT_CAP + len("...truncated")


def test_cap_content_passthrough_short():
    """_cap_content возвращает строку без изменений если ≤50k."""
    short_str = "Hello world"
    assert _cap_content(short_str) == short_str
