"""OpenAI-совместимый LLM-клиент со streaming."""

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC
from email.utils import parsedate_to_datetime

import httpx

logger = logging.getLogger(__name__)


class LLMRateLimitError(httpx.HTTPStatusError):
    """429 Too Many Requests от LLM-провайдера.

    Дополнительный атрибут retry_after_s: число секунд из заголовка Retry-After
    (int) или None если заголовок отсутствует или не парсится.
    """

    retry_after_s: int | None = None


def _parse_retry_after(header_value: str | None) -> int | None:
    """Парсит значение заголовка Retry-After в секунды.

    Поддерживает: целое число секунд и HTTP-date формат.
    Возвращает None если header_value пустой или не парсится.
    Clamp: 0..300 сек (T-03-04).
    """
    if not header_value:
        return None
    try:
        seconds = int(header_value)
        return max(0, min(seconds, 300))
    except ValueError:
        pass
    try:
        from datetime import datetime
        dt = parsedate_to_datetime(header_value)
        now = datetime.now(tz=UTC)
        delta = int((dt - now).total_seconds())
        return max(0, min(delta, 300))
    except Exception:
        return None


class LLMClient:
    """HTTP-клиент для OpenAI-совместимых LLM API (streaming)."""

    def __init__(self, endpoint: str, model: str, timeout: float = 60.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self._http = httpx.AsyncClient(base_url=self.endpoint, timeout=timeout)

    async def stream_chat_completion(
        self,
        messages: list[dict],
        api_key: str,
        tools: list[dict] | None = None,
        temperature: float = 0.3,
    ) -> AsyncIterator[dict]:
        """Стримит чанки из POST /chat/completions.

        Каждый yielded dict — это choices[0].delta из SSE-чанка.
        Останов на 'data: [DONE]'.

        Raises:
            httpx.HTTPStatusError: при ошибке HTTP от провайдера.
        """
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        # Authorization header не логируем — T-01-01
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with self._http.stream(
            "POST",
            "/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            if response.status_code == 429:
                retry_after_s = _parse_retry_after(
                    response.headers.get("retry-after") or response.headers.get("Retry-After")
                )
                exc = LLMRateLimitError(
                    "HTTP 429 Too Many Requests",
                    request=response.request,
                    response=response,
                )
                exc.retry_after_s = retry_after_s
                raise exc
            if response.status_code >= 400:
                # Логируем body 4xx/5xx для диагностики — некоторые LLM возвращают
                # человекочитаемую ошибку в теле, которая не видна без debug.
                import logging
                err_body = await response.aread()
                logging.getLogger(__name__).warning(
                    "LLM HTTP %s body: %s",
                    response.status_code,
                    err_body.decode("utf-8", errors="replace")[:1000],
                )
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[len("data: "):]
                if raw.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Не удалось распарсить SSE чанк: %s", raw[:100])
                    continue
                choices = chunk.get("choices")
                if not choices:
                    continue
                yield choices[0]

    async def aclose(self) -> None:
        """Закрывает внутренний httpx.AsyncClient."""
        await self._http.aclose()

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()


async def stream_chat_completion(
    endpoint: str,
    model: str,
    messages: list[dict],
    api_key: str,
    tools: list[dict] | None = None,
    temperature: float = 0.3,
    timeout: float = 60.0,
) -> AsyncIterator[dict]:
    """Функциональная обёртка над LLMClient для разового вызова."""
    async with LLMClient(endpoint, model, timeout) as client:
        async for chunk in client.stream_chat_completion(messages, api_key, tools, temperature):
            yield chunk
