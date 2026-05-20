"""Prompt injection scanner для данных из 1С / внешних источников.

Port of Hermes `agent/prompt_builder.py:_CONTEXT_THREAT_PATTERNS`.

Используется ПЕРЕД инжектом любого контента из 1С в SYSTEM_PROMPT
(MEMORY.md / USER.md, knowledge base, tool results, attachments).

Стратегия: regex-сканер обнаруживает 8 типов угроз. `scan()` возвращает
список найденных. `sanitize_for_prompt()` нейтрализует совпадения,
заменяя на `[REDACTED: <label>]` чтобы LLM их не выполняла.
"""

from __future__ import annotations

import re

# 8 типов prompt injection threats (адаптировано из Hermes).
# Все паттерны case-insensitive. group(0) — целое совпадение для preview/redaction.
_THREAT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"ignore\s+(previous|all|above|prior)\s+instructions", re.IGNORECASE),
        "prompt_injection",
    ),
    (
        re.compile(r"забудь\s+(предыдущие|все|выше|предыдущ)", re.IGNORECASE),
        "prompt_injection_ru",
    ),
    (
        re.compile(r"do\s+not\s+tell\s+the\s+user", re.IGNORECASE),
        "deception_hide",
    ),
    (
        re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
        "sys_prompt_override",
    ),
    (
        re.compile(r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)", re.IGNORECASE),
        "disregard_rules",
    ),
    (
        re.compile(
            r"act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'?t\s+have)\s+(restrictions|limits|rules)",
            re.IGNORECASE,
        ),
        "bypass_restrictions",
    ),
    (
        re.compile(r"<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->", re.IGNORECASE),
        "html_comment_injection",
    ),
    (
        re.compile(r"<\s*div\s+style\s*=\s*[\"\'][\s\S]*?display\s*:\s*none", re.IGNORECASE),
        "hidden_div",
    ),
    (
        re.compile(
            r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)",
            re.IGNORECASE,
        ),
        "exfil_curl",
    ),
    (
        re.compile(r"translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)", re.IGNORECASE),
        "translate_execute",
    ),
]


def scan(text: str) -> list[tuple[str, str]]:
    """Найти все matches. Возвращает [(threat_label, matched_preview), ...].

    Empty list = clean. matched_preview обрезан до 120 символов для логов.
    """
    if not text:
        return []
    hits: list[tuple[str, str]] = []
    for pattern, label in _THREAT_PATTERNS:
        m = pattern.search(text)
        if m:
            preview = m.group(0)[:120].replace("\n", " ")
            hits.append((label, preview))
    return hits


def sanitize_for_prompt(text: str) -> str:
    """Заменить все matches на `[REDACTED: <label>]` чтобы LLM их не выполняла.

    Использовать ПЕРЕД инжектом контента из внешних источников (1С, файлы)
    в SYSTEM_PROMPT или в первое user сообщение.
    """
    if not text:
        return text
    result = text
    for pattern, label in _THREAT_PATTERNS:
        result = pattern.sub(f"[REDACTED: {label}]", result)
    return result


def is_safe(text: str) -> bool:
    """Удобный shorthand: True если scan() вернул пусто."""
    return not scan(text)
