"""Тесты confirm_required branch в orchestrator/loop.py (Plan 3.2 SEC-01)."""

import asyncio
import json

import aiosqlite
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
    """In-memory SQLite с миграциями и тестовым MCP-каналом."""
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


@pytest.fixture(autouse=True)
def clear_pending():
    """Очищаем _pending dict между тестами."""
    import app.orchestrator.safety as safety_mod

    safety_mod._pending.clear()
    yield
    safety_mod._pending.clear()


async def collect_sse(gen) -> list[dict]:
    """Собирает все SSE-события из async-генератора."""
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


@pytest.mark.asyncio
async def test_loop_emits_confirm_required_on_dangerous_execute_code(mem_db, monkeypatch):
    """LLM выдаёт execute_code с dangerous keyword → confirm_required эмитится; declined → error user_declined; MCP НЕ вызывается."""
    import app.orchestrator.loop as loop_module
    import app.orchestrator.safety as safety_mod

    class FakeLLM:
        def __init__(self, *a, **kw):
            pass

        def stream_chat_completion(self, *a, **kw):
            return stub_llm_stream(
                make_tool_call_chunk(
                    0, "call-danger-1", "execute_code",
                    '{"code":"Контрагент.Удалить()"}',
                ),
                make_tool_calls_finish_chunk(),
            )

        async def aclose(self):
            pass

    call_tool_called = [False]

    class TrackingMCPClient(FakeMCPClient):
        async def call_tool(self, name: str, arguments: dict):
            call_tool_called[0] = True
            return await super().call_tool(name, arguments)

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: TrackingMCPClient("http://fake"))
    # Уменьшаем timeout для теста
    monkeypatch.setattr(loop_module, "CONFIRMATION_TIMEOUT_S", 5.0)

    # Запускаем loop в фоне; после emit confirm_required — resolve False
    async def _run_loop():
        return await collect_sse(
            loop_module.run_chat_loop(mem_db, make_request(), "api-key", "http://llm", "model")
        )

    # Запускаем в task и параллельно ждём появления pending confirmation
    loop_task = asyncio.create_task(_run_loop())

    # Небольшая задержка чтобы loop успел зарегистрировать pending confirmation
    await asyncio.sleep(0.05)

    # Резолвим pending confirmation как declined
    resolved = False
    for _attempt in range(20):
        if safety_mod._pending:
            tool_call_id = next(iter(safety_mod._pending))
            safety_mod.resolve_pending_confirmation(tool_call_id, False)
            resolved = True
            break
        await asyncio.sleep(0.05)

    events = await loop_task

    assert resolved, "Pending confirmation не появилась в safety._pending"

    event_names = [e["event"] for e in events]
    assert "confirm_required" in event_names, f"confirm_required не найден в {event_names}"

    error_events = [e for e in events if e["event"] == "error"]
    assert any(e["data"]["code"] == "user_declined" for e in error_events), \
        f"user_declined не найден в error events: {error_events}"

    assert not call_tool_called[0], "MCP call_tool не должен был вызываться при declined"


