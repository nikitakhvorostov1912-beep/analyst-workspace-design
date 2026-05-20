"""Prompt caching — cache_control breakpoints для Anthropic-compat API.

Sprint 5 (Hermes H4): ~75% input cost reduction в multi-turn.

Anthropic layout (system_and_3):
- breakpoint 1: system prompt (large, stable)
- breakpoint 2-4: last 3 non-system messages (стабильны между turn'ами в одном
  диалоге за исключением финального user)

Cache работает только если:
1. Модель поддерживает caching (Anthropic).
2. Кэш-блок ≥ 1024 токенов (~3500 chars).
3. Используется через `cache_control: {type: 'ephemeral', ttl: '5m' | '1h'}`.

Этот модуль вычисляет ГДЕ ставить cache_control. Сами заголовки добавляются
в LLM client. Для MiMo / OpenAI — no-op (просто возвращаем messages как есть).
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from app.orchestrator.model_metadata import get_metadata

logger = logging.getLogger(__name__)


# Минимум chars в блоке для cache_control (~1024 tokens).
MIN_CACHE_BLOCK_CHARS = 3_500
# Default TTL: 1h окупается со 2-го turn'а в долгих сессиях.
DEFAULT_TTL = "1h"


def apply_cache_breakpoints(
    messages: list[dict[str, Any]],
    model: str,
    *,
    ttl: str = DEFAULT_TTL,
) -> list[dict[str, Any]]:
    """Возвращает копию messages с cache_control расставленными по Hermes-схеме.

    Если модель не поддерживает caching — возвращает копию без изменений.
    Для системы:
    - System prompt: cache_control на последнем content part.
    - Последние 3 non-system message: каждый — cache_control на content части.
    """
    meta = get_metadata(model)
    if not meta.supports_caching:
        return list(messages)  # no-op shallow copy

    out = copy.deepcopy(messages)
    breakpoints_used = 0
    MAX_BREAKPOINTS = 4  # Anthropic hard limit

    # 1) System: первое message с role=system.
    for msg in out:
        if msg.get("role") == "system":
            if _mark_cache_control(msg, ttl=ttl):
                breakpoints_used += 1
            break

    # 2-4) Последние 3 non-system message.
    non_sys = [m for m in out if m.get("role") != "system"]
    last3 = non_sys[-3:] if len(non_sys) >= 3 else non_sys

    for msg in reversed(last3):
        if breakpoints_used >= MAX_BREAKPOINTS:
            break
        if _mark_cache_control(msg, ttl=ttl):
            breakpoints_used += 1

    if breakpoints_used > 0:
        logger.debug("Prompt caching: %d breakpoints применено", breakpoints_used)
    return out


def _mark_cache_control(msg: dict[str, Any], *, ttl: str) -> bool:
    """Помечает content в msg cache_control. Возвращает True если успешно.

    Контент должен быть достаточного объёма (MIN_CACHE_BLOCK_CHARS).
    """
    content = msg.get("content")

    if isinstance(content, str):
        if len(content) < MIN_CACHE_BLOCK_CHARS:
            return False
        # Конвертируем плоский string content в list-of-parts с cache_control.
        msg["content"] = [
            {
                "type": "text",
                "text": content,
                "cache_control": {"type": "ephemeral", "ttl": ttl},
            }
        ]
        return True

    if isinstance(content, list):
        # Ставим cache_control на ПОСЛЕДНИЙ text-part (если есть).
        total_chars = 0
        last_text_idx = -1
        for i, part in enumerate(content):
            if isinstance(part, dict) and part.get("type") == "text":
                total_chars += len(part.get("text") or "")
                last_text_idx = i
        if total_chars < MIN_CACHE_BLOCK_CHARS or last_text_idx < 0:
            return False
        content[last_text_idx]["cache_control"] = {"type": "ephemeral", "ttl": ttl}
        return True

    return False


def is_caching_supported(model: str) -> bool:
    """Удобный shortcut для проверки."""
    return get_metadata(model).supports_caching
