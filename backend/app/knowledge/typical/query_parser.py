"""BSL Query Language parser — regex-извлечение через text scanning.

Парсит:
1. Строковые литералы внутри BSL тел методов, которые выглядят как
   запросы (содержат `ВЫБРАТЬ` / `SELECT`).
2. Сами тексты запросов — таблицы / виртуальные таблицы / параметры /
   временные таблицы.

## Что в зоне ответственности

| Что | Способ |
|---|---|
| Извлечение query литералов из BSL метода | regex по `"..."` и склейка через `+` |
| Tables из `ИЗ` / `СОЕДИНЕНИЕ <X>` | regex `(ИЗ|СОЕДИНЕНИЕ)\\s+([\\w.]+)` |
| Виртуальные таблицы регистров | regex `(РегистрХ)\\.(\\w+)\\.(Остатки|...)\\s*\\(.*?\\)` |
| Параметры `&Параметр` | regex `&(\\w+)` |
| ВТ через `ПОМЕСТИТЬ` | regex `ПОМЕСТИТЬ\\s+(ВТ_\\w+)` |

## Чего НЕ делает

- AST с группировкой/сортировкой/итогами — Phase 4 если потребуется
- SQL injection sanity check — это работа SQL validator'а в orchestrator
- Параметры внутри виртуальной таблицы (`Остатки(&Период, Склад=&Склад)`)
  — храним сырой текст в parameters_raw, разбираем при необходимости

## Edge cases

- Многострочные запросы со склейкой через `+`: «ВЫБРАТЬ» + Символы.ПС + «Поле»
- Запросы как параметр функции: `НовыйЗапрос("ВЫБРАТЬ ...")`
- Запросы через `УстановитьТекст` / `Текст = ` присваивание
- Comment в запросе через `//` (БСП-стиль)
"""

from __future__ import annotations

import logging
import re
from typing import Iterable

from app.knowledge.typical.query_models import (
    BSLQuery,
    TableReference,
    VirtualTableReference,
    _normalize_virtual_kind,
    is_register_type_name,
)

logger = logging.getLogger(__name__)


# ── Литералы из BSL ──────────────────────────────────────────────────


# Строковый литерал BSL: "..." с экранированием `""` (двойные кавычки внутри).
# Многострочные строки в BSL — это серия литералов, склеенных через `+` и
# `|` continuation на следующих строках (специфика 1С). Регулярка ловит
# одну запись на физическом уровне; склейка идёт отдельно.
_STRING_LITERAL_RE = re.compile(r'"((?:[^"]|"")*)"', re.DOTALL)


# Маркер что строка — это запрос: содержит ключевые слова BSL Query Language.
_QUERY_MARKER_RE = re.compile(
    r"\b(ВЫБРАТЬ|SELECT|УНИЧТОЖИТЬ|DROP)\b",
    re.IGNORECASE,
)


def extract_query_strings(bsl_source: str) -> list[tuple[str, int]]:
    """Возвращает все строки, похожие на запросы, и их line_start.

    Склеивает соседние строковые литералы через `+` (типичный BSL paтtern
    многострочных запросов). Возвращает уникальные строки запросов.

    Output: list of (query_text, line_in_source).
    """
    if not bsl_source:
        return []

    results: list[tuple[str, int]] = []
    # Простой подход: пройтись построчно, считая `"..."` фрагменты.
    # Склейка через `+` детектится по наличию `+` в исходнике между концом
    # одного литерала и началом следующего (whitespace + `+` + whitespace).
    pos = 0
    current_text_parts: list[str] = []
    current_start_line: int | None = None
    src = bsl_source

    while pos < len(src):
        # Ищем следующий строковый литерал
        m = _STRING_LITERAL_RE.search(src, pos)
        if m is None:
            break

        literal_text = m.group(1).replace('""', '"')
        literal_start = m.start()
        literal_end = m.end()
        line = src.count("\n", 0, literal_start) + 1

        # Что между предыдущей строкой и этой?
        if current_text_parts:
            # Промежуток между концом предыдущего литерала и началом этого
            gap_text = src[pos:literal_start]
            # Допустимо: whitespace + `+` + whitespace + ;/новая строка
            # Если в gap есть только `+`/whitespace/newlines — продолжаем склейку
            cleaned_gap = re.sub(r"\s+", "", gap_text)
            if cleaned_gap == "+":
                current_text_parts.append(literal_text)
                pos = literal_end
                continue
            # Иначе текущий блок завершился — финализируем
            joined = "".join(current_text_parts)
            if _QUERY_MARKER_RE.search(joined):
                results.append((joined, current_start_line or line))
            current_text_parts = []
            current_start_line = None

        # Начинаем новый блок
        current_text_parts = [literal_text]
        current_start_line = line
        pos = literal_end

    # Финализируем последний накопленный блок
    if current_text_parts:
        joined = "".join(current_text_parts)
        if _QUERY_MARKER_RE.search(joined):
            results.append((joined, current_start_line or 1))

    return results


