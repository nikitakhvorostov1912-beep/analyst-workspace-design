"""Модуль безопасности: dangerous keywords + pending confirmation store (SEC-01).

W1.2 (2026-05-22): расширено покрытие на execute_query. Раньше сканировался
только execute_code (BSL). Теперь оба MCP-инструмента проверяются на keywords,
причём для execute_query добавлены SQL-DML слова (Insert/Update/Alter/Grant)
— на случай если MCP Toolkit прокидывает запрос напрямую в DBMS минуя слой
запросов 1С (read-only). Это закрывает CRITICAL-вектор «LLM вызывает
execute_query с DML».
"""

import asyncio
import os
import re
from typing import Any

# Инструменты, args которых должны сканироваться на dangerous keywords.
# Расширяется автоматически если новые MCP-сервера добавят опасные tools.
_DANGEROUS_TOOL_NAMES: frozenset[str] = frozenset({"execute_code", "execute_query"})


# ===== Dangerous keywords =====

# BSL-keywords (применимы к execute_code в первую очередь, но и для execute_query
# не помешает — комментарий в запросе может содержать BSL-вставку).
_BSL_PATTERNS = [
    r"\bУдалить\b",
    r"\bЗаписать\(",
    r"\bНачатьТранзакцию\b",
    r"\bОчистить\b",
    r"\bУстановить\b",
    r"\bОтменить\b",
]

# SQL DDL/DML keywords. Язык запросов 1С — read-only (SELECT/UNION/JOIN),
# DML отсутствует. Но если LLM «придумает» SQL-инъекцию через MCP Toolkit
# (`; DROP TABLE`, `; DELETE FROM`) — должны остановить ДО отправки в 1С.
# Также защищает от ошибочного использования execute_query как escape hatch
# для DBMS-уровня (некоторые MCP-серверы могут выполнить raw SQL).
_SQL_PATTERNS = [
    r"\bDelete\b",
    r"\bDrop\b",
    r"\bTruncate\b",
    r"\bRemove\b",
    r"\bInsert\b",
    r"\bUpdate\s+\w+\s+set\b",  # «Update X set Y=...» — именно SQL UPDATE, не BSL
    r"\bAlter\b",
    r"\bGrant\b",
    r"\bRevoke\b",
    r"\bExec\b",
    r"\bSp_executesql\b",
]

_DEFAULT_PATTERNS = _BSL_PATTERNS + _SQL_PATTERNS


def _build_patterns() -> list[re.Pattern]:
    """Строит список pre-compiled regex из дефолтных + env DANGEROUS_KEYWORDS.

    DANGEROUS_KEYWORDS=comma,separated — literal strings, оборачиваются в word-boundary regex.
    """
    patterns = [re.compile(p, re.IGNORECASE) for p in _DEFAULT_PATTERNS]

    env_keywords = os.environ.get("DANGEROUS_KEYWORDS", "").strip()
    if env_keywords:
        for kw in env_keywords.split(","):
            kw = kw.strip()
            if kw:
                patterns.append(re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE))

    return patterns


DANGEROUS_KEYWORDS: list[re.Pattern] = _build_patterns()

# Timeout для ожидания подтверждения (конфигурируется через env)
CONFIRMATION_TIMEOUT_S: float = float(os.environ.get("DANGEROUS_CONFIRM_TIMEOUT", "120.0"))


def is_dangerous_tool(tool_name: str) -> bool:
    """True если args этого MCP-инструмента нужно сканировать на dangerous keywords.

    Используется в loop.py для решения "вызывать scan_for_dangerous или нет".
    Сейчас покрывает execute_code (BSL) + execute_query (SQL-DML защита от
    DBMS-инъекций через MCP Toolkit). Расширяется через _DANGEROUS_TOOL_NAMES.
    """
    return tool_name in _DANGEROUS_TOOL_NAMES


def scan_for_dangerous(args: dict[str, Any]) -> str | None:
    """Сканирует словарь аргументов инструмента на наличие dangerous keywords.

    Сериализует args в JSON-строку и проверяет регексы.
    Возвращает строку описания совпадения или None.
    """
    import json

    args_str = json.dumps(args, ensure_ascii=False)

    for pattern in DANGEROUS_KEYWORDS:
        m = pattern.search(args_str)
        if m:
            # Убираем '(' из имени keyword для читабельного сообщения
            keyword = m.group(0).rstrip("(")
            return f"keyword: {keyword}"

    return None


# ===== Pending confirmation store =====

# module-level dict: tool_call_id → (event, payload)
_pending: dict[str, tuple[asyncio.Event, dict[str, bool]]] = {}


def register_pending_confirmation(tool_call_id: str) -> asyncio.Event:
    """Регистрирует ожидание подтверждения для tool_call_id.

    Возвращает asyncio.Event, который будет set() после resolve.
    """
    ev = asyncio.Event()
    _pending[tool_call_id] = (ev, {})
    return ev


def resolve_pending_confirmation(tool_call_id: str, approved: bool) -> bool:
    """Устанавливает результат подтверждения для tool_call_id.

    Returns:
        True если запись найдена и event установлен.
        False если tool_call_id не найден (истёк или неизвестен).
    """
    item = _pending.get(tool_call_id)
    if item is None:
        return False
    ev, payload = item
    payload["approved"] = approved
    ev.set()
    return True


async def wait_for_confirmation(tool_call_id: str, timeout_s: float = 120.0) -> bool | None:
    """Ждёт подтверждения для tool_call_id с таймаутом.

    Returns:
        True — пользователь одобрил.
        False — пользователь отклонил.
        None — таймаут или tool_call_id не зарегистрирован.
    """
    item = _pending.get(tool_call_id)
    if item is None:
        return None
    ev, payload = item
    try:
        await asyncio.wait_for(ev.wait(), timeout=timeout_s)
        return bool(payload.get("approved", False))
    except TimeoutError:
        return None
    finally:
        _pending.pop(tool_call_id, None)
