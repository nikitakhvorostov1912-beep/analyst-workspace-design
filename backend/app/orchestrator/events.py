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
    "tool_call_budget_exceeded",  # W1.3: per-turn MCP tool-call budget
    "duplicate_tool_loop",
    "unknown_channel",
    "init_error",
    "internal_error",
    "user_declined",
    "dangerous_keyword_blocked",
    "clarify_timeout",
    "rate_limit_exceeded",  # W1.4: /chat endpoint rate-limit (zarezервировано)
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

    type: Literal["table", "object", "log", "metric", "references", "code"]
    payload: dict[str, Any]


class DoneEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    total_duration_ms: int
    # Sprint 2 (Hermes C9): пользователь нажал «Стоп» — частичный ответ сохранён.
    interrupted: bool = False


class ErrorEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    code: ErrorCode
    retry_after_s: int | None = None


class ConfirmRequiredEvent(BaseModel):
    """SSE-событие confirm_required — запрос подтверждения опасного execute_code (SEC-01)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool_call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    args: dict[str, Any]
    reason: str = Field(min_length=1)


class ClarifyRequiredEvent(BaseModel):
    """Sprint 4 (Hermes D1): SSE-событие clarify_required — LLM просит уточнения.

    Frontend рисует radio (если multi=false) или checkbox-список (multi=true),
    дополнительно кнопку «Свой ответ». Юзер выбирает → POST /chat/clarify
    с {clarify_id, answer}. Loop получает ответ и возвращает в LLM как tool result.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    clarify_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    options: list[str]
    multi: bool = False
    allow_custom: bool = True


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
