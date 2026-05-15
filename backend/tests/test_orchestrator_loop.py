"""Тесты tool-calling loop (loop.py)."""

import json

import aiosqlite
import httpx
import pytest

from app.models import ChatRequest

from .fixtures.mcp_responses import (
    FakeMCPClient,
    make_stop_chunk,
    make_text_chunk,
    make_tool_call_chunk,
    make_tool_calls_finish_chunk,
    stub_llm_stream,
)


@pytest.fixture
async def mem_db():
    """In-memory SQLite с миграциями."""

    from app.storage.migrations import apply_migrations

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)

    # Добавляем тестовый MCP-канал
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


# --- Тест 1: Нет tool_calls, LLM сразу возвращает текст ---

@pytest.mark.asyncio
async def test_loop_no_tools(mem_db, monkeypatch):
    """LLM возвращает stop, без tool calls. Expected: status→delta→done."""
    import app.orchestrator.loop as loop_module

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            return stub_llm_stream(
                make_text_chunk("Привет"),
                make_text_chunk("!", finish_reason="stop"),
            )

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient("http://fake"))

    request = make_request("Привет")
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, request, "api-key", "http://llm", "model"
    ))

    event_names = [e["event"] for e in events]
    assert "status" in event_names
    assert "delta" in event_names
    assert "done" in event_names
    assert "error" not in event_names
    assert "tool_call" not in event_names

    # Проверяем персистенцию
    rows = await mem_db.execute_fetchall(
        "SELECT role FROM messages ORDER BY created_at"
    )
    roles = [r[0] for r in rows]
    assert "user" in roles
    assert "assistant" in roles


# --- Тест 2: Один tool_call ---

@pytest.mark.asyncio
async def test_loop_one_tool_call(mem_db, monkeypatch):
    """LLM → tool_call execute_query → stop с текстом. Expected: status→tool_call→tool_result→card→status→delta→done."""
    import app.orchestrator.loop as loop_module

    call_count = [0]

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, messages, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                # Первый вызов — tool_call
                return stub_llm_stream(
                    make_tool_call_chunk(0, "tc1", "execute_query", '{"query":"SELECT 1"}'),
                    make_tool_calls_finish_chunk(),
                )
            else:
                # Второй вызов — финальный ответ
                return stub_llm_stream(
                    make_text_chunk("Вот результаты"),
                    make_stop_chunk(),
                )

        async def aclose(self): pass

    # 2 строки → TableCard (одиночная numeric строка после 04-02 трактуется как MetricCard).
    fake_mcp = FakeMCPClient(
        tool_map={
            "execute_query": {
                "columns": [
                    {"name": "Контрагент", "type": "String"},
                    {"name": "Сумма", "type": "Number"},
                ],
                "rows": [["Альфа", 100], ["Бета", 200]],
            }
        }
    )
    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: fake_mcp)

    request = make_request()
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, request, "api-key", "http://llm", "model"
    ))

    event_names = [e["event"] for e in events]
    assert "tool_call" in event_names
    assert "tool_result" in event_names
    assert "card" in event_names
    assert "done" in event_names
    assert "error" not in event_names

    # Проверяем card type
    card_events = [e for e in events if e["event"] == "card"]
    assert len(card_events) == 1
    assert card_events[0]["data"]["type"] == "table"

    # Проверяем персистенцию tool_calls
    rows = await mem_db.execute_fetchall(
        "SELECT tool_calls FROM messages WHERE role = 'assistant'"
    )
    assert rows
    tool_calls = json.loads(rows[0][0])
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "execute_query"


# --- Тест 3: Два последовательных tool_call ---

@pytest.mark.asyncio
async def test_loop_two_sequential_tools(mem_db, monkeypatch):
    """LLM сначала get_metadata, потом execute_query, потом stop."""
    import app.orchestrator.loop as loop_module

    call_count = [0]

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return stub_llm_stream(
                    make_tool_call_chunk(0, "tc1", "get_metadata", "{}"),
                    make_tool_calls_finish_chunk(),
                )
            elif call_count[0] == 2:
                return stub_llm_stream(
                    make_tool_call_chunk(0, "tc2", "execute_query", '{"query":"SELECT 1"}'),
                    make_tool_calls_finish_chunk(),
                )
            else:
                return stub_llm_stream(make_text_chunk("Готово"), make_stop_chunk())

        async def aclose(self): pass

    fake_mcp = FakeMCPClient(
        tool_map={
            "get_metadata": {"summary": {"catalogs": 10}},
            "execute_query": {"columns": [], "rows": []},
        }
    )
    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: fake_mcp)

    request = make_request()
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, request, "api-key", "http://llm", "model"
    ))

    tool_calls = [e for e in events if e["event"] == "tool_call"]
    assert len(tool_calls) == 2
    assert tool_calls[0]["data"]["name"] == "get_metadata"
    assert tool_calls[1]["data"]["name"] == "execute_query"

    tool_results = [e for e in events if e["event"] == "tool_result"]
    assert len(tool_results) == 2
    assert "done" in [e["event"] for e in events]


# --- Тест 4: Лимит итераций ---

