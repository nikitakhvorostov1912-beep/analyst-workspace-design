from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

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
    last_seen_at: datetime | None = None
    created_at: datetime | None = None


class MCPConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=200)
    endpoint: str = Field(min_length=1)
    channel: str | None = None
    anon_enabled: bool = False

    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("endpoint должен начинаться с http:// или https://")
        return v

    def model_post_init(self, _context: object) -> None:
        self.validate_endpoint(self.endpoint)


class MCPConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    endpoint: str | None = None
    channel: str | None = None
    anon_enabled: bool | None = None

    def model_post_init(self, _context: object) -> None:
        if self.endpoint is not None:
            if not (self.endpoint.startswith("http://") or self.endpoint.startswith("https://")):
                raise ValueError("endpoint должен начинаться с http:// или https://")


class MCPConnectionFull(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    endpoint: str
    channel: str | None = None
    anon_enabled: bool = False
    last_seen_at: datetime | None = None
    created_at: datetime


class MCPConnectionList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connections: list[MCPConnectionFull]


class MCPPingWithTimestampResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mcp_version: str
    tool_count: int
    session_id: str
    duration_ms: int
    last_seen_at: datetime | None = None


# --- Sessions CRUD models (Plan 2.3) ---


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

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
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=200)


class ConfirmRequest(BaseModel):
    """Тело POST /chat/confirm (SEC-01)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool_call_id: str = Field(min_length=1)
    approved: bool
