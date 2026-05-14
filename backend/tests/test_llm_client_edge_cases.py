"""LLM-клиент edge cases — finish_reason length/content_filter, malformed chunk, multi-chunk tool_calls."""

import json

import httpx
import pytest

from app.clients.llm import LLMClient, _parse_retry_after


def _make_sse_body(chunks: list[dict], done: bool = True) -> bytes:
    """Собирает байтовый SSE-поток из списка dict-чанков."""
    lines = []
    for chunk in chunks:
        lines.append(f"data: {json.dumps(chunk)}\n\n")
    if done:
        lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def _make_transport(body: bytes, status: int = 200) -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda req: httpx.Response(status, content=body, headers={"content-type": "text/event-stream"})
    )


# ---------------------------------------------------------------------------
# 1. finish_reason="length" yielded в chunk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_finish_reason_length_yielded():
    """finish_reason='length' присутствует в последнем yielded chunk."""
    chunk_data = {"choices": [{"delta": {"content": "Ответ"}, "finish_reason": "length"}]}
    body = _make_sse_body([chunk_data])

    client = LLMClient(endpoint="http://mock", model="test", timeout=5.0)
    client._http = httpx.AsyncClient(transport=_make_transport(body), base_url="http://mock", timeout=5.0)

    results = []
    async for chunk in client.stream_chat_completion(
        messages=[{"role": "user", "content": "hi"}],
        api_key="test-key",
    ):
        results.append(chunk)

    await client.aclose()

    assert len(results) >= 1
    finish_reasons = [r.get("finish_reason") for r in results]
    assert "length" in finish_reasons


# ---------------------------------------------------------------------------
# 2. finish_reason="content_filter"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_finish_reason_content_filter():
    """finish_reason='content_filter' присутствует в yielded chunk."""
    chunk_data = {"choices": [{"delta": {"content": ""}, "finish_reason": "content_filter"}]}
    body = _make_sse_body([chunk_data])

    client = LLMClient(endpoint="http://mock", model="test", timeout=5.0)
    client._http = httpx.AsyncClient(transport=_make_transport(body), base_url="http://mock", timeout=5.0)

    results = []
    async for chunk in client.stream_chat_completion(
        messages=[{"role": "user", "content": "sensitive"}],
        api_key="test-key",
    ):
        results.append(chunk)

    await client.aclose()

    finish_reasons = [r.get("finish_reason") for r in results]
    assert "content_filter" in finish_reasons


# ---------------------------------------------------------------------------
# 3. Multi-chunk tool_calls — клиент yields каждый chunk без аккумуляции
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_multi_chunk_tool_calls_yielded_separately():
    """3 чанка с tool_calls — каждый yielded отдельно (loop сам аккумулирует)."""
    tc0_start = {"index": 0, "function": {"name": "fn", "arguments": '{"qu'}}
    tc0_mid = {"index": 0, "function": {"arguments": 'ery":'}}
    tc0_end = {"index": 0, "function": {"arguments": '"SELECT 1"}'}}
    chunks = [
        {"choices": [{"delta": {"tool_calls": [tc0_start]}}]},
        {"choices": [{"delta": {"tool_calls": [tc0_mid]}}]},
        {"choices": [{"delta": {"tool_calls": [tc0_end]}, "finish_reason": "tool_calls"}]},
    ]
    body = _make_sse_body(chunks)

    client = LLMClient(endpoint="http://mock", model="test", timeout=5.0)
    client._http = httpx.AsyncClient(transport=_make_transport(body), base_url="http://mock", timeout=5.0)

    results = []
    async for chunk in client.stream_chat_completion(
        messages=[{"role": "user", "content": "query"}],
        api_key="test-key",
    ):
        results.append(chunk)

    await client.aclose()

    # Все 3 чанка yielded
    assert len(results) == 3
    # Первый чанк содержит начало arguments
    first_args = results[0]["delta"]["tool_calls"][0]["function"]["arguments"]
    assert first_args == '{"qu'


