"""Детектор inline-карточек из tool_result."""

import json
import logging
import re
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

_ANON_TOKEN_RE = re.compile(r"\[[A-Z]+-\d+\]")

# Паттерн для поиска колонок с датой/периодом
_PERIOD_COLUMN_RE = re.compile(
    r"^(Период|Дата|Месяц|Date|Period|Day|Week|Quarter|Year)$",
    re.IGNORECASE,
)

# Порядок групп для ReferencesCard
_REFERENCE_KIND_ORDER = ["Реквизит", "Подчинённый", "Шаблон", "Подписка", "Право", "Прочее"]

logger = logging.getLogger(__name__)


class ColumnSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str


class TableCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[ColumnSchema]
    rows: list[list[Any]]
    total: int
    meta: dict[str, Any]
    card_id: str | None = None  # UUID4 для deanonymize endpoint (Plan 04-01)


class ObjectCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    header: dict[str, Any]
    attributes: list[dict[str, Any]]
    tabular_sections: list[dict[str, Any]]
    forms: list[dict[str, Any]]
    templates: list[dict[str, Any]]
    card_id: str | None = None  # UUID4 для deanonymize endpoint (Plan 04-01)


class LogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: str
    level: Literal["Info", "Warning", "Error", "Critical"]
    user: str | None = None
    event: str
    comment: str | None = None


class LogCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[LogEntry]
    next_cursor: str | None = None
    card_id: str | None = None  # UUID4 для load-more endpoint (Plan 03-04)


class SparklinePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: float


class MetricCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float | int
    label: str
    unit: str | None = None          # "₽", "шт.", "%"
    sparkline: list[SparklinePoint] | None = None
    delta: dict | None = None        # {"value": float, "direction": "up"|"down", "percent": bool}
    card_id: str | None = None


class ReferenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type: str                 # "Документ", "Справочник", "Регистр сведений"
    name: str                        # "ОПП"
    navigation_link: str | None = None  # "e1cib/data/Документ.ОПП"
    full_path: str                   # "Документ.ОПП.Реквизит.НомерТД"


class ReferenceGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str                        # "Реквизит", "Подчинённый", "Шаблон", "Подписка", "Право", "Прочее"
    items: list[ReferenceItem]


class ReferencesCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groups: list[ReferenceGroup]
    total: int
    card_id: str | None = None


class CodeCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["bsl", "sql", "json", "text"]
    code: str
    executable: bool = False         # True для execute_code, False для syntax_help
    result: dict | None = None       # для execute_code: tool_result inline
    card_id: str | None = None


def _infer_type_from_value(value: object) -> str:
    """Выводит тип колонки из значения первой строки."""
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, (int, float)):
        return "Number"
    if value is None:
        return "Null"
    return "String"


def _is_numeric_column(rows: list[list], col_idx: int) -> bool:
    """Возвращает True если все значения в колонке numeric (int/float, не None/bool)."""
    if not rows:
        return False
    for row in rows:
        if col_idx >= len(row):
            return False
        val = row[col_idx]
        # bool — подкласс int, но не считаем его числовым
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return False
    return True


def _find_period_column(columns: list[ColumnSchema]) -> int | None:
    """Ищет колонку с датой/периодом по имени. Возвращает индекс или None."""
    for idx, col in enumerate(columns):
        if _PERIOD_COLUMN_RE.match(col.name):
            return idx
    return None


def _infer_metric_unit(col_name: str) -> str | None:
    """Эвристически определяет единицу измерения из имени колонки."""
    lower = col_name.lower()
    if "руб" in lower or "₽" in lower or "сумма" in lower:
        return "₽"
    if "кол-во" in lower or "шт" in lower or "количество" in lower:
        return "шт."
    return None


# Regex для исключения ID-like колонок из MetricCard эвристики
_ID_COLUMN_RE = re.compile(r"^(id|ссылка|reference|link|код|code)$", re.IGNORECASE)


def _extract_mcp_content(result: dict) -> dict | None:
    """Распаковывает MCP-формат {content:[{type:text,text:...}]} в dict."""
    content = result.get("content")
    if not isinstance(content, list):
        return None
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text", "")
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
    return None


