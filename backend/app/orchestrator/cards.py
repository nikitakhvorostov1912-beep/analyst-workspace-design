"""Детектор inline-карточек из tool_result."""

import json
import logging
from typing import Any, Literal

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
    columns = []
    for col in columns_raw:
        if isinstance(col, dict):
            columns.append(ColumnSchema(name=col.get("name", ""), type=col.get("type", "String")))
        elif isinstance(col, str):
            columns.append(ColumnSchema(name=col, type="String"))
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

    entries = []
    for entry in entries_raw:
        if not isinstance(entry, dict):
            continue
        try:
            entries.append(LogEntry(
                time=str(entry.get("time", "")),
                level=entry.get("level", "Info"),
                user=entry.get("user"),
                event=str(entry.get("event", "")),
                comment=entry.get("comment"),
            ))
        except Exception:
            logger.debug("Пропущена невалидная запись журнала: %s", entry)

    payload = LogCardPayload(
        entries=entries,
        next_cursor=data.get("next_cursor"),
    )
    return {"type": "log", "payload": payload.model_dump()}


# Tools для которых строим карточки
_CARD_BUILDERS = {
    "execute_query": _build_table_card,
    "get_object_by_link": _build_object_card,
    "get_event_log": _build_log_card,
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