@pytest.mark.asyncio
async def test_loop_tool_loop_limit(mem_db, monkeypatch):
    """LLM всегда возвращает tool_call. После 10 итераций → error code=tool_loop_limit."""
    import app.orchestrator.loop as loop_module

    counter = [0]

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            counter[0] += 1
            return stub_llm_stream(
                make_tool_call_chunk(0, f"tc{counter[0]}", "execute_query", "{}"),
                make_tool_calls_finish_chunk(),
            )

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient(
        tool_map={"execute_query": {"columns": [], "rows": []}}
    ))

    request = make_request()
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, request, "api-key", "http://llm", "model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert error_events, "Должно быть event:error"
    assert error_events[-1]["data"]["code"] == "tool_loop_limit"


# --- Тест 5: MCPError ---

@pytest.mark.asyncio
async def test_loop_mcp_error(mem_db, monkeypatch):
    """MCPClient.call_tool raises MCPError → tool_result ok=False, loop продолжается."""
    import app.orchestrator.loop as loop_module
    from app.clients.mcp import MCPError

    call_count = [0]

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return stub_llm_stream(
                    make_tool_call_chunk(0, "tc1", "execute_query", "{}"),
                    make_tool_calls_finish_chunk(),
                )
            else:
                return stub_llm_stream(make_text_chunk("Ошибка получена"), make_stop_chunk())

        async def aclose(self): pass

    fake_mcp = FakeMCPClient(
        tool_map={"execute_query": MCPError(-32601, "Method not found")}
    )
    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: fake_mcp)

    request = make_request()
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, request, "api-key", "http://llm", "model"
    ))

    tool_result_events = [e for e in events if e["event"] == "tool_result"]
    assert tool_result_events
    assert tool_result_events[0]["data"]["ok"] is False
    assert "MCP error" in tool_result_events[0]["data"]["error"]

    # Loop должен продолжиться до done
    assert "done" in [e["event"] for e in events]


# --- Тест 6: Unknown channel ---

@pytest.mark.asyncio
async def test_loop_unknown_channel(mem_db, monkeypatch):
    """channel_id не существует → event:error code=unknown_channel."""
    import app.orchestrator.loop as loop_module

    monkeypatch.setattr(loop_module, "LLMClient", lambda *a, **kw: None)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    request = make_request(channel_id="nonexistent-channel")
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, request, "api-key", "http://llm", "model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert error_events
    assert error_events[0]["data"]["code"] == "unknown_channel"


# --- Тест 7: Network retry ---

@pytest.mark.asyncio
async def test_loop_network_retry(mem_db, monkeypatch):
    """Первый call_tool бросает ConnectError, второй — успешен. tool_result ok=True."""
    import app.orchestrator.loop as loop_module

    call_count = [0]

    class RetryMCPClient:
        def __init__(self, *a, **kw): pass

        async def initialize(self): pass

        async def list_tools(self):
            return [{"name": "execute_query", "description": "", "inputSchema": {"type": "object", "properties": {}}}]

        async def call_tool(self, name, arguments):
            call_count[0] += 1
            if call_count[0] == 1:
                raise httpx.ConnectError("connection refused")
            return {"columns": [], "rows": []}

        async def aclose(self): pass
        async def close(self): pass

    llm_call = [0]

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            llm_call[0] += 1
            if llm_call[0] == 1:
                return stub_llm_stream(
                    make_tool_call_chunk(0, "tc1", "execute_query", "{}"),
                    make_tool_calls_finish_chunk(),
                )
            return stub_llm_stream(make_text_chunk("Ok"), make_stop_chunk())

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: RetryMCPClient())

    request = make_request()
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, request, "api-key", "http://llm", "model"
    ))

    tool_results = [e for e in events if e["event"] == "tool_result"]
    assert tool_results
    assert tool_results[0]["data"]["ok"] is True
    assert call_count[0] == 2  # был retry


# --- Тест 8: Накопление arguments из chunks ---

@pytest.mark.asyncio
async def test_loop_tool_args_accumulate_across_chunks(mem_db, monkeypatch):
    """arguments приходят по частям: '{"q' + 'uery":' + '"SELECT 1"}' → {query:'SELECT 1'}."""
    import app.orchestrator.loop as loop_module

    async def _stream_with_partial_args():
        # Первый chunk — id и начало arguments
        yield {
            "delta": {"tool_calls": [
                {"index": 0, "id": "tc1", "function": {"name": "execute_query", "arguments": '{"q'}},
            ]},
            "finish_reason": None,
        }
        # Второй chunk — продолжение arguments
        yield {
            "delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'uery":"'}}]},
            "finish_reason": None,
        }
        # Третий chunk — конец arguments
        yield {
            "delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'SELECT 1"}'}}]},
            "finish_reason": "tool_calls",
        }

    captured_args = []

    class FakeMCPCapture:
        def __init__(self, *a, **kw): pass

        async def initialize(self): pass

        async def list_tools(self):
            return [{"name": "execute_query", "description": "", "inputSchema": {"type": "object", "properties": {}}}]

        async def call_tool(self, name, arguments):
            captured_args.append(arguments)
            return {"columns": [], "rows": []}

        async def aclose(self): pass
        async def close(self): pass

    llm_call = [0]

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            llm_call[0] += 1
            if llm_call[0] == 1:
                return _stream_with_partial_args()
            return stub_llm_stream(make_text_chunk("Ok"), make_stop_chunk())

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPCapture())

    request = make_request()
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, request, "api-key", "http://llm", "model"
    ))

    tool_call_events = [e for e in events if e["event"] == "tool_call"]
    assert tool_call_events
    assert tool_call_events[0]["data"]["args"] == {"query": "SELECT 1"}
