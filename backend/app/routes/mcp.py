"""POST /mcp/{conn_id}/ping — инициализация MCP сессии и счёт инструментов.

Phase 1 backward compat: если conn_id найден в mcp_connections — использует endpoint из БД.
Если не найден и передан X-MCP-Endpoint или ?endpoint= — использует переданный (Phase 1 паттерн).
"""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Path, Request

from app.clients.mcp import MCPClient
from app.models import MCPPingResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/mcp/{conn_id}/ping", response_model=MCPPingResponse)
async def mcp_ping(
    conn_id: Annotated[str, Path(description="ID MCP соединения")],
    request: Request,
    x_mcp_endpoint: Annotated[str | None, Header(alias="X-MCP-Endpoint")] = None,
    endpoint: str | None = None,
) -> MCPPingResponse:
    """Проверяет MCP соединение: initialize + tools/list.

    Backward compat (Phase 1 + Phase 2):
    - Если conn_id найден в mcp_connections → endpoint из БД.
    - Если не найден И передан X-MCP-Endpoint или ?endpoint= → переданный endpoint (Phase 1).
    - Если ничего → 404.

    Args:
        conn_id: ID соединения.
        request: FastAPI request (для доступа к app.state.db).
        x_mcp_endpoint: URL MCP endpoint (header, Phase 1 fallback).
        endpoint: URL MCP endpoint (query параметр, Phase 1 fallback).

    Returns:
        MCPPingResponse с mcp_version, tool_count, session_id, duration_ms.
    """
    mcp_endpoint: str | None = None

    # Phase 2: ищем conn_id в БД
    db = getattr(request.app.state, "db", None)
    if db is not None:
        async with db.execute(
            "SELECT endpoint FROM mcp_connections WHERE id = ?",
            (conn_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is not None:
            mcp_endpoint = row[0]

    # Phase 1 fallback: endpoint из header или query
    if mcp_endpoint is None:
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
