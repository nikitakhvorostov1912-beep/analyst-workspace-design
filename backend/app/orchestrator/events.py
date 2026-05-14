"""Pydantic-модели SSE-событий и сериализатор в wire-формат."""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Все легитимные коды ошибок SSE.
# Plan 3.2 добавляет user_declined/dangerous_keyword_blocked — они уже здесь.
ErrorCode = Literal[
    "llm_rate_limit",
    "llm_invalid_key",
    "llm_network_error",
    "llm_server_error",
    "mcp_disconnected",
    "mcp_connect_error",
    "tool_loop_limit",
    "unknown_channel",
    "init_error",
    "internal_error",
    "user_declined",
    "dangerous_keyword_blocked",
]


class StatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["thinking", "calling_tool", "formatting"]


class ToolCallEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    args: dict[str, Any]


class ToolResultEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ok: bool
    result: Any = None
    error: str | None = None
    duration_ms: int


class DeltaEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str


class CardEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["table", "object", "log"]
    payload: dict[str, Any]


class DoneEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    total_duration_ms: int


class ErrorEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    code: ErrorCode
    retry_after_s: int | None = None


def format_sse(event_name: str, data: BaseModel | dict) -> str:
    """Сериализует SSE-событие в wire-формат.

    Формат: event: <name>\ndata: <json>\n\n
    Один event = одна строка data: (компактный JSON).
    """
    if isinstance(data, BaseModel):
        json_str = data.model_dump_json(by_alias=False)
    else:
        json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {json_str}\n\n"
