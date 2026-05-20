"""Error classifier — приоритетный pipeline классификации ошибок.

Sprint 2 (Hermes E1, 1087 строк в оригинале — у нас компактнее).

Концепция Hermes:
- FailoverReason enum описывает что произошло.
- classify(exc) возвращает FailoverDecision: что делать дальше.
- Решения: RETRY (transient) / FALLBACK (попробовать запасной endpoint) /
  COMPRESS (контекст переполнен → сжать) / RATE_LIMIT (ждать) /
  AUTH_FAIL (стоп, юзер) / ABORT (фатально, стоп).

Этот модуль — pure function over exceptions. Не делает I/O. Используется
loop.py чтобы решать что делать после исключения LLM/MCP-вызова.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

import httpx

from app.clients.llm import LLMRateLimitError
from app.clients.mcp import MCPDisconnectedError, MCPError


class FailoverReason(str, enum.Enum):
    """Категория сбоя — детерминирует действие loop'а."""

    TRANSIENT_NETWORK = "transient_network"      # ConnectError/Timeout — retry
    HTTP_5XX = "http_5xx"                        # 500/502/503/504 — retry
    HTTP_4XX = "http_4xx"                        # 400/404 — abort (наша вина или endpoint)
    RATE_LIMIT = "rate_limit"                    # 429 — ждать retry_after
    AUTH = "auth"                                # 401/403 — пользователь должен поправить ключ
    CONTEXT_OVERFLOW = "context_overflow"        # 413 / "context length exceeded" — compress
    MCP_DISCONNECTED = "mcp_disconnected"        # 1C недоступен — abort с понятным сообщением
    MCP_PROTOCOL = "mcp_protocol"                # JSON-RPC ошибка — abort, это баг MCP-сервера
    UNKNOWN = "unknown"                          # не классифицировано — abort с trace в логе


class Action(str, enum.Enum):
    """Что делать loop'у."""

    RETRY = "retry"
    COMPRESS_AND_RETRY = "compress_and_retry"
    ABORT = "abort"


@dataclass(frozen=True)
class FailoverDecision:
    """Результат классификации — что делать с исключением."""

    reason: FailoverReason
    action: Action
    user_message: str          # что показать в UI
    error_code: str            # код для frontend (используется в ErrorEvent.code)
    retry_after_s: float | None = None  # подсказка для retry policy
    log_level: str = "warning"          # warning | error | info


# Маркеры в тексте ошибки которые указывают на context overflow.
# Разные LLM-провайдеры формулируют по-разному — собираем все встречавшиеся.
_CONTEXT_OVERFLOW_MARKERS = (
    "context length",
    "context_length",
    "maximum context",
    "context_window",
    "tokens exceeded",
    "tokens > max",
    "превышен лимит контекста",
    "too long",  # некоторые формулировки от MiMo
    "request entity too large",
)


def _contains_context_overflow_marker(text: str) -> bool:
    lower = text.lower()
    return any(m in lower for m in _CONTEXT_OVERFLOW_MARKERS)


