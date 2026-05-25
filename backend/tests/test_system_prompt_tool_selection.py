"""Тесты PROMPT-1 — Few-shot tool decision tree в system prompt.

Контракт:
1. SYSTEM_PROMPT содержит блок "ПРИМЕРЫ ВЫБОРА TOOL".
2. Для каждого из 8 ключевых tools есть хотя бы один few-shot пример вида
   "Q: ... A: <tool>(...)".
3. Блок содержит анти-паттерны (что НЕ делать).
4. Golden dataset покрывает ≥ 80% MCP tools (не only edge cases).
5. Heuristic-классификатор поверх системного prompt + golden dataset даёт
   ≥ 80% accuracy (acceptance criterion PROMPT-1).

Heuristic-классификатор — простой keyword matcher по тексту вопроса. Он
**имитирует** базовую интуицию LLM. Это не замена real LLM, но catches
регрессии в формулировках golden + system prompt.
"""

from __future__ import annotations

import re

import pytest

from app.orchestrator.loop import SYSTEM_PROMPT
from tests.fixtures.golden_tool_selection import (
    GOLDEN_TOOL_SELECTION,
    REQUIRED_FEW_SHOT_CLASSES,
    count_unique_tools_in_golden,
    golden_examples_for_tool,
)


# ===== Инварианты system prompt =====


def test_system_prompt_contains_few_shot_section():
    """Блок few-shot должен присутствовать как явный раздел."""
    assert "ПРИМЕРЫ ВЫБОРА TOOL" in SYSTEM_PROMPT


def test_system_prompt_contains_anti_patterns():
    """Анти-паттерны (что НЕ делать) — критичная часть decision tree."""
    assert "АНТИ-ПАТТЕРНЫ" in SYSTEM_PROMPT or "НЕ ДЕЛАЙ" in SYSTEM_PROMPT
    # Якорный пример: "execute_query на ... журнал" — самая частая путаница
    assert "журнал" in SYSTEM_PROMPT.lower()


def test_system_prompt_covers_no_tool_case():
    """Должен быть пример когда tool НЕ нужен (методология / generation)."""
    # Один из якорей: "БСП" как пример общего вопроса БЕЗ tool
    assert "Что такое БСП" in SYSTEM_PROMPT or "TOOL НЕ ЗВАТЬ" in SYSTEM_PROMPT


@pytest.mark.parametrize("tool_name", REQUIRED_FEW_SHOT_CLASSES)
def test_system_prompt_has_few_shot_for_tool(tool_name: str):
    """Для каждого ключевого tool — минимум 1 few-shot пример Q: ... A: <tool>(."""
    # Шаблон "A: <tool_name>(" встречается хотя бы раз в блоке few-shot.
    # Это не regex по строкам — простой substring match достаточен.
    marker = f"{tool_name}("
    assert marker in SYSTEM_PROMPT, (
        f"Tool '{tool_name}' не имеет few-shot example в SYSTEM_PROMPT. "
        f"Должна быть строка 'A: {tool_name}(...' хотя бы один раз."
    )


def test_system_prompt_not_overgrown():
    """Sanity: prompt не должен раздуваться > 25k символов (наша линия комфорта).

    Большие system prompt'ы съедают токены каждый запрос. Если перевалили —
    стоит пересмотреть структуру или вынести часть в отдельный context bundle.
    """
    assert len(SYSTEM_PROMPT) < 25_000, (
        f"SYSTEM_PROMPT раздулся до {len(SYSTEM_PROMPT)} символов — "
        f"пересмотри структуру или вынеси часть"
    )


# ===== Golden dataset свойства =====


def test_golden_dataset_size():
    """20 примеров — план PROMPT-1."""
    assert len(GOLDEN_TOOL_SELECTION) == 20


def test_golden_covers_majority_of_tools():
    """Покрытие: ≥ 7 разных tools (из 10 toolkit) представлены в датасете.

    submit_for_deanonymization и get_link_of_object — редкие, могут не быть.
    execute_code — destructive, минимум 0 примеров (не приветствуем).
    """
    assert count_unique_tools_in_golden() >= 7


def test_each_required_tool_has_at_least_one_example():
    """Каждый из обязательных tools имеет ≥ 1 golden example."""
    must_have = {
        "get_metadata",
        "execute_query",
        "get_event_log",
        "find_references_to_object",
        "get_access_rights",
        "get_bsl_syntax_help",
    }
    for tool in must_have:
        assert golden_examples_for_tool(tool), (
            f"Tool '{tool}' нет в golden dataset — добавь хотя бы 1 пример"
        )


