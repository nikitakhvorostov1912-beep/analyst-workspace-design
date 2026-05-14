"""REST CRUD endpoints для mcp_connections: GET/POST/PUT/DELETE /connections."""

import logging
import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import ValidationError

from app.clients.mcp import MCPClient
from app.models import (
    MCPConnectionCreate,
    MCPConnectionFull,
    MCPConnectionList,
    MCPConnectionUpdate,
    MCPPingWithTimestampResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connections", tags=["connections"])


def _row_to_full(row: dict) -> MCPConnectionFull:
    """Конвертирует строку SQLite в MCPConnectionFull."""
    return MCPConnectionFull(
        id=row["id"],
        name=row["name"],
        endpoint=row["endpoint"],
        channel=row["channel"],
        anon_enabled=bool(row["anon_enabled"]),
        last_seen_at=row["last_seen_at"],
        created_at=row["created_at"],
    )


@router.get("", response_model=MCPConnectionList)
async def list_connections(request: Request) -> MCPConnectionList:
    """Возвращает все MCP-подключения из БД, сортировка по created_at DESC."""
    db = request.app.state.db
    async with db.execute(
        "SELECT id, name, endpoint, channel, anon_enabled, last_seen_at, created_at "
        "FROM mcp_connections ORDER BY created_at DESC"
    ) as cursor:
        rows = await cursor.fetchall()

    connections = [
        _row_to_full(
            {
                "id": row[0],
                "name": row[1],
                "endpoint": row[2],
                "channel": row[3],
                "anon_enabled": row[4],
                "last_seen_at": row[5],
                "created_at": row[6],
            }
        )
        for row in rows
    ]
    return MCPConnectionList(connections=connections)


@router.post("", response_model=MCPConnectionFull, status_code=201)
async def create_connection(
    body: MCPConnectionCreate,
    request: Request,
) -> MCPConnectionFull:
    """Создаёт новое MCP-подключение."""
    db = request.app.state.db
    conn_id = str(uuid4())

    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, channel, anon_enabled) "
        "VALUES (?, ?, ?, ?, ?)",
        (conn_id, body.name, body.endpoint, body.channel, int(body.anon_enabled)),
    )
    await db.commit()

    async with db.execute(
        "SELECT id, name, endpoint, channel, anon_enabled, last_seen_at, created_at "
        "FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=500, detail="Ошибка создания подключения")

    return _row_to_full(
        {
            "id": row[0],
            "name": row[1],
            "endpoint": row[2],
            "channel": row[3],
            "anon_enabled": row[4],
            "last_seen_at": row[5],
            "created_at": row[6],
        }
    )


@router.put("/{conn_id}", response_model=MCPConnectionFull)
async def update_connection(
    conn_id: Annotated[str, Path(description="ID MCP-подключения")],
    body: MCPConnectionUpdate,
    request: Request,
) -> MCPConnectionFull:
    """Обновляет поля MCP-подключения (partial update)."""
    db = request.app.state.db

    async with db.execute(
        "SELECT id, name, endpoint, channel, anon_enabled, last_seen_at, created_at "
        "FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        existing = await cursor.fetchone()

    if existing is None:
        raise HTTPException(status_code=404, detail=f"Подключение '{conn_id}' не найдено")

    updates: dict[str, object] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.endpoint is not None:
        updates["endpoint"] = body.endpoint
    if body.channel is not None:
        updates["channel"] = body.channel
    if body.anon_enabled is not None:
        updates["anon_enabled"] = int(body.anon_enabled)

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [conn_id]
        await db.execute(
            f"UPDATE mcp_connections SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()

    async with db.execute(
        "SELECT id, name, endpoint, channel, anon_enabled, last_seen_at, created_at "
        "FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        row = await cursor.fetchone()

    return _row_to_full(
        {
            "id": row[0],
            "name": row[1],
            "endpoint": row[2],
            "channel": row[3],
            "anon_enabled": row[4],
            "last_seen_at": row[5],
            "created_at": row[6],
        }
    )


@router.delete("/{conn_id}", status_code=204)
async def delete_connection(
    conn_id: Annotated[str, Path(description="ID MCP-подключения")],
    request: Request,
) -> None:
    """Удаляет MCP-подключение. 204 при успехе, 404 если не найдено."""
    db = request.app.state.db

    async with db.execute(
        "SELECT id FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        existing = await cursor.fetchone()

    if existing is None:
        raise HTTPException(status_code=404, detail=f"Подключение '{conn_id}' не найдено")

    await db.execute("DELETE FROM mcp_connections WHERE id = ?", (conn_id,))
    await db.commit()


@router.post("/{conn_id}/ping", response_model=MCPPingWithTimestampResponse)
async def ping_connection(
    conn_id: Annotated[str, Path(description="ID MCP-подключения")],
    request: Request,
) -> MCPPingWithTimestampResponse:
    """Пингует MCP endpoint из БД, обновляет last_seen_at при успехе."""
    db = request.app.state.db

    async with db.execute(
        "SELECT endpoint FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Подключение '{conn_id}' не найдено")

    endpoint = row[0]
    started_at = time.monotonic()

    try:
        async with MCPClient(endpoint) as client:
            session = await client.initialize()
            tools = await client.list_tools()
    except Exception as exc:
        short = str(exc)[:200]
        logger.warning("MCP ping failed for %s: %s", conn_id, short)
        raise HTTPException(
            status_code=502,
            detail=f"MCP не отвечает: {short}",
        ) from exc

    duration_ms = int((time.monotonic() - started_at) * 1000)

    await db.execute(
        "UPDATE mcp_connections SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conn_id,),
    )
    await db.commit()

    async with db.execute(
        "SELECT last_seen_at FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        ts_row = await cursor.fetchone()
    last_seen = ts_row[0] if ts_row else None

    return MCPPingWithTimestampResponse(
        mcp_version=session.mcp_version,
        tool_count=len(tools),
        session_id=session.session_id,
        duration_ms=duration_ms,
        last_seen_at=last_seen,
    )