def classify(exc: Exception, *, context: dict[str, Any] | None = None) -> FailoverDecision:
    """Классифицирует исключение и возвращает план действий.

    Args:
        exc: пойманное исключение.
        context: опциональный контекст ({where: "llm" | "mcp", attempt: int}).

    Returns:
        FailoverDecision — что делать. ABORT по умолчанию если ничего не подошло.
    """
    where = (context or {}).get("where", "unknown")

    # --- LLM rate-limit (наш кастомный класс) ---
    if isinstance(exc, LLMRateLimitError):
        return FailoverDecision(
            reason=FailoverReason.RATE_LIMIT,
            action=Action.ABORT,
            user_message="Превышен лимит запросов к LLM. Попробуйте позже.",
            error_code="llm_rate_limit",
            retry_after_s=getattr(exc, "retry_after_s", None),
        )

    # --- MCP-специфичные ---
    if isinstance(exc, MCPDisconnectedError):
        return FailoverDecision(
            reason=FailoverReason.MCP_DISCONNECTED,
            action=Action.ABORT,
            user_message="Соединение с 1С MCP потеряно.",
            error_code="mcp_disconnected",
        )
    if isinstance(exc, MCPError):
        return FailoverDecision(
            reason=FailoverReason.MCP_PROTOCOL,
            action=Action.ABORT,
            user_message=f"Ошибка протокола MCP: {str(exc)[:200]}",
            error_code="mcp_protocol_error",
        )

    # --- HTTP-ошибки (LLM и/или MCP) ---
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body_snippet = ""
        try:
            body_snippet = exc.response.text[:500]
        except Exception:  # noqa: BLE001 — best-effort извлечение
            pass

        if status == 429:
            retry_after = _parse_retry_after(exc.response.headers.get("retry-after"))
            return FailoverDecision(
                reason=FailoverReason.RATE_LIMIT,
                action=Action.ABORT,
                user_message="Превышен лимит запросов. Попробуйте позже.",
                error_code="llm_rate_limit" if where == "llm" else "rate_limit",
                retry_after_s=retry_after,
            )
        if status in (401, 403):
            return FailoverDecision(
                reason=FailoverReason.AUTH,
                action=Action.ABORT,
                user_message="Неверный API-ключ или нет доступа к LLM."
                if where == "llm"
                else "Нет доступа к ресурсу.",
                error_code="llm_invalid_key" if where == "llm" else "forbidden",
            )
        if status == 413 or _contains_context_overflow_marker(body_snippet):
            return FailoverDecision(
                reason=FailoverReason.CONTEXT_OVERFLOW,
                action=Action.COMPRESS_AND_RETRY,
                user_message="Контекст слишком большой — пересжимаю историю и пробую снова.",
                error_code="context_overflow",
                log_level="info",
            )
        if 500 <= status < 600:
            return FailoverDecision(
                reason=FailoverReason.HTTP_5XX,
                action=Action.RETRY,
                user_message=f"Сервер вернул HTTP {status} — пробую снова.",
                error_code="llm_server_error" if where == "llm" else "server_error",
            )
        if 400 <= status < 500:
            return FailoverDecision(
                reason=FailoverReason.HTTP_4XX,
                action=Action.ABORT,
                user_message=f"Ошибка запроса (HTTP {status}).",
                error_code="bad_request",
            )

    # --- Сетевые ошибки (timeout / connect) ---
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)):
        return FailoverDecision(
            reason=FailoverReason.TRANSIENT_NETWORK,
            action=Action.RETRY,
            user_message="Сетевая ошибка — пробую снова.",
            error_code="llm_network_error" if where == "llm" else "network_error",
        )

    # Любая прочая httpx.RequestError — тоже сеть, transient.
    if isinstance(exc, httpx.RequestError):
        return FailoverDecision(
            reason=FailoverReason.TRANSIENT_NETWORK,
            action=Action.RETRY,
            user_message="Сетевая ошибка при обращении к серверу.",
            error_code="network_error",
        )

    # --- Прочие сообщения, проверяем по тексту (context_overflow от raw exceptions) ---
    msg = str(exc)
    if _contains_context_overflow_marker(msg):
        return FailoverDecision(
            reason=FailoverReason.CONTEXT_OVERFLOW,
            action=Action.COMPRESS_AND_RETRY,
            user_message="Контекст слишком большой — пересжимаю историю.",
            error_code="context_overflow",
            log_level="info",
        )

    # --- Fallback ---
    return FailoverDecision(
        reason=FailoverReason.UNKNOWN,
        action=Action.ABORT,
        user_message="Внутренняя ошибка обработки запроса.",
        error_code="internal_error",
        log_level="error",
    )


def _parse_retry_after(header: str | None) -> float | None:
    """Парсит Retry-After header → секунды.

    Спецификация HTTP допускает или int-секунды, или HTTP-date.
    Поддерживаем только int — date встречается редко в API LLM.
    """
    if not header:
        return None
    try:
        return float(header.strip())
    except (ValueError, TypeError):
        return None
