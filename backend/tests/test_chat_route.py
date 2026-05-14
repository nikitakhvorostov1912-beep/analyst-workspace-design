"""Тесты POST /chat — SSE контракт."""

import json
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient


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


@pytest.mark.asyncio
async def test_chat_missing_api_key_returns_400(client: AsyncClient):
    """POST /chat без X-LLM-API-Key → 400."""
    response = await client.post(
        "/chat",
        json={"message": "hello"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_chat_returns_sse_with_status_and_delta(client: AsyncClient, monkeypatch):
    """POST /chat возвращает SSE поток с events: status, delta, done."""
    # Подменяем LLMClient через monkeypatch на стаб

    async def _stub_stream(*_args, **_kwargs) -> AsyncIterator[dict]:
        yield {"delta": {"content": "Привет"}}
        yield {"delta": {"content": "!"}}

    import app.routes.chat as chat_module

    class StubLLMClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def stream_chat_completion(self, *_args, **_kwargs):
            return _stub_stream()

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(chat_module, "LLMClient", StubLLMClient)

    response = await client.post(
        "/chat",
        json={"message": "hello"},
        headers={"X-LLM-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(response.text)
    event_names = [e["event"] for e in events]

    assert "status" in event_names, f"status не найден в {event_names}"
    assert "delta" in event_names, f"delta не найден в {event_names}"
    assert "done" in event_names, f"done не найден в {event_names}"

    # Проверяем что status идёт первым
    assert event_names[0] == "status"
    assert events[0]["data"]["stage"] == "thinking"


@pytest.mark.asyncio
async def test_chat_first_event_is_status(client: AsyncClient, monkeypatch):
    """Первый SSE-event должен быть status (NFR-1: first byte ≤ 500ms)."""
    import app.routes.chat as chat_module

    async def _empty_stream(*_a, **_kw) -> AsyncIterator[dict]:
        return
        yield  # делает генератором

    class StubLLMClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def stream_chat_completion(self, *_a, **_kw):
            return _empty_stream()

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(chat_module, "LLMClient", StubLLMClient)

    response = await client.post(
        "/chat",
        json={"message": "test"},
        headers={"X-LLM-API-Key": "test-key"},
    )
    events = _parse_sse_events(response.text)
    assert events[0]["event"] == "status"
    assert events[-1]["event"] == "done"
