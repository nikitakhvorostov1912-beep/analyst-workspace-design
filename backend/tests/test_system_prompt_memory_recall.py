"""Тесты PROMPT-3 — Memory recall trigger в system prompt.

Контракт:
1. SYSTEM_PROMPT содержит блок «ПАМЯТЬ (memory_append / memory_remove)».
2. Прописаны 4 ключевых правила: read first, when append, when NOT append, when remove.
3. Описаны namespaces (agent vs user).
4. Есть anti-patterns.
5. Golden dataset balanced (есть examples всех 4 action типов).
6. Heuristic-классификатор ≥ 80% accuracy (acceptance PROMPT-3).
"""

from __future__ import annotations

import re

import pytest

from app.orchestrator.loop import SYSTEM_PROMPT
from tests.fixtures.golden_memory_recall import (
    GOLDEN_MEMORY_RECALL,
    MemoryAction,
    count_examples_by_action,
)


# ===== Инварианты system prompt =====


def test_system_prompt_contains_memory_section():
    """Блок «ПАМЯТЬ» должен присутствовать как явный раздел."""
    assert "ПАМЯТЬ" in SYSTEM_PROMPT
    assert "memory_append" in SYSTEM_PROMPT
    assert "memory_remove" in SYSTEM_PROMPT


def test_system_prompt_covers_read_first_rule():
    """Должно явно говорить «читай память перед ответом»."""
    # Якорные фразы — любая из них означает что rule артикулирован
    markers = ["ЧИТАЙ ПАМЯТЬ", "сверься с", "<persistent-memory>"]
    assert any(m in SYSTEM_PROMPT for m in markers)


def test_system_prompt_covers_when_to_append():
    """Должно быть «когда записывать» с критериями."""
    assert "КОГДА ВЫЗЫВАТЬ memory_append" in SYSTEM_PROMPT or "ЗАПИСАТЬ ФАКТ" in SYSTEM_PROMPT
    # Намёк на критерии (переиспользуемо, не выводится из метаданных)
    assert "Переиспользуем" in SYSTEM_PROMPT or "будущих сессиях" in SYSTEM_PROMPT


def test_system_prompt_covers_when_NOT_to_append():
    """Должно быть «когда НЕ записывать» — критично, иначе LLM пишет всё подряд."""
    assert "КОГДА НЕ ВЫЗЫВАТЬ memory_append" in SYSTEM_PROMPT or "НЕ ЗАПИСЫВАТЬ" in SYSTEM_PROMPT


def test_system_prompt_covers_when_to_remove():
    """memory_remove — refresh устаревших фактов."""
    assert "КОГДА ВЫЗЫВАТЬ memory_remove" in SYSTEM_PROMPT or "memory_remove" in SYSTEM_PROMPT
    assert "забудь" in SYSTEM_PROMPT.lower() or "refresh" in SYSTEM_PROMPT.lower()


def test_system_prompt_explains_namespaces():
    """agent vs user — критично для правильной раздачи."""
    assert "agent" in SYSTEM_PROMPT
    assert "user" in SYSTEM_PROMPT
    # Один из якорей различия
    assert "окружение" in SYSTEM_PROMPT.lower() or "конвенц" in SYSTEM_PROMPT.lower()
    assert "предпочтени" in SYSTEM_PROMPT.lower()


def test_system_prompt_has_memory_anti_patterns():
    """Анти-паттерны явно прописаны."""
    assert "АНТИ-ПАТТЕРНЫ memory" in SYSTEM_PROMPT or "память не лог" in SYSTEM_PROMPT.lower()


# ===== Golden dataset свойства =====


def test_golden_memory_dataset_size():
    """15 примеров — план PROMPT-3."""
    assert len(GOLDEN_MEMORY_RECALL) == 15


def test_golden_memory_dataset_balanced():
    """Все 4 action типа представлены, ни один не >50% датасета."""
    counts = count_examples_by_action()
    for action in ("append", "remove", "read", "none"):
        assert counts[action] >= 1, f"Нет ни одного примера для action={action}"
        ratio = counts[action] / len(GOLDEN_MEMORY_RECALL)
        assert ratio <= 0.55, (
            f"Action {action} занимает {ratio:.0%} — датасет не balanced"
        )