def _build_table_card(args: dict, result: dict) -> dict | None:
    """Строит TableCard из результата execute_query."""
    data = result if "columns" in result else _extract_mcp_content(result)
    if data is None:
        return None

    columns_raw = data.get("columns")
    rows = data.get("rows")
    if not isinstance(columns_raw, list) or not isinstance(rows, list):
        return None

    # columns может быть list[str] или list[{name, type}]
    # Если тип не указан — выводим из первой строки
    first_row = rows[0] if rows else []
    columns = []
    for idx, col in enumerate(columns_raw):
        if isinstance(col, dict):
            col_type = col.get("type") or col.get("dataType", "")
            if not col_type and idx < len(first_row):
                col_type = _infer_type_from_value(first_row[idx])
            columns.append(ColumnSchema(name=col.get("name", ""), type=col_type or "String"))
        elif isinstance(col, str):
            inferred = _infer_type_from_value(first_row[idx]) if idx < len(first_row) else "String"
            columns.append(ColumnSchema(name=col, type=inferred))
        else:
            columns.append(ColumnSchema(name=str(col), type="String"))

    payload = TableCardPayload(
        columns=columns,
        rows=rows,
        total=len(rows),
        meta={
            "query": args.get("query"),
            "duration_ms": result.get("duration_ms"),
        },
        card_id=str(uuid4()),
    )
    return {"type": "table", "payload": payload.model_dump()}


def _build_object_card(args: dict, result: dict) -> dict | None:
    """Строит ObjectCard из результата get_object_by_link или get_metadata(detail=full)."""
    data = result if "header" in result or "name" in result else _extract_mcp_content(result)
    if data is None:
        return None

    # Пробуем разобрать структуру объекта
    header = data.get("header") or {
        "name": data.get("name", ""),
        "type": data.get("type", ""),
        "path": data.get("path", ""),
    }
    payload = ObjectCardPayload(
        header=header,
        attributes=data.get("attributes", []),
        tabular_sections=data.get("tabular_sections", []),
        forms=data.get("forms", []),
        templates=data.get("templates", []),
        card_id=str(uuid4()),
    )
    return {"type": "object", "payload": payload.model_dump()}


def _build_log_card(args: dict, result: dict) -> dict | None:
    """Строит LogCard из результата get_event_log."""
    data = result if "entries" in result else _extract_mcp_content(result)
    if data is None:
        return None

    entries_raw = data.get("entries")
    if not isinstance(entries_raw, list):
        return None

    _VALID_LEVELS = {"Info", "Warning", "Error", "Critical"}
    entries = []
    for entry in entries_raw:
        if not isinstance(entry, dict):
            continue
        raw_level = entry.get("level", "Info")
        safe_level = raw_level if raw_level in _VALID_LEVELS else "Info"
        try:
            entries.append(LogEntry(
                time=str(entry.get("time", "")),
                level=safe_level,
                user=entry.get("user"),
                event=str(entry.get("event", "")),
                comment=entry.get("comment"),
            ))
        except Exception:
            logger.debug("Пропущена невалидная запись журнала: %s", entry)

    payload = LogCardPayload(
        entries=entries,
        next_cursor=data.get("next_cursor"),
        card_id=str(uuid4()),  # UUID4 для load-more endpoint
    )
    return {"type": "log", "payload": payload.model_dump()}


def _parse_mcp_text_content(result: dict) -> dict | None:
    """Псевдоним _extract_mcp_content для совместимости с планом."""
    return _extract_mcp_content(result)


