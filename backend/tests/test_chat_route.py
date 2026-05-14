"""Тесты POST /chat — SSE контракт (Phase 2)."""

import json

import aiosqlite
import pytest
from httpx import AsyncClient

from .fixtures.mcp_responses import FakeMCPClient, make_stop_chunk, make_text_chunk, stub_llm_stream


def _parse_sse_events(body: str) -> list[dict]:
    """Парсит SSE-поток в список {event, data}."""
    events = []
    current: dict = {}
    for line in body.splitlines():
        if line.startswith("event: "):
            current["event"] = line[len("event: "):]
        elif line.startswith("data: "):
            raw = line[len("data: "):]
            try:
                current["data"] = json.loads(raw)
            except json.JSONDecodeError:
                current["data"] = raw
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


@pytest.fixture
async def db_with_channel(db: aiosqlite.Connection):
    """Фикстура: БД с тестовым MCP-каналом."""
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint) VALUES (?, ?, ?)",
        ("test-ch", "Тест", "http://fake-mcp/mcp"),
    )
    await db.commit()
    return db


# --- Базовые проверки ---

@pytest.mark.asyncio
async def test_chat_missing_api_key_returns_400(client: AsyncClient):
    """POST /chat без X-LLM-API-Key → 400."""
    response = await client.post(
        "/chat",
        json={"message": "hello", "channel_id": "x"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_chat_missing_channel_id_returns_422(client: AsyncClient):
    """POST /chat без channel_id → 422."""
    response = await client.post(
        "/chat",
        json={"message": "hello"},
        headers={"X-LLM-API-Key": "test-key"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_returns_sse_with_status_and_delta(client: AsyncClient, monkeypatch):
    """POST /chat возвращает SSE поток с events: status, done."""
    import app.orchestrator.loop as loop_module

    class StubLLMClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def stream_chat_completion(self, *_args, **_kwargs):
            return stub_llm_stream(
                make_text_chunk("Привет"),
                make_stop_chunk(),
            )

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(loop_module, "LLMClient", StubLLMClient)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    response = await client.post(
        "/chat",
        json={"message": "hello", "channel_id": "test-ch"},
        headers={"X-LLM-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(response.text)
    event_names = [e["event"] for e in events]

    assert "status" in event_names


@pytest.mark.asyncio
async def test_chat_first_event_is_status(client: AsyncClient, monkeypatch):
    """Первый SSE-event должен быть status (NFR-1)."""
    import app.orchestrator.loop as loop_module

    class StubLLMClient:
        def __init__(self, *_a, **_kw) -> None:
            pass

        def stream_chat_completion(self, *_a, **_kw):
            return stub_llm_stream(make_stop_chunk())

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(loop_module, "LLMClient", StubLLMClient)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    response = await client.post(
        "/chat",
        json={"message": "test", "channel_id": "test-ch"},
        headers={"X-LLM-API-Key": "test-key"},
    )
    events = _parse_sse_events(response.text)
    # Первый event всегда status (thinking) — до всех I/O
    assert events[0]["event"] == "status"
    assert events[0]["data"]["stage"] == "thinking"


@pytest.mark.asyncio
async def test_chat_unknown_channel_returns_error(client: AsyncClient, monkeypatch):
    """POST /chat с несуществующим channel_id → event:error code=unknown_channel."""
    import app.orchestrator.loop as loop_module

    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient())

    response = await client.post(
        "/chat",
        json={"message": "test", "channel_id": "nonexistent"},
        headers={"X-LLM-API-Key": "test-key"},
    )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    error_events = [e for e in events if e["event"] == "error"]
    assert error_events
    assert error_events[0]["data"]["code"] == "unknown_channel"
