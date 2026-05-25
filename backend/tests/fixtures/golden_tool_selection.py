"""Golden dataset для PROMPT-1 — tool selection accuracy.

20 типовых вопросов аналитика 1С + expected tool. Используется:
1. Юнит-тестом который проверяет что system prompt содержит few-shot для каждого
   класса вопросов (см. test_system_prompt_tool_selection.py).
2. Эталонной табличкой для ручной валидации после изменения system prompt.
3. (M-K1+) для acceptance test через реальный LLM на benchmark прогоне.

Цель: ≥ 80% accuracy на golden dataset (16 из 20 правильно). Это **acceptance
criterion для PROMPT-1**, см. .planning/.../M-K0-stabilization/STATE.md.

Каждый запись: (вопрос, expected_tool, обоснование). Tool — имя из 10 MCP
toolkit tools, либо `null` если правильный ответ — НЕ звать tool (методология).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenExample:
    question: str
    expected_tool: str | None  # None = ответ из знаний без tool
    rationale: str


GOLDEN_TOOL_SELECTION: tuple[GoldenExample, ...] = (
    # === get_metadata (структура) ===
    GoldenExample(
        question="Какие документы есть в базе?",
        expected_tool="get_metadata",
        rationale="Структура — get_metadata(meta_type='Документ'), не выборка данных",
    ),
    GoldenExample(
        question="Покажи все справочники с именем Контр",
        expected_tool="get_metadata",
        rationale="Поиск по имени метаданных — get_metadata + name_mask",
    ),
    GoldenExample(
        question="Какие регистры накопления есть?",
        expected_tool="get_metadata",
        rationale="meta_type='РегистрНакопления'",
    ),
    GoldenExample(
        question="Сделай обзор конфигурации этой базы",
        expected_tool="get_metadata",
        rationale="Множественные get_metadata по ключевым meta_type, не execute_query",
    ),
    # === execute_query (данные) ===
    GoldenExample(
        question="Сколько контрагентов в базе?",
        expected_tool="execute_query",
        rationale="Агрегат COUNT по данным — execute_query, не get_metadata",
    ),
    GoldenExample(
        question="Покажи последние 10 реализаций",
        expected_tool="execute_query",
        rationale="Выборка строк из документов с лимитом",
    ),
    GoldenExample(
        question="Найди контрагента по ИНН 7707083893",
        expected_tool="execute_query",
        rationale="Параметризованный поиск по реквизиту",
    ),
    GoldenExample(
        question="Сумма продаж за январь по контрагенту X",
        expected_tool="execute_query",
        rationale="Агрегация с фильтром — запрос с группировкой",
    ),
    # === get_event_log (диагностика) ===
    GoldenExample(
        question="Что случилось вчера с базой?",
        expected_tool="get_event_log",
        rationale="Журнал регистрации — get_event_log с фильтром по времени",
    ),
    GoldenExample(
        question="Были ли ошибки за последний час?",
        expected_tool="get_event_log",
        rationale="severity=['Ошибка'] + date range",
    ),
    GoldenExample(
        question="Кто провёл документ Реализация-001 20.04?",
        expected_tool="get_event_log",
        rationale="event_name=['_$Data$_.Post'] + metadata filter",
    ),
    # === find_references_to_object (зависимости) ===
    GoldenExample(
        question="Где используется справочник Контрагенты?",
        expected_tool="find_references_to_object",
        rationale="Анализ метаданных-зависимостей, не выборка данных",
    ),
    GoldenExample(
        question="Что сломается если переименовать реквизит Сумма у документа Реализация?",
        expected_tool="find_references_to_object",
        rationale="Impact analysis по object_path реквизита",
    ),
    # === get_access_rights (права) ===
    GoldenExample(
        question="Какие права у роли БухгалтерУчёт на документы Реализация?",
        expected_tool="get_access_rights",
        rationale="Права — отдельный API, не таблица в БД",
    ),
    GoldenExample(
        question="Почему пользователь Иванов не видит документ X?",
        expected_tool="get_access_rights",
        rationale="Сначала get_access_rights для user+object, потом анализ ограничений",
    ),
    # === get_bsl_syntax_help (справочник) ===
    GoldenExample(
        question="Какие параметры у ОбщегоНазначения.ЗначениеРеквизитаОбъекта?",
        expected_tool="get_bsl_syntax_help",
        rationale="Документация платформы, не execute_code",
    ),
    GoldenExample(
        question="Как программно открыть форму?",
        expected_tool="get_bsl_syntax_help",
        rationale="Справочная информация по API платформы",
    ),
    # === get_object_by_link (навигация) ===
    GoldenExample(
        question="Что лежит по ссылке e1cib/data/Документ.Реализация?ref=abc",
        expected_tool="get_object_by_link",
        rationale="Прямой переход по навигационной ссылке",
    ),
    # === НЕТ tool (методология / generation) ===
    GoldenExample(
        question="Что такое БСП в 1С?",
        expected_tool=None,
        rationale="Методологический вопрос — ответ из общих знаний",
    ),
    GoldenExample(
        question="Напиши шаблон запроса для остатков по складу",
        expected_tool=None,
        rationale="Code generation — готовый шаблон в ответе, без tool вызова",
    ),
)


# Классы вопросов которые должны быть покрыты few-shot examples в system prompt.
# Используется test_system_prompt_tool_selection.py для контракт-теста.
REQUIRED_FEW_SHOT_CLASSES: tuple[str, ...] = (
    "get_metadata",
    "execute_query",
    "execute_code",
    "get_event_log",
    "find_references_to_object",
    "get_access_rights",
    "get_bsl_syntax_help",
    "get_object_by_link",
)


def count_unique_tools_in_golden() -> int:
    """Сколько разных tools покрыто в golden dataset (для метрики покрытия)."""
    return len({ex.expected_tool for ex in GOLDEN_TOOL_SELECTION if ex.expected_tool})


def golden_examples_for_tool(tool_name: str) -> tuple[GoldenExample, ...]:
    """Все примеры для конкретного tool."""
    return tuple(ex for ex in GOLDEN_TOOL_SELECTION if ex.expected_tool == tool_name)
