from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    session_id: str | None = None
    channel_id: str = Field(min_length=1)
    # api key пробрасывается через header X-LLM-API-Key, в теле НЕ передаётся


class ChatSSEEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: str
    data: dict


class MCPPingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mcp_version: str
    tool_count: int
    session_id: str
    duration_ms: int


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    version: str
    db: Literal["ok", "error"]


class MCPConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    endpoint: str
    channel: str | None = None
    anon_enabled: bool = False


# --- Sessions CRUD models (Plan 2.3) ---


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    channel_id: str = Field(min_length=1)


class SessionListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None
    channel_id: str
    updated_at: datetime
    message_count: int


class SessionsGrouped(BaseModel):
    model_config = ConfigDict(extra="forbid")

    today: list[SessionListItem] = []
    yesterday: list[SessionListItem] = []
    this_week: list[SessionListItem] = []
    earlier: list[SessionListItem] = []


class SessionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None
    channel_id: str
    created_at: datetime
    updated_at: datetime


class MessageRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role: Literal["user", "assistant", "tool"]
    content: str | None
    tool_calls: list[dict[str, Any]] | None
    cards: list[dict[str, Any]] | None
    duration_ms: int | None
    created_at: datetime


class SessionMessages(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[MessageRow]


class SessionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