# ---------------------------------------------------------------------------
# 4. Malformed chunk пропускается, следующий валидный yields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_malformed_chunk_skipped():
    """Один чанк 'data: not_json', следующий валидный → клиент пропускает первый, yields второй."""
    valid_chunk = {"choices": [{"delta": {"content": "Привет"}}]}
    bad_line = "data: not_valid_json\n\n"
    good_line = f"data: {json.dumps(valid_chunk)}\n\n"
    done_line = "data: [DONE]\n\n"
    body = (bad_line + good_line + done_line).encode()

    client = LLMClient(endpoint="http://mock", model="test", timeout=5.0)
    client._http = httpx.AsyncClient(transport=_make_transport(body), base_url="http://mock", timeout=5.0)

    results = []
    async for chunk in client.stream_chat_completion(
        messages=[{"role": "user", "content": "hi"}],
        api_key="test-key",
    ):
        results.append(chunk)

    await client.aclose()

    # Только валидный chunk yielded
    assert len(results) == 1
    assert results[0]["delta"]["content"] == "Привет"


# ---------------------------------------------------------------------------
# 5. [DONE] маркер останавливает итерацию
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_done_marker_stops_iteration():
    """'data: [DONE]' завершает async-итерацию; последующие чанки не обрабатываются."""
    chunk_before = {"choices": [{"delta": {"content": "before"}}]}
    chunk_after = {"choices": [{"delta": {"content": "after"}}]}
    # chunk_after идёт ПОСЛЕ [DONE]
    body = (
        f"data: {json.dumps(chunk_before)}\n\n"
        "data: [DONE]\n\n"
        f"data: {json.dumps(chunk_after)}\n\n"
    ).encode()

    client = LLMClient(endpoint="http://mock", model="test", timeout=5.0)
    client._http = httpx.AsyncClient(transport=_make_transport(body), base_url="http://mock", timeout=5.0)

    results = []
    async for chunk in client.stream_chat_completion(
        messages=[{"role": "user", "content": "hi"}],
        api_key="test-key",
    ):
        results.append(chunk)

    await client.aclose()

    # Только before, не after
    assert len(results) == 1
    assert results[0]["delta"]["content"] == "before"


# ---------------------------------------------------------------------------
# 6. _parse_retry_after — HTTP-date формат
# ---------------------------------------------------------------------------

def test_parse_retry_after_integer():
    """_parse_retry_after('45') → 45."""
    assert _parse_retry_after("45") == 45


def test_parse_retry_after_none_on_empty():
    """_parse_retry_after(None) → None."""
    assert _parse_retry_after(None) is None


def test_parse_retry_after_clamp_max():
    """_parse_retry_after('999') → 300 (clamp max)."""
    assert _parse_retry_after("999") == 300


def test_parse_retry_after_clamp_zero():
    """_parse_retry_after('-10') → 0 (clamp min)."""
    assert _parse_retry_after("-10") == 0


def test_parse_retry_after_invalid_string():
    """_parse_retry_after('invalid') → None."""
    assert _parse_retry_after("invalid-date") is None


def test_parse_retry_after_http_date_format():
    """_parse_retry_after с HTTP-date форматом → int секунды (≥0, ≤300)."""
    # Используем дату в далёком будущем для стабильного результата > 0
    future_date = "Thu, 01 Jan 2099 00:00:00 GMT"
    result = _parse_retry_after(future_date)
    assert isinstance(result, int)
    # Результат зажат в [0, 300]
    assert 0 <= result <= 300


# ---------------------------------------------------------------------------
# 7. context manager — __aenter__ / __aexit__
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_client_context_manager():
    """LLMClient работает как async context manager (__aenter__ / __aexit__)."""
    body = _make_sse_body([{"choices": [{"delta": {"content": "hi"}}]}])
    transport = _make_transport(body)

    async with LLMClient(endpoint="http://mock", model="test", timeout=5.0) as client:
        client._http = httpx.AsyncClient(transport=transport, base_url="http://mock", timeout=5.0)
        results = []
        async for chunk in client.stream_chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            api_key="test-key",
        ):
            results.append(chunk)
    # Нет исключений — __aexit__ вызван корректно
    assert len(results) == 1


# ---------------------------------------------------------------------------
# 8. standalone stream_chat_completion wrapper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_standalone_stream_chat_completion():
    """Функциональная обёртка stream_chat_completion является async generator."""
    import inspect

    from app.clients.llm import stream_chat_completion

    # Достаточно проверить тип — реальный вызов требует живого endpoint
    assert inspect.isasyncgenfunction(stream_chat_completion)
