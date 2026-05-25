"""Golden dataset для PROMPT-3 — Memory recall trigger.

15 типовых ситуаций «пользователь сказал X / память содержит Y» + expected
action (read/append/remove/none). Используется test_system_prompt_memory_recall.py.

Цель: ≥ 80% accuracy на golden dataset (12 из 15 правильно).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MemoryAction = Literal["append", "remove", "read", "none"]


@dataclass(frozen=True)
class MemoryGoldenExample:
    """Один кейс: что в памяти + что сказал пользователь → ожидаемое действие."""

    memory_state: str  # содержимое <persistent-memory> блока (или '' если пусто)
    user_message: str
    expected_action: MemoryAction
    rationale: str


GOLDEN_MEMORY_RECALL: tuple[MemoryGoldenExample, ...] = (
    # === APPEND — явный триггер от пользователя ===
    MemoryGoldenExample(
        memory_state="",
        user_message="Запомни: эта база — копия продакшена, любые мутации запрещены",
        expected_action="append",
        rationale="Явный 'запомни' + переиспользуемый факт о режиме базы",
    ),
    MemoryGoldenExample(
        memory_state="",
        user_message="У нас prefix всех новых объектов — РТ_, не АП_",
        expected_action="append",
        rationale="Конвенция проекта — записать в agent namespace",
    ),
    MemoryGoldenExample(
        memory_state="",
        user_message="По умолчанию смотрю данные за последние 30 дней",
        expected_action="append",
        rationale="Личное предпочтение → user namespace",
    ),
    MemoryGoldenExample(
        memory_state="",
        user_message="Зафиксируй: версия БСП в этой базе — 3.1.12",
        expected_action="append",
        rationale="Конкретная версия + переиспользуемо",
    ),
    # === REMOVE — явный refresh ===
    MemoryGoldenExample(
        memory_state="Префикс новых объектов — АП_",
        user_message="Забудь про prefix АП_, теперь у нас РТ_",
        expected_action="remove",
        rationale="Явное 'забудь' + есть устаревшая запись в памяти",
    ),
    MemoryGoldenExample(
        memory_state="БСП версия в базе — 3.1.10",
        user_message="Обновили БСП, теперь 3.1.12 (только что узнал из метаданных)",
        expected_action="remove",
        rationale="Refresh устаревшей записи + добавить новую",
    ),
    # === READ — память содержит ответ ===
    MemoryGoldenExample(
        memory_state="База ut_rt_copy — копия Русского Транзита, read-only",
        user_message="можно ли в этой базе изменить документ?",
        expected_action="read",
        rationale="Ответ уже в памяти — использовать, не переспрашивать",
    ),
    MemoryGoldenExample(
        memory_state="Префикс новых объектов — РТ_",
        user_message="каким префиксом мне назвать новый общий модуль?",
        expected_action="read",
        rationale="Конвенция в памяти — отвечать на её основе",
    ),
    MemoryGoldenExample(
        memory_state="Пользователь работает с 4 проектами параллельно (Транзит, УСО, ERP-Век, КА2)",
        user_message="у меня сейчас несколько проектов в работе",
        expected_action="read",
        rationale="Перечень уже сохранён — сослаться, не переспрашивать",
    ),
    # === NONE — сиюминутный/очевидный/диалоговый факт ===
    MemoryGoldenExample(
        memory_state="",
        user_message="Покажи последние 10 документов реализации",
        expected_action="none",
        rationale="Сиюминутный запрос данных — не факт для памяти",
    ),
    MemoryGoldenExample(
        memory_state="",
        user_message="Сколько контрагентов в базе?",
        expected_action="none",
        rationale="Текущая выборка — get_metadata/execute_query, не память",
    ),
    MemoryGoldenExample(
        memory_state="",
        user_message="Что такое БСП?",
        expected_action="none",
        rationale="Общее объяснение — ответ из знаний без сохранения",
    ),
    MemoryGoldenExample(
        memory_state="",
        user_message="Найди ошибки за вчера",
        expected_action="none",
        rationale="Сиюминутная диагностика — get_event_log без сохранения",
    ),
    # === NONE — дубликат в памяти, не дублируем ===
    MemoryGoldenExample(
        memory_state="Префикс новых объектов — РТ_",
        user_message="кстати, prefix у нас РТ_",
        expected_action="none",
        rationale="Дубликат уже существующей записи — не дублировать",
    ),
    MemoryGoldenExample(
        memory_state="",
        user_message="сейчас 16:30",
        expected_action="none",
        rationale="Сиюминутный факт — не записывать",
    ),
)


def count_examples_by_action() -> dict[MemoryAction, int]:
    """Распределение по action — для проверки balanced dataset."""
    counts: dict[MemoryAction, int] = {"append": 0, "remove": 0, "read": 0, "none": 0}
    for ex in GOLDEN_MEMORY_RECALL:
        counts[ex.expected_action] += 1
    return counts
