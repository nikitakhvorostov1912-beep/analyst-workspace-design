"""Auxiliary LLM client — для side-tasks (compression, titles, memory review).

Sprint 1 — упрощённая версия. Один OpenAI-compatible endpoint, опционально
с другой моделью (aux_model). Без multi-provider fallback chain Hermes —
это будет в Sprint 5.

Используется в:
- title_generator (есть)
- Sprint 2: ContextCompressor
- Sprint 3: background_review, curator

Design rationale: aux_model должен быть дешевле и быстрее main модели,
чтобы side-tasks не съедали бюджет основного диалога. Например:
- main: claude-sonnet-4-6
- aux:  mimo-v2-flash (fast & cheap)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AuxiliaryClient:
    """Маленький wrapper над OpenAI-compatible API для side-tasks.

    НЕ streaming — для side-tasks важна простота, не latency. Один call,
    один response.

    Args:
        base_url: endpoint (тот же что и main, если не переопределён).
        api_key: ключ (тот же что main).
        model: модель. Если '' — fallback на main_model.
        main_model: основная модель сессии (fallback).
        timeout: secs. По умолчанию 60.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str | None = None,
        main_model: str,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model or main_model
        self.main_model = main_model
        self.timeout = timeout
        # W3.4 (2026-05-22): httpx.AsyncClient переиспользуется между .complete()
        # вызовами вместо `async with` per-call. ContextCompressor вызывает aux
        # на каждом переполнении контекста (5-15 раз за длинную сессию) — это
        # 5-15 TCP handshake'ов раньше. Теперь keep-alive + connection pooling
        # из коробки httpx даёт reuse одного соединения.
        # Закрытие через aclose() — вручную в loop.py outer finally (W1.5 verified
        # — там сейчас нет, см. TODO в loop.py перед outer try).
        self._http: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Ленивая инициализация. Безопасно вызывать многократно."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=self.timeout)
        return self._http

    async def aclose(self) -> None:
        """Закрыть HTTP клиент. Идемпотентно."""
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 1000,
        temperature: float = 0.3,
        response_format: dict | None = None,
    ) -> str:
        """Non-streaming completion. Возвращает текст ответа.

        Raises:
            httpx.HTTPStatusError: при не-2xx ответе.
            httpx.RequestError: при сетевой ошибке.
            ValueError: если в response нет content (формат не соответствует ожиданию).
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # W3.4: переиспользуемый http client (keep-alive)
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"Aux client: no choices in response (model={self.model})")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError(
                f"Aux client: response.choices[0].message.content is not a string (model={self.model})"
            )
        return content

    async def complete_with_fallback(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> str | None:
        """Best-effort wrapper. Возвращает None при любой ошибке вместо raise.

        Использовать для side-tasks где failure не должна ломать основной поток
        (например, background memory review).
        """
        try:
            return await self.complete(
                messages, max_tokens=max_tokens, temperature=temperature
            )
        except Exception as exc:
            logger.warning(
                "Aux client failed (model=%s): %s", self.model, _short_exc(exc),
            )
            return None


def _short_exc(exc: Exception) -> str:
    msg = str(exc)
    return msg if len(msg) <= 200 else msg[:200] + "..."
