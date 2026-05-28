"""Phantom-method detector — детерминированная анти-галлюцинация для БСП (M-K4).

Извлекает вызовы вида `Модуль.Метод(` из текста ответа LLM и сверяет с
корпусом БСП (`bsp_chunks`). Логика **corpus-relative**:

- Модуль ЕСТЬ в корпусе, но `Модуль.Метод` — НЕТ → **phantom** (выдуманная
  сигнатура: FM-1 из AI-SPEC, доминирующий тип галлюцинации кодогенерации,
  напр. `ОбщегоНазначения.ПолучитьЗначениеРеквизита()` — метода не существует).
- Модуля НЕТ в корпусе → unknown, НЕ флагаем (может быть метод кастомной
  конфигурации клиента или платформенный, а не БСП).

WHY детерминированно: проверка сигнатур не требует LLM judge — это lookup по
индексу. Используется eval-харнесом (dimension D1 в AI-SPEC) и опционально
guardrail'ом G2 (пометка ответа флагом «сигнатура не верифицирована»).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import aiosqlite

# Вызов `Идентификатор.Идентификатор(` — оба начинаются с буквы/подчёркивания
# (`[^\W\d]` = word-char, не цифра). \w в Python (str) Unicode-aware → кириллица.
_CALL_RE = re.compile(r"([^\W\d]\w*)\.([^\W\d]\w*)\s*\(")


@dataclass(frozen=True, slots=True)
class PhantomReport:
    """Результат проверки текста на фантомные методы БСП.

    checked — `Модуль.Метод`, чьи модули известны корпусу (реально проверены).
    phantom — из checked те, которых в корпусе нет (вероятная галлюцинация).
    """

    checked: tuple[str, ...]
    phantom: tuple[str, ...]

    @property
    def has_phantom(self) -> bool:
        return len(self.phantom) > 0


def extract_bsl_calls(text: str) -> list[tuple[str, str]]:
    """Все вызовы `Модуль.Метод(` в тексте (dedup, порядок появления)."""
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for match in _CALL_RE.finditer(text or ""):
        pair = (match.group(1), match.group(2))
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
    return out


async def check_phantom_methods(
    db: aiosqlite.Connection,
    text: str,
    *,
    version_filter: str | None = None,
) -> PhantomReport:
    """Проверяет упомянутые в тексте методы БСП против корпуса bsp_chunks.

    Args:
        db: aiosqlite connection (bsp_chunks доступна)
        text: текст ответа LLM
        version_filter: '3.1' | '3.2' | None — ограничить версией БСП

    Returns:
        PhantomReport. Если корпус БСП пуст — checked/phantom пустые
        (нечего сверять, не флагаем ложно).
    """
    calls = extract_bsl_calls(text)
    if not calls:
        return PhantomReport(checked=(), phantom=())

    mod_sql = "SELECT DISTINCT module_name FROM bsp_chunks"
    mod_params: tuple = ()
    if version_filter:
        mod_sql += " WHERE version = ?"
        mod_params = (version_filter,)
    cursor = await db.execute(mod_sql, mod_params)
    known_modules = {row[0] for row in await cursor.fetchall()}
    if not known_modules:
        return PhantomReport(checked=(), phantom=())

    checked: list[str] = []
    phantom: list[str] = []
    for module, method in calls:
        if module not in known_modules:
            continue  # unknown module — не БСП, не флагаем
        full = f"{module}.{method}"
        checked.append(full)
        exist_sql = "SELECT 1 FROM bsp_chunks WHERE module_name = ? AND method_name = ?"
        exist_params: tuple = (module, method)
        if version_filter:
            exist_sql += " AND version = ?"
            exist_params = (module, method, version_filter)
        exist_sql += " LIMIT 1"
        cursor = await db.execute(exist_sql, exist_params)
        if await cursor.fetchone() is None:
            phantom.append(full)

    return PhantomReport(checked=tuple(checked), phantom=tuple(phantom))
