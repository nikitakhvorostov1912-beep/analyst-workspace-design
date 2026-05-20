"""Redact — regex-маскировка секретов перед логированием/выводом.

Sprint 4 (Hermes E8): защита от утечки секретов в:
- Журнал ошибок (error logs)
- Stream diagnostics
- Сохраняемые trajectory (logging)
- Frontend payload

Алгоритм:
- Короткие токены (≤16 chars) — полностью маскируются "***"
- Длинные (≥17 chars) — сохраняют первые 6 + последние 4: "sk-abc123…d4f9"

Не трогаем:
- Контент пользователя (он сам решает что писать).
- Tool result payloads (они уже идут в LLM context).
- Markdown / HTML структуру.

Trigger patterns подобраны под common API key форматы. Можно расширять.
"""

from __future__ import annotations

import re
from typing import Pattern


# (label, regex, group_index_of_secret) — порядок важен (от специфичных к общим).
# group_index_of_secret = 0 → весь матч маскируется; > 0 → только эта группа.
_PATTERNS: list[tuple[str, Pattern[str], int]] = [
    # OpenAI / Anthropic / OpenRouter API ключи
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"), 0),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"), 0),
    ("openrouter_key", re.compile(r"\bsk-or-[A-Za-z0-9_\-]{20,}\b"), 0),
    # GitHub tokens
    ("github_token", re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"), 0),
    ("github_oauth", re.compile(r"\bgho_[A-Za-z0-9]{30,}\b"), 0),
    # AWS credentials
    ("aws_access_key", re.compile(r"\bAKIA[A-Z0-9]{16}\b"), 0),
    # Telegram bot token
    ("tg_bot", re.compile(r"\b\d{9,11}:[A-Za-z0-9_-]{30,}\b"), 0),
    # Bearer header (захватываем только сам токен после "Bearer ")
    ("bearer", re.compile(r"(Bearer\s+)([A-Za-z0-9_\-\.]{20,})", re.IGNORECASE), 2),
    # X-API-Key / Authorization-like заголовки (k=v)
    (
        "api_key_pair",
        re.compile(
            r"((?:api[_\-]?key|authorization|token|secret)\s*[:=]\s*['\"]?)"
            r"([A-Za-z0-9_\-\.]{20,})",
            re.IGNORECASE,
        ),
        2,
    ),
    # Generic high-entropy base64-like string длиной 32+ (хвост чувствительных URL).
    # Намеренно после специфичных паттернов, чтобы они шли первыми.
    # Не трогаем строки < 32 — много false positives на путях файлов и id 1С.
]


def _mask(secret: str) -> str:
    """Маскирует сам секрет: короткие — ***, длинные — head/tail preserve."""
    n = len(secret)
    if n <= 16:
        return "***"
    return secret[:6] + "…" + secret[-4:]


def redact(text: str) -> str:
    """Возвращает строку с замаскированными секретами.

    Безопасно к None / пустым / не-строкам — возвращает как есть.
    """
    if not isinstance(text, str) or not text:
        return text

    out = text
    for label, pattern, group_idx in _PATTERNS:
        def _repl(match: re.Match[str], gi: int = group_idx) -> str:
            if gi == 0:
                return _mask(match.group(0))
            # Сохраняем prefix groups, маскируем только group_idx
            prefix = match.group(1) if match.lastindex and match.lastindex >= 1 else ""
            secret = match.group(gi)
            return prefix + _mask(secret)

        out = pattern.sub(_repl, out)
    return out


def redact_dict(data: dict, *, keys_to_redact: set[str] | None = None) -> dict:
    """Возвращает копию dict с замаскированными значениями.

    Args:
        data: исходный dict (не мутируется).
        keys_to_redact: имена ключей которые ВСЕГДА маскировать целиком
            (даже если значение не похоже на секрет — например "password").
            Default: {"password", "api_key", "token", "secret", "authorization"}.
    """
    if keys_to_redact is None:
        keys_to_redact = {"password", "api_key", "token", "secret", "authorization", "x-api-key"}

    out: dict = {}
    for key, value in data.items():
        key_lower = key.lower() if isinstance(key, str) else key
        if isinstance(key_lower, str) and key_lower in keys_to_redact:
            if isinstance(value, str) and value:
                out[key] = _mask(value)
            else:
                out[key] = value
        elif isinstance(value, str):
            out[key] = redact(value)
        elif isinstance(value, dict):
            out[key] = redact_dict(value, keys_to_redact=keys_to_redact)
        elif isinstance(value, list):
            out[key] = [
                redact_dict(v, keys_to_redact=keys_to_redact)
                if isinstance(v, dict)
                else (redact(v) if isinstance(v, str) else v)
                for v in value
            ]
        else:
            out[key] = value
    return out