def _dispatch_query_card(args: dict, result: dict) -> dict | None:
    """Диспетчер для execute_query: MetricCard (single/timeline) или TableCard."""
    data = result if "columns" in result else _extract_mcp_content(result)
    if data is None:
        return None

    columns_raw = data.get("columns")
    rows = data.get("rows")
    if not isinstance(columns_raw, list) or not isinstance(rows, list):
        return None

    # Строим список ColumnSchema для работы с helpers
    first_row = rows[0] if rows else []
    columns: list[ColumnSchema] = []
    for idx, col in enumerate(columns_raw):
        if isinstance(col, dict):
            col_type = col.get("type") or col.get("dataType", "")
            if not col_type and idx < len(first_row):
                col_type = _infer_type_from_value(first_row[idx])
            columns.append(ColumnSchema(name=col.get("name", ""), type=col_type or "String"))
        elif isinstance(col, str):
            inferred = _infer_type_from_value(first_row[idx]) if idx < len(first_row) else "String"
            columns.append(ColumnSchema(name=col, type=inferred))
        else:
            columns.append(ColumnSchema(name=str(col), type="String"))

    if not rows:
        return _build_table_card(args, data)

    # Находим numeric колонки (не ID-like)
    numeric_indices = [
        i for i in range(len(columns))
        if _is_numeric_column(rows, i) and not _ID_COLUMN_RE.match(columns[i].name)
    ]

    # Path A: single metric — 1 строка, есть numeric колонки
    if len(rows) == 1 and numeric_indices:
        first_numeric_idx = numeric_indices[0]
        value = rows[0][first_numeric_idx]
        col_name = columns[first_numeric_idx].name
        payload = MetricCardPayload(
            value=value,
            label=col_name,
            unit=_infer_metric_unit(col_name),
            sparkline=None,
            delta=None,
            card_id=str(uuid4()),
        )
        return {"type": "metric", "payload": payload.model_dump()}

    # Path B: timeline — 1 < len(rows) ≤ 100, есть period column, есть numeric
    period_idx = _find_period_column(columns)
    if 1 < len(rows) <= 100 and period_idx is not None and numeric_indices:
        # Берём первую numeric колонку, не совпадающую с period
        timeline_numeric_indices = [i for i in numeric_indices if i != period_idx]
        if timeline_numeric_indices:
            numeric_idx = timeline_numeric_indices[0]
            try:
                points = [
                    SparklinePoint(label=str(row[period_idx]), value=float(row[numeric_idx]))
                    for row in rows
                ]
            except (TypeError, ValueError):
                # Не можем построить точки — fallback на TableCard
                return _build_table_card(args, data)

            first_val = points[0].value
            last_val = points[-1].value
            diff = last_val - first_val
            direction = "up" if diff >= 0 else "down"

            delta: dict = {
                "value": diff,
                "direction": direction,
                "percent": False,
            }
            if first_val != 0:
                delta["percent_value"] = diff / abs(first_val) * 100

            col_name = columns[numeric_idx].name
            payload = MetricCardPayload(
                value=last_val,
                label=col_name,
                unit=_infer_metric_unit(col_name),
                sparkline=points,
                delta=delta,
                card_id=str(uuid4()),
            )
            return {"type": "metric", "payload": payload.model_dump()}

    # Fallback: TableCard
    return _build_table_card(args, data)


def _build_references_card(args: dict, result: dict) -> dict | None:
    """Строит ReferencesCard из результата find_references_to_object, сгруппированную по usage_kind."""
    data = result if "references" in result or "items" in result else _extract_mcp_content(result)
    if data is None:
        data = result

    refs_raw = data.get("references", data.get("items", []))

    if not isinstance(refs_raw, list) or len(refs_raw) == 0:
        return None

    # Группируем по usage_kind
    groups_dict: dict[str, list[ReferenceItem]] = {}

    for ref in refs_raw:
        if isinstance(ref, str):
            # Fallback: legacy list of strings
            kind = "Прочее"
            item = ReferenceItem(
                object_type="Объект",
                name=ref,
                navigation_link=None,
                full_path=ref,
            )
        elif isinstance(ref, dict):
            kind = ref.get("usage_kind", "Прочее") or "Прочее"
            if kind not in _REFERENCE_KIND_ORDER:
                kind = "Прочее"
            # Извлекаем object_type из full_path или явного поля
            full_path = str(ref.get("full_path", ref.get("path", "")))
            name = str(ref.get("name", ref.get("object", "")))
            # object_type: либо явно задан, либо первая часть full_path до точки
            object_type = str(ref.get("object_type", ""))
            if not object_type and "." in full_path:
                # "Документ.ОПП.Реквизит.НомерТД" → "Документ"
                object_type = full_path.split(".")[0]
            if not object_type:
                object_type = "Объект"
            item = ReferenceItem(
                object_type=object_type,
                name=name,
                navigation_link=ref.get("navigation_link"),
                full_path=full_path,
            )
        else:
            continue

        if kind not in groups_dict:
            groups_dict[kind] = []
        groups_dict[kind].append(item)

    if not groups_dict:
        return None

    # Сортируем группы в фиксированном порядке
    groups: list[ReferenceGroup] = []
    for kind in _REFERENCE_KIND_ORDER:
        if kind in groups_dict:
            groups.append(ReferenceGroup(kind=kind, items=groups_dict[kind]))

    total = sum(len(g.items) for g in groups)

    payload = ReferencesCardPayload(
        groups=groups,
        total=total,
        card_id=str(uuid4()),
    )
    return {"type": "references", "payload": payload.model_dump()}