# ── Парсинг отдельного запроса ───────────────────────────────────────


# `ИЗ <Таблица>` / `ВНУТРЕННЕЕ СОЕДИНЕНИЕ <Таблица>` / `ЛЕВОЕ СОЕДИНЕНИЕ <Таблица>` / etc
_TABLE_FROM_RE = re.compile(
    r"\b(?:ИЗ|FROM|"
    r"ВНУТРЕННЕЕ\s+СОЕДИНЕНИЕ|INNER\s+JOIN|"
    r"ЛЕВОЕ\s+СОЕДИНЕНИЕ|LEFT\s+(?:OUTER\s+)?JOIN|"
    r"ПРАВОЕ\s+СОЕДИНЕНИЕ|RIGHT\s+(?:OUTER\s+)?JOIN|"
    r"ПОЛНОЕ\s+СОЕДИНЕНИЕ|FULL\s+(?:OUTER\s+)?JOIN|"
    r"КРОСС\s+СОЕДИНЕНИЕ|CROSS\s+JOIN)\s+"
    r"([\w.]+(?:\s*\([^)]*\))?)"
    r"(?:\s+(?:КАК|AS)\s+(\w+))?",
    re.IGNORECASE,
)

# Виртуальные таблицы регистров с разбором аргументов
_VIRTUAL_TABLE_RE = re.compile(
    r"\b(РегистрНакопления|РегистрСведений|РегистрБухгалтерии|РегистрРасчета|"
    r"AccumulationRegister|InformationRegister|AccountingRegister|"
    r"CalculationRegister)"
    r"\.(\w+)"
    r"\.(Остатки|Обороты|ОстаткиИОбороты|СрезПоследних|СрезПервых|"
    r"ОборотыДтКт|ДвиженияССубконто|ДанныеГрафика|ФактическийПериодДействия|"
    r"БазаЗначений)"
    r"\s*\(([^)]*)\)"
    r"(?:\s+(?:КАК|AS)\s+(\w+))?",
    re.IGNORECASE | re.DOTALL,
)

# Параметры `&Имя`
_PARAMETER_RE = re.compile(r"&(\w+)")

# Временные таблицы через ПОМЕСТИТЬ ВТ_X
_PUT_TEMP_TABLE_RE = re.compile(
    r"\bПОМЕСТИТЬ\s+(\w+)", re.IGNORECASE
)

# УНИЧТОЖИТЬ ВТ_X — для destroy queries
_DESTROY_TEMP_RE = re.compile(
    r"\bУНИЧТОЖИТЬ\s+(\w+)", re.IGNORECASE
)


