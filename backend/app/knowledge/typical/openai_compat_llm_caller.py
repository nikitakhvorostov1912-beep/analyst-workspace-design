"""Universal OpenAI-compatible LLM caller для real LLM rebuild карточек (M-K2.5.10.2).

Работает с любым провайдером поддерживающим OpenAI-совместимый `/chat/completions`:
DeepSeek, NVIDIA NIM, OpenAI, Anthropic (через OpenAI shim), Together, Groq,
Mistral, OpenRouter, Cloud.ru, etc.

Реализует `LLMCaller` Protocol из `card_generator.py` — подключается как
drop-in замена для `MockLLMCaller` в `generate_card_for_channel()`.

## Отличия от LLMClient (app/clients/llm.py)

- **Non-streaming** — карточки атомарные JSON, streaming не нужен
- **JSON response_format** — форсирует валидный JSON output где поддерживается
- **Cost tracking** — pricing table per provider, accumulated stats
- **Adaptive retry** — exponential backoff на 429/503, smart-decide на 5xx
- **Latency telemetry** — для ETA / cost per second monitoring

## Поддерживаемые провайдеры (с pricing)

| Provider domain | Input $/M | Output $/M | Note |
|---|---|---|---|
| api.deepseek.com | 0.07 | 1.10 | deepseek-chat / deepseek-reasoner |
| integrate.api.nvidia.com | 0.0 | 0.0 | Free tier с rate limits |
| api.openai.com | 0.15 / 2.50 | 0.60 / 10.00 | gpt-4o-mini / gpt-4o |
| api.anthropic.com | 0.80 / 3.00 | 4.00 / 15.00 | haiku 3.5 / sonnet 4.5 |
| api.together.xyz | varies | varies | per-model lookup |
| api.groq.com | 0.05 | 0.08 | llama 3.1 8B |
| api.mistral.ai | 0.20 | 0.60 | mistral-small |
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.knowledge.typical.card_generator import LLMResponse

logger = logging.getLogger(__name__)


# ─── Pricing table (USD per 1M tokens) ───────────────────────────────


_PRICING: dict[str, dict[str, float]] = {
    # DeepSeek
    "deepseek-chat":              {"input": 0.07,  "output": 1.10},
    "deepseek-coder":             {"input": 0.014, "output": 0.28},
    "deepseek-reasoner":          {"input": 0.55,  "output": 2.19},

    # OpenAI
    "gpt-4o-mini":                {"input": 0.15,  "output": 0.60},
    "gpt-4o":                     {"input": 2.50,  "output": 10.00},
    "gpt-4.1-mini":               {"input": 0.40,  "output": 1.60},
    "gpt-4.1":                    {"input": 2.00,  "output": 8.00},
    "o4-mini":                    {"input": 1.10,  "output": 4.40},

    # Anthropic
    "claude-3-5-haiku-20241022":  {"input": 0.80,  "output": 4.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00,  "output": 15.00},
    "claude-sonnet-4-5-20250929": {"input": 3.00,  "output": 15.00},

    # Groq (very cheap, fast)
    "llama-3.1-8b-instant":       {"input": 0.05,  "output": 0.08},
    "llama-3.3-70b-versatile":    {"input": 0.59,  "output": 0.79},

    # Mistral
    "mistral-small-latest":       {"input": 0.20,  "output": 0.60},
    "mistral-large-latest":       {"input": 2.00,  "output": 6.00},

    # NVIDIA NIM (free tier, считаем как $0)
    "nvidia/llama-3.3-nemotron-super-49b-v1.5": {"input": 0.0, "output": 0.0},
    "meta/llama-3.1-8b-instruct":               {"input": 0.0, "output": 0.0},
}


def calculate_cost(*, model: str, tokens_in: int, tokens_out: int) -> float:
    """Cost в USD. Если модель неизвестна — возвращает 0 (unknown pricing)."""
    pricing = _PRICING.get(model)
    if not pricing:
        # Fuzzy match: попытка найти по startswith (e.g. "gpt-4o-mini-2024-07-18" → "gpt-4o-mini")
        for known_model, p in _PRICING.items():
            if model.startswith(known_model) or known_model.startswith(model):
                pricing = p
                break
    if not pricing:
        return 0.0
    return (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000


# ─── Telemetry ───────────────────────────────────────────────────────


@dataclass
class CallTelemetry:
    """Аккумулированная статистика по всем call'ам LLMCaller."""

    total_calls: int = 0
    total_success: int = 0
    total_failure: int = 0
    total_retries: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    total_latency_s: float = 0.0
    failures_by_code: dict[int, int] = field(default_factory=dict)

    @property
    def avg_latency_s(self) -> float:
        if self.total_success == 0:
            return 0.0
        return self.total_latency_s / self.total_success

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_success / self.total_calls

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "total_success": self.total_success,
            "total_failure": self.total_failure,
            "total_retries": self.total_retries,
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_latency_s": round(self.total_latency_s, 1),
            "avg_latency_s": round(self.avg_latency_s, 2),
            "success_rate": round(self.success_rate, 3),
            "failures_by_code": dict(self.failures_by_code),
        }


