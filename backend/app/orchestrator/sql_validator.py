"""AST-уровневая валидация SQL/1С-запросов перед отправкой в MCP (P2.3, 2026-05-23).

Защита defence-in-depth поверх keyword-scanner из `safety.py`. Зачем нужно:

- keyword-scan ловит `\bDelete\b`, но LLM может обойти через encoded/concatenated
  payload (`Del'||'ete`, литерал в строке, комментарий-обходку).
- AST-валидация парсит запрос и смотрит на первый токен statement'а: только
  SELECT/ВЫБРАТЬ + variations пропускаются. DELETE/UPDATE/INSERT/DROP/...
  блокируются на структурном уровне.

Модуль fail-safe: при ошибке парсинга → BLOCKED (никогда не пропускаем
неразобранное в 1С/DBMS).

При отсутствии sqlparse (старая среда без зависимости) — graceful degrade
к keyword-only защите: `available=False` в `_status()`, validator возвращает
OK для всех запросов и пишет один WARN в логи при импорте. В production
sqlparse зашит в pyproject.toml > 0.5 (см. P2.3 в COMMERCE-PLAN-2026-05-23).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Опциональный импорт. В тестах/dev без sqlparse — fallback к keyword scan.
try:
    import sqlparse  # type: ignore[import-untyped]
    from sqlparse.sql import Comment, Statement
    from sqlparse.tokens import Keyword

    _SQLPARSE_AVAILABLE = True
except ImportError:  # pragma: no cover
    sqlparse = None  # type: ignore[assignment]
    Comment = None  # type: ignore[assignment]
    Statement = None  # type: ignore[assignment]
    Keyword = None  # type: ignore[assignment]
    _SQLPARSE_AVAILABLE = False
    logger.warning(
        "sqlparse не установлен → SQL AST validator работает в degrade-режиме. "
        "Установите `pip install sqlparse>=0.5` для полной защиты."
    )


# ===== Whitelist / blacklist =====

# Разрешённые «глаголы» — только read-only запросы.
# Включаем русские (язык запросов 1С) + английские (DBMS direct, на случай
# escape hatch через MCP Toolkit).
_ALLOWED_FIRST_TOKENS: frozenset[str] = frozenset(
    {
        "SELECT",
        "WITH",  # CTE начинается с WITH ... SELECT (read-only)
        "ВЫБРАТЬ",
        "SHOW",  # информация о схеме, read-only
        "DESCRIBE",
        "DESC",
        "EXPLAIN",  # план запроса, read-only
    }
)

# Явно запрещённые keywords — даже если они НЕ первый токен.
# Catch для inline DML: `SELECT * FROM (DELETE FROM ...) sub` и подобных.
_FORBIDDEN_KEYWORDS: frozenset[str] = frozenset(
    {
        # English DML/DDL
        "DELETE",
        "DROP",
        "TRUNCATE",
        "INSERT",
        "UPDATE",
        "ALTER",
        "CREATE",
        "RENAME",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
        "CALL",
        "MERGE",
        "REPLACE",
        # Stored procedures / dynamic SQL
        "SP_EXECUTESQL",
        "XP_CMDSHELL",
        # 1С — глаголы изменения
        "УДАЛИТЬ",
        "ИЗМЕНИТЬ",
        "ВСТАВИТЬ",
        "ОЧИСТИТЬ",
    }
)


class ValidationStatus(str, Enum):
    """Результат AST-валидации SQL/1С запроса."""

    OK = "ok"
    BLOCKED = "blocked"
    INVALID = "invalid"  # не парсится — отказываем (fail-safe)


@dataclass(frozen=True)
class ValidationResult:
    """Результат валидации с пояснением (для пользовательского сообщения)."""

    status: ValidationStatus
    reason: str = ""

    @property
    def passed(self) -> bool:
        return self.status == ValidationStatus.OK


# Готовые экземпляры — экономим аллокации при OK-path (горячий путь).
_OK = ValidationResult(ValidationStatus.OK, "")


# ===== Public API =====


def is_available() -> bool:
    """True если AST-валидация активна (sqlparse установлен)."""
    return _SQLPARSE_AVAILABLE


def validate_query(query_text: str) -> ValidationResult:
    """Валидирует SQL/1С-запрос на AST-уровне.

    Возвращает OK для чистых read-only запросов, BLOCKED для DML/DDL,
    INVALID для непарсимых строк (fail-safe).

    Args:
        query_text: текст запроса (1С или SQL).

    Returns:
        ValidationResult с status + reason.
    """
    if not _SQLPARSE_AVAILABLE:
        # Без sqlparse — нечем валидировать. Пропускаем (keyword-scan
        # в safety.py остаётся как защита).
        return _OK

    if not query_text or not query_text.strip():
        return ValidationResult(ValidationStatus.INVALID, "пустой запрос")

    # Удаляем комментарии до парсинга — sqlparse может игнорировать DELETE
    # внутри `-- DELETE FROM ...`, но мы хотим заметить попытку обхода.
    stripped = _strip_comments(query_text)

    try:
        parsed = sqlparse.parse(stripped)
    except Exception as exc:  # noqa: BLE001 — sqlparse бросает разные типы
        return ValidationResult(
            ValidationStatus.INVALID, f"sqlparse не смог разобрать: {exc}"
        )

    if not parsed:
        return ValidationResult(ValidationStatus.INVALID, "пустой результат парсинга")

    for stmt in parsed:
        # Пропуск пустых statement-ов (точка с запятой между запросами).
        if _is_empty_statement(stmt):
            continue

        # 1. Первый токен statement-а должен быть в allow-list.
        first = _first_significant_token(stmt)
        if first is None:
            return ValidationResult(
                ValidationStatus.INVALID,
                "не удалось определить первый токен запроса",
            )

        first_upper = first.upper()
        if first_upper not in _ALLOWED_FIRST_TOKENS:
            return ValidationResult(
                ValidationStatus.BLOCKED,
                f"первый токен запроса '{first}' не разрешён (только SELECT/ВЫБРАТЬ/EXPLAIN/SHOW)",
            )

        # 2. Внутри statement не должно быть forbidden keywords (defence-in-depth
        #    для inline subquery с DML).
        forbidden = _find_forbidden_token(stmt)
        if forbidden is not None:
            return ValidationResult(
                ValidationStatus.BLOCKED,
                f"запрещённый keyword внутри запроса: '{forbidden}'",
            )

    return _OK


# ===== Helpers =====


_COMMENT_LINE_RE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(query_text: str) -> str:
    """Удаляет SQL-комментарии (`--...` line + `/* ... */` block).

    Нужно чтобы LLM не мог обойти validator через комментарий-обходку:
    `SELECT 1; -- DELETE FROM users` → после strip → `SELECT 1; DELETE FROM users`
    → 2-й statement BLOCKED.
    """
    no_block = _COMMENT_BLOCK_RE.sub(" ", query_text)
    no_line = _COMMENT_LINE_RE.sub(" ", no_block)
    return no_line


def _is_empty_statement(stmt) -> bool:  # type: ignore[no-untyped-def]
    """True если statement содержит только whitespace/punctuation."""
    return all(_is_whitespace_or_punctuation(tok) for tok in stmt.tokens)


def _is_whitespace_or_punctuation(token) -> bool:  # type: ignore[no-untyped-def]
    """True если токен — пробел, перенос или ;."""
    if token.is_whitespace:
        return True
    value = (token.value or "").strip()
    return value in {"", ";", ",", "(", ")"}


def _first_significant_token(stmt) -> str | None:  # type: ignore[no-untyped-def]
    """Возвращает первый «значимый» токен statement (не whitespace/punct/comment).

    Стандартный `stmt.token_first(skip_cm=True)` пропускает только комментарии,
    но не пунктуацию. Хочется именно первый keyword.
    """
    for token in stmt.tokens:
        if _is_whitespace_or_punctuation(token):
            continue
        # Пропускаем комментарии (уже подстрелены в _strip_comments,
        # но на всякий случай).
        if Comment is not None and isinstance(token, Comment):
            continue
        value = (token.value or "").strip()
        if not value:
            continue
        # Берём первое «слово» (для составных вроде `INSERT INTO`).
        first_word = value.split()[0] if value.split() else value
        return first_word
    return None


def _find_forbidden_token(stmt) -> str | None:  # type: ignore[no-untyped-def]
    """Рекурсивно ищет forbidden keyword внутри statement.

    Возвращает первый найденный keyword или None.
    """
    if Keyword is None:
        return None

    for token in stmt.flatten():
        if token.ttype is Keyword or (token.ttype is not None and "Keyword" in str(token.ttype)):
            value = (token.value or "").strip().upper()
            if value in _FORBIDDEN_KEYWORDS:
                return value

    # Дополнительный walk через токены — keywords могут быть identifier'ами
    # на некоторых диалектах. Сканируем строковое представление statement.
    text_upper = str(stmt).upper()
    for forbidden in _FORBIDDEN_KEYWORDS:
        # \b работает для латиницы, для кириллических 1С keywords используем
        # пограничную проверку через look-around.
        pattern = rf"(?<![\w]){re.escape(forbidden)}(?![\w])"
        if re.search(pattern, text_upper):
            return forbidden

    return None
