"""REST CRUD endpoints для mcp_connections: GET/POST/PUT/DELETE /connections."""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from app.clients.mcp import MCPClient
from app.models import (
    MCPConnectionCreate,
    MCPConnectionFull,
    MCPConnectionList,
    MCPConnectionUpdate,
    MCPPingWithTimestampResponse,
    MetadataSuggestItem,
    MetadataSuggestResponse,
)

TTL_SECONDS = int(os.environ.get("METADATA_CACHE_TTL_S", 3600))

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connections", tags=["connections"])


def _get_db(request: Request):
    return request.app.state.db


async def _lookup_cache(
    db,
    channel_id: str,
    q: str,
    limit: int,
) -> list[MetadataSuggestItem]:
    """Запрашивает metadata_cache по prefix + substring match."""
    rows = await db.execute_fetchall(
        """
        SELECT object_type, name, object_path, presentation
        FROM metadata_cache
        WHERE channel_id = ?
          AND (name LIKE ? OR object_path LIKE ?)
        ORDER BY name
        LIMIT ?
        """,
        (channel_id, f"{q}%", f"%{q}%", limit),
    )
    return [
        MetadataSuggestItem(
            object_type=row[0],
            name=row[1],
            full_path=row[2],
            presentation=row[3],
        )
        for row in rows
    ]


async def _cache_is_fresh(db, channel_id: str) -> bool:
    """Проверяет: есть ли записи в кеше и не устарели ли они (TTL_SECONDS)."""
    rows = await db.execute_fetchall(
        "SELECT MAX(fetched_at) FROM metadata_cache WHERE channel_id = ?",
        (channel_id,),
    )
    if not rows or rows[0][0] is None:
        return False
    max_ts_raw = rows[0][0]
    # Парсим timestamp
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            max_ts = datetime.strptime(str(max_ts_raw), fmt)
            break
        except ValueError:
            continue
    else:
        return False
    return datetime.utcnow() - max_ts < timedelta(seconds=TTL_SECONDS)


def _row_to_full(row: dict) -> MCPConnectionFull:
    """Конвертирует строку SQLite в MCPConnectionFull."""
    return MCPConnectionFull(
        id=row["id"],
        name=row["name"],
        endpoint=row["endpoint"],
        channel=row["channel"],
        anon_enabled=bool(row["anon_enabled"]),
        kind=(row.get("kind") or "embedded"),  # backward compat для старых записей
        last_seen_at=row["last_seen_at"],
        created_at=row["created_at"],
    )


# Колонки в фиксированном порядке для всех SELECT — гарантирует, что
# _row_to_full получает одинаковую структуру независимо от cursor.
_CONNECTION_COLUMNS = "id, name, endpoint, channel, anon_enabled, kind, last_seen_at, created_at"


def _row_tuple_to_dict(row: tuple) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "endpoint": row[2],
        "channel": row[3],
        "anon_enabled": row[4],
        "kind": row[5],
        "last_seen_at": row[6],
        "created_at": row[7],
    }


@router.get("", response_model=MCPConnectionList)
async def list_connections(request: Request) -> MCPConnectionList:
    """Возвращает все MCP-подключения из БД, сортировка по created_at DESC."""
    db = request.app.state.db
    async with db.execute(
        f"SELECT {_CONNECTION_COLUMNS} FROM mcp_connections ORDER BY created_at DESC"
    ) as cursor:
        rows = await cursor.fetchall()

    connections = [_row_to_full(_row_tuple_to_dict(row)) for row in rows]
    return MCPConnectionList(connections=connections)