@pytest.mark.asyncio
async def test_loop_approved_continues(mem_db, monkeypatch):
    """Approved → MCP вызывается, tool_result есть, loop завершается done."""
    import app.orchestrator.loop as loop_module
    import app.orchestrator.safety as safety_mod

    call_count = [0]

    class FakeLLM:
        def __init__(self, *a, **kw):
            pass

        def stream_chat_completion(self, messages, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return stub_llm_stream(
                    make_tool_call_chunk(
                        0, "call-approve-1", "execute_code",
                        '{"code":"Контрагент.Удалить()"}',
                    ),
                    make_tool_calls_finish_chunk(),
                )
            else:
                return stub_llm_stream(
                    make_text_chunk("Выполнено"),
                    make_stop_chunk(),
                )

        async def aclose(self):
            pass

    fake_mcp = FakeMCPClient(
        tool_map={"execute_code": {"result": "ok"}},
        tools=[{"name": "execute_code", "description": "BSL", "inputSchema": {"type": "object", "properties": {}}}],
    )
    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: fake_mcp)
    monkeypatch.setattr(loop_module, "CONFIRMATION_TIMEOUT_S", 5.0)

    async def _run_loop():
        return await collect_sse(
            loop_module.run_chat_loop(mem_db, make_request(), "api-key", "http://llm", "model")
        )

    loop_task = asyncio.create_task(_run_loop())

    # Ждём появления pending и резолвим approved=True
    await asyncio.sleep(0.05)

    resolved = False
    for _attempt in range(20):
        if safety_mod._pending:
            tool_call_id = next(iter(safety_mod._pending))
            safety_mod.resolve_pending_confirmation(tool_call_id, True)
            resolved = True
            break
        await asyncio.sleep(0.05)

    events = await loop_task

    assert resolved, "Pending confirmation не появилась"

    event_names = [e["event"] for e in events]
    assert "confirm_required" in event_names
    assert "tool_result" in event_names, f"tool_result не найден в {event_names}"
    assert "done" in event_names, f"done не найден в {event_names}"
    assert fake_mcp._call_count.get("execute_code", 0) >= 1, "execute_code должен был вызваться"


@pytest.mark.asyncio
async def test_loop_safe_execute_code_no_confirm(mem_db, monkeypatch):
    """execute_code без dangerous keyword → confirm_required НЕ эмитится, MCP сразу вызывается."""
    import app.orchestrator.loop as loop_module

    call_count = [0]

    class FakeLLM:
        def __init__(self, *a, **kw):
            pass

        def stream_chat_completion(self, messages, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return stub_llm_stream(
                    make_tool_call_chunk(
                        0, "call-safe-1", "execute_code",
                        '{"code":"СообщитьПользователю(\'hi\')"}',
                    ),
                    make_tool_calls_finish_chunk(),
                )
            else:
                return stub_llm_stream(
                    make_text_chunk("Сделано"),
                    make_stop_chunk(),
                )

        async def aclose(self):
            pass

    fake_mcp = FakeMCPClient(
        tool_map={"execute_code": {"result": "hi"}},
        tools=[{"name": "execute_code", "description": "BSL", "inputSchema": {"type": "object", "properties": {}}}],
    )
    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: fake_mcp)

    events = await collect_sse(
        loop_module.run_chat_loop(mem_db, make_request(), "api-key", "http://llm", "model")
    )

    event_names = [e["event"] for e in events]
    assert "confirm_required" not in event_names, f"confirm_required не должен быть: {event_names}"
    assert "tool_result" in event_names
    assert "done" in event_names
    assert fake_mcp._call_count.get("execute_code", 0) >= 1


@pytest.mark.asyncio
async def test_loop_confirm_timeout_emits_error(mem_db, monkeypatch):
    """timeout → event:error code=dangerous_keyword_blocked."""
    import app.orchestrator.loop as loop_module

    class FakeLLM:
        def __init__(self, *a, **kw):
            pass

        def stream_chat_completion(self, *a, **kw):
            return stub_llm_stream(
                make_tool_call_chunk(
                    0, "call-timeout-1", "execute_code",
                    '{"code":"Контрагент.Удалить()"}',
                ),
                make_tool_calls_finish_chunk(),
            )

        async def aclose(self):
            pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient("http://fake"))
    # Мгновенный timeout
    monkeypatch.setattr(loop_module, "CONFIRMATION_TIMEOUT_S", 0.05)

    events = await collect_sse(
        loop_module.run_chat_loop(mem_db, make_request(), "api-key", "http://llm", "model")
    )

    event_names = [e["event"] for e in events]
    assert "confirm_required" in event_names
    error_events = [e for e in events if e["event"] == "error"]
    assert any(e["data"]["code"] == "dangerous_keyword_blocked" for e in error_events), \
        f"dangerous_keyword_blocked не найден: {error_events}"
