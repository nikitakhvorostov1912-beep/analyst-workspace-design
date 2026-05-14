"""Детектор inline-карточек из tool_result."""

import json
import logging
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

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


class ObjectCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    header: dict[str, Any]
    attributes: list[dict[str, Any]]
    tabular_sections: list[dict[str, Any]]
    forms: list[dict[str, Any]]
    templates: list[dict[str, Any]]


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


def _infer_type_from_value(value: object) -> str:
    """Выводит тип колонки из значения первой строки."""
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, (int, float)):
        return "Number"
    if value is None:
        return "Null"
    return "String"


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


def _build_references_card(args: dict, result: dict) -> dict | None:
    """Строит TableCard из результата find_references_to_object."""
    data = result if "rows" in result or "columns" in result else _extract_mcp_content(result)
    if data is None:
        # Если rows нет, пробуем сформировать из списка ссылок
        data = result

    rows = data.get("rows")
    if isinstance(rows, list):
        # Есть явные rows — стандартный путь через _build_table_card
        return _build_table_card(args, data)

    # Fallback: result может содержать references как list[dict]
    refs = data.get("references", data.get("items", []))
    if not isinstance(refs, list):
        return None

    columns = [
        {"name": "Объект", "type": "String"},
        {"name": "Путь", "type": "String"},
        {"name": "Представление", "type": "String"},
    ]
    built_rows = []
    for ref in refs:
        if isinstance(ref, dict):
            built_rows.append([
                str(ref.get("object", "")),
                str(ref.get("path", "")),
                str(ref.get("presentation", "")),
            ])
    constructed = {"columns": columns, "rows": built_rows}
    return _build_table_card(args, constructed)


# Tools для которых строим карточки
_CARD_BUILDERS = {
    "execute_query": _build_table_card,
    "get_object_by_link": _build_object_card,
    "get_event_log": _build_log_card,
    "find_references_to_object": _build_references_card,
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
