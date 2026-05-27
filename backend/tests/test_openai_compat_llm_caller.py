"""Тесты для OpenAICompatLLMCaller (M-K2.5.10.2).

Используем respx для mock HTTP — без реальных API вызовов.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.knowledge.typical.openai_compat_llm_caller import (
    LLMAuthError,
    LLMBadRequestError,
    LLMCallError,
    LLMRateLimitError,
    LLMServerError,
    OpenAICompatLLMCaller,
    calculate_cost,
)


# ─── Pricing ──────────────────────────────────────────────────────────


class TestPricing:
    def test_deepseek_chat_cost(self):
        cost = calculate_cost(
            model="deepseek-chat", tokens_in=1_000_000, tokens_out=1_000_000,
        )
        assert cost == pytest.approx(0.07 + 1.10)

    def test_unknown_model_returns_zero(self):
        cost = calculate_cost(
            model="completely-unknown-model-xyz", tokens_in=1000, tokens_out=1000,
        )
        assert cost == 0.0

    def test_fuzzy_match_with_version_suffix(self):
        # Реальная модель OpenAI часто называется gpt-4o-mini-2024-07-18
        cost = calculate_cost(
            model="gpt-4o-mini-2024-07-18", tokens_in=1_000_000, tokens_out=1_000_000,
        )
        # Должно найти "gpt-4o-mini" по startswith
        assert cost > 0
        assert cost == pytest.approx(0.15 + 0.60)


# ─── Construction ─────────────────────────────────────────────────────


class TestConstruction:
    def test_strips_trailing_slash(self):
        caller = OpenAICompatLLMCaller(
            endpoint="https://api.deepseek.com/v1/",
            model="deepseek-chat",
            api_key="sk-test",
        )
        assert caller.endpoint == "https://api.deepseek.com/v1"

    def test_empty_api_key_raises(self):
        with pytest.raises(ValueError, match="api_key"):
            OpenAICompatLLMCaller(
                endpoint="https://api.example.com/v1",
                model="x",
                api_key="",
            )

    def test_empty_model_raises(self):
        with pytest.raises(ValueError, match="model"):
            OpenAICompatLLMCaller(
                endpoint="https://api.example.com/v1",
                model="",
                api_key="sk-x",
            )


# ─── Happy path ───────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_complete_success():
    """Успешный call возвращает LLMResponse с правильными полями."""
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "test-id",
                "model": "deepseek-chat",
                "choices": [
                    {"message": {"content": '{"summary": "test"}'}, "finish_reason": "stop"},
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            },
        )
    )

    caller = OpenAICompatLLMCaller(
        endpoint="https://api.example.com/v1",
        model="deepseek-chat",
        api_key="sk-test",
    )
    response = await caller.complete([{"role": "user", "content": "test"}])

    assert response.content == '{"summary": "test"}'
    assert response.tokens_in == 100
    assert response.tokens_out == 50
    assert response.model == "deepseek-chat"

    # Telemetry
    assert caller.telemetry.total_calls == 1
    assert caller.telemetry.total_success == 1
    assert caller.telemetry.total_failure == 0
    assert caller.telemetry.total_tokens_in == 100
    assert caller.telemetry.total_tokens_out == 50
    # Cost: 100/1M*0.07 + 50/1M*1.10 = 0.000007 + 0.000055 = 0.000062
    assert caller.telemetry.total_cost_usd == pytest.approx(0.000062, rel=0.01)


@pytest.mark.asyncio
@respx.mock
async def test_request_format():
    """Проверяет что payload содержит правильные поля."""
    captured: dict = {}

    def capture(request: httpx.Request) -> httpx.Response:
        import json as _json
        captured.update(_json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json={
                "model": "test", "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    respx.post("https://api.example.com/v1/chat/completions").mock(side_effect=capture)

    caller = OpenAICompatLLMCaller(
        endpoint="https://api.example.com/v1",
        model="test-model",
        api_key="sk-x",
        temperature=0.5,
        max_tokens=2000,
        request_json_object=True,
    )
    await caller.complete([{"role": "user", "content": "hi"}])

    assert captured["model"] == "test-model"
    assert captured["temperature"] == 0.5
    assert captured["max_tokens"] == 2000
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["messages"] == [{"role": "user", "content": "hi"}]


# ─── Error handling ───────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_401_raises_auth_error_no_retry():
    """401 → LLMAuthError, без retry."""
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": {"message": "Invalid API key"}}),
    )

    caller = OpenAICompatLLMCaller(
        endpoint="https://api.example.com/v1",
        model="x",
        api_key="sk-bad",
        max_retries=5,
    )
    with pytest.raises(LLMAuthError) as exc_info:
        await caller.complete([{"role": "user", "content": "hi"}])

    assert exc_info.value.status == 401
    assert route.call_count == 1  # без retry
    assert caller.telemetry.total_failure == 1
    assert caller.telemetry.failures_by_code[401] == 1


@pytest.mark.asyncio
@respx.mock
async def test_400_raises_bad_request_no_retry():
    """400 (model not found) → LLMBadRequestError, без retry."""
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(400, json={"error": "model not found"}),
    )

    caller = OpenAICompatLLMCaller(
        endpoint="https://api.example.com/v1",
        model="nonexistent",
        api_key="sk-x",
    )
    with pytest.raises(LLMBadRequestError):
        await caller.complete([{"role": "user", "content": "hi"}])

    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_429_retries_then_succeeds():
    """429 → retry с backoff, потом 200."""
    responses = [
        httpx.Response(429, json={"error": "rate limit"}, headers={"retry-after": "0"}),
        httpx.Response(429, json={"error": "rate limit"}, headers={"retry-after": "0"}),
        httpx.Response(
            200,
            json={
                "model": "x", "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        ),
    ]
    route = respx.post("https://api.example.com/v1/chat/completions").mock(side_effect=responses)

    caller = OpenAICompatLLMCaller(
        endpoint="https://api.example.com/v1",
        model="x",
        api_key="sk-x",
        max_retries=5,
    )
    response = await caller.complete([{"role": "user", "content": "hi"}])

    assert response.content == "{}"
    assert route.call_count == 3
    assert caller.telemetry.total_retries == 2  # 2 retry до успеха
    assert caller.telemetry.total_success == 1


@pytest.mark.asyncio
@respx.mock
async def test_429_exhausts_retries_raises():
    """429 на всех retry → LLMRateLimitError."""
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            429, json={"error": "rate limit"}, headers={"retry-after": "0"},
        ),
    )

    caller = OpenAICompatLLMCaller(
        endpoint="https://api.example.com/v1",
        model="x",
        api_key="sk-x",
        max_retries=3,
    )
    with pytest.raises(LLMRateLimitError):
        await caller.complete([{"role": "user", "content": "hi"}])

    assert caller.telemetry.total_retries == 3
    assert caller.telemetry.total_failure == 1


@pytest.mark.asyncio
@respx.mock
async def test_500_retries_then_succeeds():
    """5xx → retry."""
    responses = [
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(
            200,
            json={
                "model": "x", "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        ),
    ]
    route = respx.post("https://api.example.com/v1/chat/completions").mock(side_effect=responses)

    caller = OpenAICompatLLMCaller(
        endpoint="https://api.example.com/v1",
        model="x",
        api_key="sk-x",
        max_retries=3,
    )
    response = await caller.complete([{"role": "user", "content": "hi"}])

    assert response.content == "{}"
    assert route.call_count == 2


# ─── Telemetry ────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_telemetry_accumulates_across_calls():
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )
    )

    caller = OpenAICompatLLMCaller(
        endpoint="https://api.example.com/v1",
        model="deepseek-chat",
        api_key="sk-x",
    )
    for _ in range(5):
        await caller.complete([{"role": "user", "content": "x"}])

    assert caller.telemetry.total_calls == 5
    assert caller.telemetry.total_success == 5
    assert caller.telemetry.total_tokens_in == 500
    assert caller.telemetry.total_tokens_out == 250
    assert caller.telemetry.success_rate == 1.0

    d = caller.telemetry.to_dict()
    assert d["total_calls"] == 5
    assert d["total_cost_usd"] > 0


# ─── Integration с card_generator ─────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_works_as_LLMCaller_in_generate_card():
    """OpenAICompatLLMCaller drop-in совместим с generate_card."""
    from app.knowledge.typical.card_context import CardContext  # noqa: PLC0415
    from app.knowledge.typical.card_generator import generate_card  # noqa: PLC0415

    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "choices": [{
                    "message": {
                        "content": (
                            '{"summary": "Документ продажи",'
                            ' "purpose": "Регистрирует реализацию",'
                            ' "key_attributes": [{"name": "Контрагент", "role": "покупатель"}],'
                            ' "movements": [],'
                            ' "posting_flow": []}'
                        ),
                    },
                }],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )
    )

    caller = OpenAICompatLLMCaller(
        endpoint="https://api.example.com/v1",
        model="deepseek-chat",
        api_key="sk-x",
    )
    ctx = CardContext(
        object_qualified_name="Document.X",
        object_kind="Document",
        object_name="X",
        object_uuid=None,
        object_comment="",
        object_source_path=None,
    )
    result = await generate_card(context=ctx, llm=caller)

    assert result.card.summary == "Документ продажи"
    assert result.card.purpose == "Регистрирует реализацию"
    assert result.card.key_attributes[0].name == "Контрагент"
    assert result.card.key_attributes[0].role == "покупатель"
    assert result.tokens_in == 100
    assert result.model == "deepseek-chat"