def _detect_code_language(
    code: str,
    tool_name: str,
    explicit_lang: str | None,
) -> Literal["bsl", "sql", "json", "text"]:
    """Определяет язык кода по эвристике."""
    if explicit_lang in ("bsl", "sql", "json", "text"):
        return explicit_lang  # type: ignore[return-value]
    if tool_name == "get_bsl_syntax_help":
        return "bsl"
    stripped = code.strip()
    if re.match(r"^\s*(ВЫБРАТЬ|SELECT)\b", stripped, re.IGNORECASE):
        return "sql"
    if re.search(r"\b(Процедура|Функция|КонецПроцедуры|Если\s.*\sТогда)\b", stripped):
        return "bsl"
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    return "text"


def _build_code_card(args: dict, result: dict) -> dict | None:
    """Строит CodeCard из результата execute_code или get_bsl_syntax_help."""
    # Определяем tool по тому, что есть в args
    is_execute = "code" in args or "text" in args

    if is_execute:
        # execute_code: code из args
        code = args.get("code") or args.get("text") or ""
        result_data = _extract_mcp_content(result) or (result if isinstance(result, dict) else None)
        executable = True
    else:
        # get_bsl_syntax_help: snippet из result
        data = _extract_mcp_content(result) or result
        code = ""
        if isinstance(data, dict):
            code = str(data.get("snippet") or data.get("code") or data.get("text") or "")
        result_data = None
        executable = False

    if not code:
        return None

    # Усечение по DoS-митигации (T-04-12)
    if len(code) > 50_000:
        code = code[:50_000] + "\n...truncated"

    explicit_lang = args.get("language") if isinstance(args.get("language"), str) else None
    tool_name = "get_bsl_syntax_help" if not is_execute else "execute_code"
    language = _detect_code_language(code, tool_name, explicit_lang)

    payload = CodeCardPayload(
        language=language,
        code=code,
        executable=executable,
        result=result_data if isinstance(result_data, dict) else None,
        card_id=str(uuid4()),
    )
    return {"type": "code", "payload": payload.model_dump()}


def _extract_anon_tokens_from_payload(payload: object) -> list[str]:
    """Рекурсивно обходит payload, извлекает уникальные anon-токены.

    Поддерживает str, dict, list. Возвращает sorted unique список.
    """
    found: set[str] = set()

    def _walk(obj: object) -> None:
        if isinstance(obj, str):
            found.update(_ANON_TOKEN_RE.findall(obj))
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _walk(item)

    _walk(payload)
    return sorted(found)


# Tools для которых строим карточки
_CARD_BUILDERS = {
    "execute_query": _dispatch_query_card,
    "get_object_by_link": _build_object_card,
    "get_event_log": _build_log_card,
    "find_references_to_object": _build_references_card,
    "execute_code": _build_code_card,
    "get_bsl_syntax_help": _build_code_card,
}


def build_card_from_tool_result(
    tool_name: str,
    args: dict,
    result: dict,
) -> dict | None:
    """Строит card payload из результата tool.

    Args:
        tool_name: имя MCP-инструмента
        args: аргументы вызова
        result: результат от MCP

    Returns:
        dict с {type, payload} или None если карточка не применима.
    """
    if tool_name == "get_metadata":
        # get_metadata с detail=True/full → ObjectCard
        detail = args.get("detail", args.get("mode", ""))
        if detail in (True, "full", "attributes"):
            return _build_object_card(args, result)
        # Без detail — краткая информация, карточка не нужна
        return None

    builder = _CARD_BUILDERS.get(tool_name)
    if builder is None:
        return None

    try:
        return builder(args, result)
    except Exception:
        logger.debug("Не удалось построить карточку для %s", tool_name, exc_info=True)
        return None
