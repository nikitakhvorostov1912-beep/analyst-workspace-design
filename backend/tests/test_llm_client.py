"""Тесты LLMClient — парсинг SSE из OpenAI-compat endpoint."""

import json

import httpx
import pytest

from app.clients.llm import LLMClient


def _make_sse_body(chunks: list[dict], done: bool = True) -> bytes:
    """Собирает байтовый SSE-поток из списка dict-чанков."""
    lines = []
    for chunk in chunks:
        lines.append(f"data: {json.dumps(chunk)}\n\n")
    if done:
        lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


@pytest.mark.asyncio
async def test_stream_chat_completion_parses_content_chunks():
    """LLMClient корректно парсит content-чанки и yields choices[0]."""
    chunk_data = {"choices": [{"delta": {"content": "Hello"}}]}
    body = _make_sse_body([chunk_data, chunk_data, chunk_data])

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
    )
    client = LLMClient(endpoint="http://mock", model="test", timeout=5.0)
    # Заменяем http-клиент на mock, сохраняя base_url
    client._http = httpx.AsyncClient(transport=transport, base_url="http://mock", timeout=5.0)

    results = []
    async for chunk in client.stream_chat_completion(
        messages=[{"role": "user", "content": "hi"}],
        api_key="test-key",
    ):
        results.append(chunk)

    await client.aclose()

    assert len(results) == 3
    for r in results:
        assert r["delta"]["content"] == "Hello"


@pytest.mark.asyncio
async def test_stream_chat_completion_handles_tool_calls():
    """LLMClient сохраняет tool_calls в yielded chunk."""
    tool_call_delta = {
        "index": 0,
        "function": {"name": "foo", "arguments": '{"a":1}'},
    }
    chunk_data = {"choices": [{"delta": {"tool_calls": [tool_call_delta]}}]}
    body = _make_sse_body([chunk_data])

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
    )
    client = LLMClient(endpoint="http://mock", model="test", timeout=5.0)
    client._http = httpx.AsyncClient(transport=transport, base_url="http://mock", timeout=5.0)

    results = []
    async for chunk in client.stream_chat_completion(
        messages=[{"role": "user", "content": "call tool"}],
        api_key="test-key",
    ):
        results.append(chunk)

    await client.aclose()

    assert len(results) == 1
    tool_calls = results[0]["delta"]["tool_calls"]
    assert tool_calls[0]["function"]["name"] == "foo"
    assert tool_calls[0]["function"]["arguments"] == '{"a":1}'


@pytest.mark.asyncio
async def test_api_key_not_leaked_in_repr():
    """LLMClient не содержит api_key в repr (T-01-01)."""
    client = LLMClient(endpoint="http://mock", model="test")
    assert "secret-key" not in repr(client)
    assert "secret-key" not in str(client)
    await client.aclose()