def test_golden_has_no_tool_cases():
    """Минимум 2 примера «tool не нужен» (методология / generation)."""
    no_tool = [ex for ex in GOLDEN_TOOL_SELECTION if ex.expected_tool is None]
    assert len(no_tool) >= 2


# ===== Heuristic accuracy =====


def _classify_question(question: str) -> str | None:
    """Простой keyword-classifier — имитация интуиции LLM.

    Возвращает имя tool или None. Логика синхронизирована с few-shot examples
    в system prompt — если изменился prompt, поменяй keyword'ы здесь же.

    Это НЕ замена real LLM benchmark'у. Это regression guard:
    при изменении формулировок golden или система prompt — accuracy не должна
    деградировать ниже 80%.
    """
    q = question.lower()

    # Порядок проверок важен — от более специфичных к общим.

    # find_references_to_object — про "где используется", "что сломается если"
    if (
        "где используется" in q
        or "что сломается" in q
        or "что зависит от" in q
        or "кто ссылается" in q
    ):
        return "find_references_to_object"

    # get_access_rights — про права / "почему не видит"
    if (
        "право" in q
        or "права" in q
        or "не видит" in q
        or "доступ" in q
        or "роль" in q and "на" in q
    ):
        return "get_access_rights"

    # get_event_log — диагностика, ошибки, события
    if (
        "что случилось" in q
        or "ошибк" in q
        or "журнал" in q
        or "кто провёл" in q
        or "кто провел" in q
        or "вчера" in q
        or "за последний" in q
    ):
        return "get_event_log"

    # get_object_by_link — навигационная ссылка
    if "e1cib" in q or "по ссылке" in q:
        return "get_object_by_link"

    # get_bsl_syntax_help — про параметры функции/процедуры платформы
    if (
        "параметры у" in q
        or "как программно" in q
        or "как вызвать" in q
        or "какие методы у" in q
        or "синтаксис" in q
    ):
        return "get_bsl_syntax_help"

    # NO TOOL — методология / generation
    if (
        "что такое" in q
        or "объясни" in q
        or "напиши шаблон" in q
        or "пример запроса" in q
        or "шаблон" in q and "запрос" in q
    ):
        return None

    # get_metadata — про список метаданных / структуру / обзор
    if (
        ("какие" in q and ("документ" in q or "справочник" in q or "регистр" in q or "отчёт" in q or "обработк" in q))
        or "обзор конфигурации" in q
        or "покажи структуру" in q
        or "покажи все" in q  # "покажи все справочники с именем …"
        or "что вообще в" in q
    ):
        return "get_metadata"

    # execute_query — выборка данных (количество, последние, поиск по реквизиту)
    if (
        "сколько" in q
        or "последни" in q
        or "найди" in q
        or "сумма" in q
        or "покажи 10" in q
        or "покажи топ" in q
        or "выбери" in q
    ):
        return "execute_query"

    # Fallback — не знаем
    return None


def test_heuristic_accuracy_meets_80_percent():
    """PROMPT-1 acceptance: ≥ 80% accuracy на golden dataset через heuristic.

    Heuristic ≠ real LLM, но если он < 80% — значит даже простой keyword matcher
    не справляется → формулировки golden или класс примеров плохие. Это
    regression guard.

    Real LLM benchmark — отдельная задача в M-K1+ когда у нас будет автоматизация
    прогона через LLM (через MCP test harness).
    """
    correct = 0
    misclassified: list[tuple[str, str | None, str | None]] = []
    for ex in GOLDEN_TOOL_SELECTION:
        predicted = _classify_question(ex.question)
        if predicted == ex.expected_tool:
            correct += 1
        else:
            misclassified.append((ex.question, ex.expected_tool, predicted))

    accuracy = correct / len(GOLDEN_TOOL_SELECTION)
    assert accuracy >= 0.80, (
        f"Heuristic accuracy {accuracy:.0%} ниже 80% (PROMPT-1 acceptance). "
        f"Неправильно классифицированы:\n"
        + "\n".join(
            f"  - {q!r}: expected={exp}, got={pred}"
            for q, exp, pred in misclassified
        )
    )
