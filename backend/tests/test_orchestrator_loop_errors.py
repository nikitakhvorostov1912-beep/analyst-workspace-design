"""Тесты маппинга ошибок LLM/MCP в SSE-коды (Plan 03-01, Task 1 RED)."""

import json

import aiosqlite
import httpx
import pytest

from app.models import ChatRequest

from .fixtures.mcp_responses import FakeMCPClient, make_text_chunk, stub_llm_stream


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
    """Собирает все SSE-события из генератора."""
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


def make_request(message: str = "тест", channel_id: str = "test-ch") -> ChatRequest:
    return ChatRequest(message=message, channel_id=channel_id)


def make_http_status_error(status_code: int, headers: dict | None = None) -> httpx.HTTPStatusError:
    """Создаёт httpx.HTTPStatusError с заданным статусом."""
    request = httpx.Request("POST", "http://fake-llm/chat/completions")
    response = httpx.Response(status_code, headers=headers or {}, request=request)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


# --- LLM error mapping tests ---

@pytest.mark.asyncio
async def test_loop_maps_429_to_llm_rate_limit_with_retry_after(mem_db, monkeypatch):
    """LLM 429 + Retry-After: 45 → event error code=llm_rate_limit retry_after_s=45."""
    import app.orchestrator.loop as loop_module
    from app.clients.llm import LLMRateLimitError

    exc = make_http_status_error(429, {"retry-after": "45"})
    rate_limit_exc = LLMRateLimitError(
        "429 rate limit",
        request=exc.request,
        response=exc.response,
    )
    rate_limit_exc.retry_after_s = 45

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            raise rate_limit_exc

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "llm_rate_limit"
    assert error_events[0]["data"]["retry_after_s"] == 45


@pytest.mark.asyncio
async def test_loop_maps_429_without_retry_after_to_null(mem_db, monkeypatch):
    """LLM 429 без заголовка Retry-After → retry_after_s=null."""
    import app.orchestrator.loop as loop_module
    from app.clients.llm import LLMRateLimitError

    exc = make_http_status_error(429)
    rate_limit_exc = LLMRateLimitError(
        "429 rate limit",
        request=exc.request,
        response=exc.response,
    )
    rate_limit_exc.retry_after_s = None

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            raise rate_limit_exc

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "llm_rate_limit"
    assert error_events[0]["data"]["retry_after_s"] is None


@pytest.mark.asyncio
async def test_loop_maps_401_to_llm_invalid_key(mem_db, monkeypatch):
    """LLM 401 → code llm_invalid_key, message содержит 'Неверный API-ключ'."""
    import app.orchestrator.loop as loop_module

    exc = make_http_status_error(401)

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            raise exc

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "llm_invalid_key"
    assert "Неверный API-ключ" in error_events[0]["data"]["message"]


@pytest.mark.asyncio
async def test_loop_maps_403_to_llm_invalid_key(mem_db, monkeypatch):
    """LLM 403 → code llm_invalid_key."""
    import app.orchestrator.loop as loop_module

    exc = make_http_status_error(403)

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            raise exc

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "llm_invalid_key"


@pytest.mark.asyncio
async def test_loop_maps_5xx_to_llm_server_error(mem_db, monkeypatch):
    """LLM 502 → code llm_server_error."""
    import app.orchestrator.loop as loop_module

    exc = make_http_status_error(502)

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            raise exc

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "llm_server_error"


@pytest.mark.asyncio
async def test_loop_maps_request_error_to_llm_network_error(mem_db, monkeypatch):
    """httpx.ConnectError → code llm_network_error."""
    import app.orchestrator.loop as loop_module

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            raise httpx.ConnectError("connection refused")

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "llm_network_error"


# --- MCP error mapping tests ---

@pytest.mark.asyncio
async def test_loop_maps_mcp_initialize_failure_to_mcp_disconnected(mem_db, monkeypatch):
    """MCP initialize() бросает ConnectError → code mcp_disconnected."""
    import app.orchestrator.loop as loop_module

    class BrokenMCPClient:
        def __init__(self, *a, **kw): pass

        async def initialize(self):
            raise httpx.ConnectError("connection refused")

        async def list_tools(self):
            return []

        async def call_tool(self, *a, **kw):
            return {}

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: BrokenMCPClient())

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            return stub_llm_stream(make_text_chunk("ok", finish_reason="stop"))

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "mcp_disconnected"
    assert "Не удалось подключиться" in error_events[0]["data"]["message"]


@pytest.mark.asyncio
async def test_loop_maps_mcp_call_tool_disconnected_to_mcp_disconnected(mem_db, monkeypatch):
    """MCP.call_tool бросает ConnectError → code mcp_disconnected (не mcp_connect_error)."""
    import app.orchestrator.loop as loop_module

    class DisconnectingMCPClient:
        def __init__(self, *a, **kw): pass

        async def initialize(self): pass

        async def list_tools(self):
            return [{"name": "execute_query", "description": "q", "inputSchema": {"type": "object", "properties": {}}}]

        async def call_tool(self, name: str, arguments: dict):
            raise httpx.ConnectError("lost connection")

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: DisconnectingMCPClient())

    # LLM всегда просит execute_query
    from tests.fixtures.mcp_responses import make_tool_call_chunk, make_tool_calls_finish_chunk
    tool_chunks = [
        make_tool_call_chunk(0, "tc1", "execute_query", '{"query":"SELECT 1"}'),
        make_tool_calls_finish_chunk(),
    ]

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            return stub_llm_stream(*tool_chunks)

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "mcp_disconnected"


@pytest.mark.asyncio
async def test_loop_no_traceback_in_error_message(mem_db, monkeypatch):
    """ErrorEvent.message никогда не содержит Python traceback."""
    import app.orchestrator.loop as loop_module

    class BrokenLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            tb = (
                "Some internal Python error\n"
                "File 'backend/app/orchestrator/loop.py', line 200\n"
                "Traceback (most recent call last):\n  ..."
            )
            raise RuntimeError(tb)

        async def aclose(self): pass

    monkeypatch.setattr(loop_module, "LLMClient", BrokenLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, make_request(), "sk-test", "http://fake-llm/v1", "test-model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) >= 1

    for ev in error_events:
        msg = ev["data"]["message"]
        assert "Traceback (most recent call last)" not in msg
        assert "backend.app." not in msg
        assert len(msg) <= 200


# --- LLMRateLimitError class test ---

def test_llm_rate_limit_error_class_carries_retry_after():
    """LLMRateLimitError имеет атрибут retry_after_s."""
    from app.clients.llm import LLMRateLimitError

    request = httpx.Request("POST", "http://fake/chat")
    response = httpx.Response(429, headers={"retry-after": "60"}, request=request)
    exc = LLMRateLimitError("rate limited", request=request, response=response)
    exc.retry_after_s = 60

    assert exc.retry_after_s == 60
    assert isinstance(exc, httpx.HTTPStatusError)