# ===== Heuristic classifier =====


# Cross-language synonyms — англ ↔ рус общие термины которые LLM понимает,
# а простой substring match — нет (без лемматизации).
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "prefix": ("префикс",),
    "префикс": ("prefix", "префикс"),
}


def _stem(token: str, n: int = 5) -> str:
    """Грубая «лемма» = первые n символов. Покрывает русск. морфологию
    (проект→проекты→проектами→проектов имеют общий 5-char префикс «проек»)."""
    return token[:n]


def _tokens(text: str, min_len: int = 4) -> list[str]:
    return [t for t in re.split(r"\W+", text.lower()) if len(t) >= min_len]


def _has_overlap(msg: str, memory: str) -> bool:
    """Есть ли пересечение терминов между сообщением и памятью?

    Использует stem-matching (первые 5 chars) + cross-language synonyms.
    """
    if not memory:
        return False
    msg_tokens = _tokens(msg)
    memory_tokens = _tokens(memory)
    memory_stems = {_stem(t) for t in memory_tokens}
    memory_lower = memory.lower()

    for tok in msg_tokens:
        # Direct stem match
        if _stem(tok) in memory_stems:
            return True
        # Cross-language synonym
        for syn in _SYNONYMS.get(tok, ()):
            if syn in memory_lower:
                return True
    return False


def _classify_memory_action(memory_state: str, user_message: str) -> MemoryAction:
    """Простой keyword/state-based classifier — имитация поведения LLM.

    Имитирует логику из system prompt few-shot. Не замена real LLM benchmark'у —
    regression guard.
    """
    msg = user_message.lower().strip()

    # 1. REMOVE — явное "забудь" + есть пересечение с памятью
    if "забудь" in msg and memory_state:
        return "remove"

    # 1b. REFRESH (remove) — пользователь сообщает обновление факта который
    # есть в памяти. Triggers: «обновили», «теперь N», «стало», «поменялось».
    refresh_keywords = ("обновили", "теперь", "стало", "поменялось", "поменяли")
    if memory_state and any(kw in msg for kw in refresh_keywords):
        if _has_overlap(msg, memory_state):
            return "remove"

    # 2. APPEND — явный триггер сохранения
    explicit_save = ("запомни", "зафиксируй", "запиши")
    if any(kw in msg for kw in explicit_save):
        return "append"

    # 2b. APPEND — конвенция/предпочтение если НЕТ дубликата в памяти
    convention_keywords = (
        "prefix", "префикс", "по умолчанию", "у нас",
        "наш стандарт", "обычно", "всегда",
    )
    if any(kw in msg for kw in convention_keywords):
        # Дубликат? — overlap с памятью + явное упоминание prefix/конвенции там
        if memory_state and _has_overlap(msg, memory_state):
            return "none"  # дубликат
        return "append"

    # 3. READ — память не пустая И вопрос касается зафиксированного факта
    if memory_state and _has_overlap(msg, memory_state):
        return "read"

    # 4. NONE — всё остальное
    return "none"


def test_heuristic_memory_accuracy_meets_80_percent():
    """PROMPT-3 acceptance: ≥ 80% accuracy на golden dataset.

    Если меньше — формулировки few-shot в system prompt или golden плохо
    согласованы, либо heuristic нужно обновить под новые правила.
    """
    correct = 0
    misclassified: list[tuple[str, MemoryAction, MemoryAction]] = []
    for ex in GOLDEN_MEMORY_RECALL:
        predicted = _classify_memory_action(ex.memory_state, ex.user_message)
        if predicted == ex.expected_action:
            correct += 1
        else:
            misclassified.append((ex.user_message, ex.expected_action, predicted))

    accuracy = correct / len(GOLDEN_MEMORY_RECALL)
    assert accuracy >= 0.80, (
        f"Memory recall heuristic accuracy {accuracy:.0%} ниже 80% (PROMPT-3 acceptance).\n"
        + "Неправильно классифицированы:\n"
        + "\n".join(
            f"  - {q!r}: expected={exp}, got={pred}"
            for q, exp, pred in misclassified
        )
    )