def parse_query(
    query_text: str,
    *,
    source_method: str | None = None,
    source_line: int | None = None,
) -> BSLQuery:
    """Разбирает текст запроса в BSLQuery.

    Регулярки нечувствительны к регистру (BSL Query Language
    case-insensitive). Дубликаты дедуплицируются.
    """
    if not query_text:
        return BSLQuery(text="")

    # Убираем построчные `// comment` — БСП-стиль комментов в запросах.
    cleaned = re.sub(r"//[^\n]*", "", query_text)

    # Виртуальные таблицы (перебираем первыми, чтобы исключить из tables_from)
    virtual_tables_raw: list[VirtualTableReference] = []
    consumed_spans: list[tuple[int, int]] = []
    for m in _VIRTUAL_TABLE_RE.finditer(cleaned):
        reg_type, reg_name, vt_kind, params_raw, alias = m.group(1, 2, 3, 4, 5)
        virtual_tables_raw.append(
            VirtualTableReference(
                register_type=reg_type,
                register_name=reg_name,
                virtual_kind=_normalize_virtual_kind(vt_kind),
                parameters_raw=params_raw.strip(),
                alias=alias,
            )
        )
        consumed_spans.append(m.span())

    # Физические таблицы (ИЗ / СОЕДИНЕНИЕ)
    tables_raw: list[TableReference] = []
    for m in _TABLE_FROM_RE.finditer(cleaned):
        # Пропускаем если попадает в span виртуальной таблицы
        start, end = m.span()
        if any(cs <= start < ce for cs, ce in consumed_spans):
            continue
        table_name, alias = m.group(1, 2)
        # Виртуальная таблица могла попасть в этот regex (в group 1 будет
        # `РегистрНакопления.X.Остатки(...)`) — фильтруем
        if "(" in table_name:
            # обрезаем до скобки — это РегистрХ.Y.Метод
            head = table_name.split("(", 1)[0].strip()
            parts = head.split(".")
            if len(parts) >= 2 and is_register_type_name(parts[0]):
                # уже захвачено как virtual table, пропускаем
                continue
            table_name = head

        is_temp = table_name.startswith("ВТ_") or table_name.startswith("VT_")
        tables_raw.append(
            TableReference(
                name=table_name,
                alias=alias,
                is_temp_table=is_temp,
            )
        )

    # Параметры
    parameters = sorted({m.group(1) for m in _PARAMETER_RE.finditer(cleaned)})

    # ПОМЕСТИТЬ ВТ_X
    temp_created = sorted({m.group(1) for m in _PUT_TEMP_TABLE_RE.finditer(cleaned)})

    # Уничтожение ВТ
    is_destroy = bool(_DESTROY_TEMP_RE.search(cleaned))

    # is_select — есть ли ВЫБРАТЬ / SELECT
    is_select = bool(re.search(r"\bВЫБРАТЬ\b|\bSELECT\b", cleaned, re.IGNORECASE))

    # temp_tables_read — taables что начинаются с ВТ_ и НЕ в temp_created
    temp_read = sorted(
        {t.name for t in tables_raw if t.is_temp_table and t.name not in temp_created}
    )

    # Дедуплицируем tables (по name)
    seen_names: set[str] = set()
    deduped_tables: list[TableReference] = []
    for t in tables_raw:
        if t.name not in seen_names:
            seen_names.add(t.name)
            deduped_tables.append(t)

    # Дедуплицируем virtual_tables (по qualified_name + virtual_kind)
    seen_vt: set[tuple[str, str]] = set()
    deduped_vt: list[VirtualTableReference] = []
    for vt in virtual_tables_raw:
        key = (vt.qualified_name, vt.virtual_kind)
        if key not in seen_vt:
            seen_vt.add(key)
            deduped_vt.append(vt)

    return BSLQuery(
        text=query_text,
        tables=tuple(deduped_tables),
        virtual_tables=tuple(deduped_vt),
        parameters=tuple(parameters),
        temp_tables_created=tuple(temp_created),
        temp_tables_read=tuple(temp_read),
        is_select=is_select,
        is_destroy_temp=is_destroy,
        source_method=source_method,
        source_line=source_line,
    )


# ── Объединённый pipeline ────────────────────────────────────────────


def extract_queries_from_method(
    method_body: str,
    *,
    source_method: str | None = None,
    method_line_offset: int = 0,
) -> list[BSLQuery]:
    """Полный pipeline: извлечь все запросы из тела метода + разобрать.

    `method_line_offset` — линия начала метода в модуле, для коррекции
    `source_line` в BSLQuery (чтобы линии относились к файлу, а не
    к телу).
    """
    queries: list[BSLQuery] = []
    for text, line in extract_query_strings(method_body):
        q = parse_query(
            text,
            source_method=source_method,
            source_line=line + method_line_offset,
        )
        queries.append(q)
    return queries


def iter_queries_from_methods(
    methods: Iterable[Any],
) -> Iterable[BSLQuery]:
    """Удобная обёртка для пакетного разбора всех методов BSLModule.

    `methods` — итерируется как list[BSLMethod] (с .body_source / .name /
    .line_start). Возвращает плоский поток BSLQuery.
    """
    for method in methods:
        body = getattr(method, "body_source", "")
        if not body:
            continue
        offset = getattr(method, "line_start", 1) - 1
        yield from extract_queries_from_method(
            body,
            source_method=getattr(method, "name", None),
            method_line_offset=offset,
        )
