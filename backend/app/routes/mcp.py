"""POST /mcp/{conn_id}/ping — инициализация MCP сессии и счёт инструментов."""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Path

from app.clients.mcp import MCPClient
from app.models import MCPPingResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/mcp/{conn_id}/ping", response_model=MCPPingResponse)
async def mcp_ping(
    conn_id: Annotated[str, Path(description="ID MCP соединения (Phase 1: игнорируется)")],
    x_mcp_endpoint: Annotated[str | None, Header(alias="X-MCP-Endpoint")] = None,
    endpoint: str | None = None,
) -> MCPPingResponse:
    """Проверяет MCP соединение: initialize + tools/list.

    В Phase 1 conn_id игнорируется (нет CRUD для connections).
    Endpoint берётся из header X-MCP-Endpoint или query параметра endpoint.

    Args:
        conn_id: ID соединения (резерв для Phase 2).
        x_mcp_endpoint: URL MCP endpoint (header).
        endpoint: URL MCP endpoint (query параметр).

    Returns:
        MCPPingResponse с mcp_version, tool_count, session_id, duration_ms.
    """
    mcp_endpoint = x_mcp_endpoint or endpoint
    if not mcp_endpoint:
        raise HTTPException(
            status_code=400,
            detail="Необходим endpoint MCP (header X-MCP-Endpoint или query ?endpoint=)",
        )

    started_at = time.monotonic()

    async with MCPClient(mcp_endpoint) as client:
        session = await client.initialize()
        tools = await client.list_tools()

    duration_ms = int((time.monotonic() - started_at) * 1000)

    return MCPPingResponse(
        mcp_version=session.mcp_version,
        tool_count=len(tools),
        session_id=session.session_id,
        duration_ms=duration_ms,
    )