@router.post("", response_model=MCPConnectionFull, status_code=201)
async def create_connection(
    body: MCPConnectionCreate,
    request: Request,
) -> MCPConnectionFull:
    """Создаёт новое MCP-подключение.

    Проверяет uniqueness: одного и того же `endpoint` достаточно — UI не должен
    создавать N копий «Транзит → http://localhost:6010/mcp». При совпадении —
    возвращаем 409 Conflict с указанием уже существующей записи, чтобы клиент
    мог предложить «Редактировать существующее» вместо «Создать ещё одно».
    """
    db = request.app.state.db
    async with db.execute(
        "SELECT id, name FROM mcp_connections WHERE endpoint = ? LIMIT 1",
        (body.endpoint,),
    ) as cursor:
        clash = await cursor.fetchone()

    if clash is not None:
        existing_id, existing_name = clash[0], clash[1]
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "duplicate_endpoint",
                "message": (
                    f"Подключение с адресом {body.endpoint} уже существует "
                    f"(«{existing_name}»). Откройте его на редактирование."
                ),
                "existing_id": existing_id,
                "existing_name": existing_name,
            },
        )

    conn_id = str(uuid4())
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, channel, anon_enabled, kind) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            conn_id,
            body.name,
            body.endpoint,
            body.channel,
            int(body.anon_enabled),
            body.kind,
        ),
    )
    await db.commit()

    async with db.execute(
        f"SELECT {_CONNECTION_COLUMNS} FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=500, detail="Ошибка создания подключения")

    return _row_to_full(_row_tuple_to_dict(row))


@router.put("/{conn_id}", response_model=MCPConnectionFull)
async def update_connection(
    conn_id: Annotated[str, Path(description="ID MCP-подключения")],
    body: MCPConnectionUpdate,
    request: Request,
) -> MCPConnectionFull:
    """Обновляет поля MCP-подключения (partial update)."""
    db = request.app.state.db

    async with db.execute(
        f"SELECT {_CONNECTION_COLUMNS} FROM mcp_connections WHERE id = ?",
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
    if body.kind is not None:
        updates["kind"] = body.kind

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [conn_id]
        await db.execute(
            f"UPDATE mcp_connections SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()

    async with db.execute(
        f"SELECT {_CONNECTION_COLUMNS} FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        row = await cursor.fetchone()

    return _row_to_full(_row_tuple_to_dict(row))


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


# Кэп списка tool_names в ping response. 20 имён достаточно для UI-чипов на /status,
# полный список (10-15 у 1C MCP, 5 у bsl-context) обычно умещается. Без кэпа большие
# aux MCP могут раздуть payload.
_PING_TOOLS_CAP = 20


@router.post("/{conn_id}/ping", response_model=MCPPingWithTimestampResponse)
async def ping_connection(
    conn_id: Annotated[str, Path(description="ID MCP-подключения")],
    request: Request,
) -> MCPPingWithTimestampResponse:
    """Пингует MCP endpoint из БД, обновляет last_seen_at при успехе.

    Возвращает kind/server_name/tool_names — чтобы /status показал тип подключения,
    название сервера (Native MCP / 1C MCP Toolkit / ...) и первые имена инструментов.
    """
    db = request.app.state.db

    async with db.execute(
        "SELECT endpoint, kind FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Подключение '{conn_id}' не найдено")

    endpoint = row[0]
    kind = row[1] or "embedded"
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

    tool_names = [str(t.get("name", "")) for t in tools[:_PING_TOOLS_CAP] if t.get("name")]

    return MCPPingWithTimestampResponse(
        mcp_version=session.mcp_version,
        tool_count=len(tools),
        session_id=session.session_id,
        duration_ms=duration_ms,
        last_seen_at=last_seen,
        kind=kind,
        server_name=session.server_name,
        tool_names=tool_names,
    )


@router.get("/{channel_id}/metadata-suggest", response_model=MetadataSuggestResponse)
async def metadata_suggest(
    channel_id: Annotated[str, Path(description="ID MCP-подключения (channel)")],
    q: str = Query(..., min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=100),
    db=Depends(_get_db),  # noqa: B008  — стандартный FastAPI dependency-injection паттерн
) -> MetadataSuggestResponse:
    """Возвращает список объектов метаданных 1С из кеша (TTL 1ч).

    При cache miss или устаревании — обновляет через MCP get_metadata.
    При недоступности MCP и наличии кеша — возвращает stale данные.
    При недоступности MCP и пустом кеше — 502.
    """
    # Проверяем существование channel
    rows = await db.execute_fetchall(
        "SELECT id, endpoint FROM mcp_connections WHERE id = ?",
        (channel_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Канал '{channel_id}' не найден")

    endpoint = rows[0][1]
    is_fresh = await _cache_is_fresh(db, channel_id)

    if is_fresh:
        items = await _lookup_cache(db, channel_id, q, limit)
        return MetadataSuggestResponse(items=items, cached=True, stale=False)

    # Cache miss или устарел — пытаемся обновить через MCP
    refresh_ok = False
    try:
        async with MCPClient(endpoint) as client:
            await client.initialize()
            tools = await client.list_tools()
            tool_names = {t.get("name") for t in tools}

            if "get_metadata" in tool_names:
                result = await client.call_tool("get_metadata", {"detail": False})
                # Парсим результат: ожидаем список объектов
                objects = _parse_metadata_result(result)

                # Обновляем кеш
                await db.execute(
                    "DELETE FROM metadata_cache WHERE channel_id = ?",
                    (channel_id,),
                )
                for obj in objects:
                    await db.execute(
                        """
                        INSERT INTO metadata_cache
                            (channel_id, object_path, object_type, name, presentation, fetched_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            channel_id,
                            obj.get("full_path", obj.get("name", "")),
                            obj.get("object_type", ""),
                            obj.get("name", ""),
                            obj.get("presentation"),
                        ),
                    )
                await db.commit()
                refresh_ok = True
    except Exception as exc:
        logger.warning("metadata_suggest MCP refresh failed for %s: %s", channel_id, exc)

    if refresh_ok:
        items = await _lookup_cache(db, channel_id, q, limit)
        return MetadataSuggestResponse(items=items, cached=True, stale=False)

    # MCP недоступен — проверяем stale кеш
    stale_items = await _lookup_cache(db, channel_id, q, limit)
    if stale_items:
        return MetadataSuggestResponse(items=stale_items, cached=True, stale=True)

    # Пустой кеш + MCP недоступен
    raise HTTPException(status_code=502, detail="MCP недоступен и кеш пуст")


def _parse_metadata_result(result: object) -> list[dict]:
    """Извлекает список объектов из результата MCP get_metadata.

    Формат ответа varies — обрабатываем известные варианты.
    """
    import json

    # result может быть: list[dict] | dict | str
    if isinstance(result, list):
        return [_normalize_obj(item) for item in result if isinstance(item, dict)]

    if isinstance(result, dict):
        # Может быть обёрнут в {"content": [...]} или {"objects": [...]}
        for key in ("content", "objects", "items", "result"):
            if key in result and isinstance(result[key], list):
                return [_normalize_obj(item) for item in result[key] if isinstance(item, dict)]
        return [_normalize_obj(result)]

    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            return _parse_metadata_result(parsed)
        except (json.JSONDecodeError, TypeError):
            pass

    return []


def _normalize_obj(obj: dict) -> dict:
    """Нормализует объект метаданных к единому формату."""
    name = obj.get("name", obj.get("Name", ""))
    obj_type = obj.get("type", obj.get("object_type", obj.get("Type", "")))
    full_path = obj.get("full_path", obj.get("path", f"{obj_type}.{name}" if obj_type and name else name))
    presentation = obj.get("presentation", obj.get("synonym", obj.get("Synonym")))
    return {
        "name": name,
        "object_type": obj_type,
        "full_path": full_path,
        "presentation": presentation,
    }
