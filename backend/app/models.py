from typing import Literal

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    session_id: str | None = None
    channel_id: str | None = None
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