# ─── Errors ──────────────────────────────────────────────────────────


class LLMCallError(Exception):
    """Базовая ошибка LLM call'a. Содержит status / body для debugging."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class LLMAuthError(LLMCallError):
    """401 / 403 — невалидный API key или нет доступа. НЕ retry."""


class LLMBadRequestError(LLMCallError):
    """4xx (кроме 401/403/429) — что-то с payload (model not found, etc.). НЕ retry."""


class LLMRateLimitError(LLMCallError):
    """429 — rate limit. Retry с exponential backoff."""

    def __init__(self, message: str, retry_after_s: int | None = None, **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.retry_after_s = retry_after_s


class LLMServerError(LLMCallError):
    """5xx — провайдер upstream. Retry."""


# ─── Main class ──────────────────────────────────────────────────────


@dataclass
class OpenAICompatLLMCaller:
    """LLMCaller для любого OpenAI-compatible API.

    Реализует Protocol `LLMCaller` из card_generator.py:
        async def complete(messages) -> LLMResponse

    Конфигурируется endpoint + model + api_key. Опции:
    - temperature: 0.0..2.0 (default 0.2 для детерминированности)
    - timeout: HTTP timeout per request (default 180s)
    - max_retries: количество попыток на 429/5xx (default 5)
    - request_json_object: если True добавляет response_format=json_object
        (поддерживается OpenAI, DeepSeek, NVIDIA, Anthropic shim, Mistral;
        НЕ поддерживается OpenRouter некоторыми моделями)

    Telemetry доступна через `self.telemetry` после серии call'ов.
    """

    endpoint: str
    model: str
    api_key: str
    temperature: float = 0.2
    timeout: float = 180.0
    max_retries: int = 5
    request_json_object: bool = True
    max_tokens: int | None = None  # None = не ограничивать
    telemetry: CallTelemetry = field(default_factory=CallTelemetry)

    def __post_init__(self) -> None:
        # Защита: убираем trailing slash чтобы не получить //chat/completions.
        self.endpoint = self.endpoint.rstrip("/")
        if not self.api_key:
            raise ValueError("api_key обязателен и не может быть пустым")
        if not self.model:
            raise ValueError("model обязателен")

    async def complete(self, messages: list[dict[str, str]]) -> LLMResponse:
        """Single LLM call с retry. Реализует LLMCaller Protocol."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.request_json_object:
            payload["response_format"] = {"type": "json_object"}

        self.telemetry.total_calls += 1

        # Retry loop с exponential backoff
        backoff = 1.0
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            start = time.monotonic()
            try:
                response = await self._http_call(payload)
                elapsed = time.monotonic() - start
                # Парсинг ответа
                choice = response["choices"][0]
                content = choice["message"]["content"] or ""
                usage = response.get("usage") or {}
                tokens_in = int(usage.get("prompt_tokens") or 0)
                tokens_out = int(usage.get("completion_tokens") or 0)
                cost = calculate_cost(
                    model=self.model, tokens_in=tokens_in, tokens_out=tokens_out,
                )

                # Telemetry
                self.telemetry.total_success += 1
                self.telemetry.total_tokens_in += tokens_in
                self.telemetry.total_tokens_out += tokens_out
                self.telemetry.total_cost_usd += cost
                self.telemetry.total_latency_s += elapsed

                return LLMResponse(
                    content=content,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    model=response.get("model") or self.model,
                )

            except LLMAuthError as e:
                # 401/403 — retry бессмысленен
                self.telemetry.total_failure += 1
                self.telemetry.failures_by_code[e.status or 0] = (
                    self.telemetry.failures_by_code.get(e.status or 0, 0) + 1
                )
                raise

            except LLMBadRequestError as e:
                # 4xx (model not found, etc.) — retry бессмысленен
                self.telemetry.total_failure += 1
                self.telemetry.failures_by_code[e.status or 0] = (
                    self.telemetry.failures_by_code.get(e.status or 0, 0) + 1
                )
                raise

            except LLMRateLimitError as e:
                last_error = e
                self.telemetry.total_retries += 1
                self.telemetry.failures_by_code[429] = (
                    self.telemetry.failures_by_code.get(429, 0) + 1
                )
                # Если провайдер указал Retry-After — используем его
                wait_s = e.retry_after_s if e.retry_after_s else backoff
                wait_s = min(wait_s, 60.0)
                logger.warning(
                    "LLM rate limit (attempt %d/%d), wait %.1fs",
                    attempt, self.max_retries, wait_s,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(wait_s)
                    backoff = min(backoff * 2, 60.0)
                    continue

            except LLMServerError as e:
                last_error = e
                self.telemetry.total_retries += 1
                self.telemetry.failures_by_code[e.status or 500] = (
                    self.telemetry.failures_by_code.get(e.status or 500, 0) + 1
                )
                logger.warning(
                    "LLM server error %s (attempt %d/%d), wait %.1fs",
                    e.status, attempt, self.max_retries, backoff,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
                    continue

            except httpx.TimeoutException as e:
                last_error = LLMCallError(f"Timeout: {e}")
                self.telemetry.total_retries += 1
                self.telemetry.failures_by_code[-1] = (
                    self.telemetry.failures_by_code.get(-1, 0) + 1
                )
                logger.warning(
                    "LLM timeout (attempt %d/%d), wait %.1fs",
                    attempt, self.max_retries, backoff,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
                    continue

            except httpx.HTTPError as e:
                # Network errors — retry
                last_error = LLMCallError(f"Network error: {e}")
                self.telemetry.total_retries += 1
                if attempt < self.max_retries:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
                    continue

        # Все retry исчерпаны
        self.telemetry.total_failure += 1
        if last_error:
            raise last_error
        raise LLMCallError(f"Все {self.max_retries} попыток исчерпаны")

    async def _http_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Single HTTP call. Парсит response в dict или бросает LLM*Error."""
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            r = await http.post(
                f"{self.endpoint}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )

        status = r.status_code
        if status == 200:
            try:
                return r.json()
            except Exception as e:
                raise LLMCallError(f"Не-JSON ответ 200: {e}", status=200, body=r.text[:500]) from e

        body_excerpt = r.text[:500]

        if status in (401, 403):
            raise LLMAuthError(
                f"Auth failed {status}: {body_excerpt}", status=status, body=body_excerpt,
            )

        if status == 429:
            retry_after = None
            ra = r.headers.get("retry-after") or r.headers.get("Retry-After")
            if ra:
                try:
                    retry_after = int(ra)
                except ValueError:
                    pass
            raise LLMRateLimitError(
                f"Rate limit 429: {body_excerpt}", status=429, body=body_excerpt,
                retry_after_s=retry_after,
            )

        if 500 <= status < 600:
            raise LLMServerError(
                f"Server error {status}: {body_excerpt}", status=status, body=body_excerpt,
            )

        # Прочие 4xx — bad request
        raise LLMBadRequestError(
            f"Bad request {status}: {body_excerpt}", status=status, body=body_excerpt,
        )
