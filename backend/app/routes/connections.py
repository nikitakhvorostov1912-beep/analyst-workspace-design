"""REST CRUD endpoints для mcp_connections: GET/POST/PUT/DELETE /connections."""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from app.clients.mcp import MCPClient, is_local_endpoint, normalize_local_endpoint
from app.clients.mcp_errors import classify_ping_error, collect_local_diagnostics
from app.models import (
    MCPConnectionCreate,
    MCPConnectionFull,
    MCPConnectionList,
    MCPConnectionUpdate,
    MCPPingWithTimestampResponse,
    MetadataSuggestItem,
    MetadataSuggestResponse,
)
from app.routes.chat import chat_limiter
from app.security.mcp_endpoint_validator import (
    MCPEndpointError,
    validate_mcp_endpoint,
)
from app.knowledge.onboarding import run_detection_for_channel, should_run_detection
from app.services.capability_discovery import discover_capabilities

TTL_SECONDS = int(os.environ.get("METADATA_CACHE_TTL_S", 3600))

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connections", tags=["connections"])

# Fire-and-forget онбординг-детект — ссылка, чтобы GC не собрал task.
_DETECTION_TASKS: set[asyncio.Task] = set()


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
    """Конвертирует строку SQLite в MCPConnectionFull.

    M-K1.6: добавлены capability fields (mode/configuration/platform/
    ext_version/capabilities/fingerprint). Backward compat — все Optional,
    fallback defaults для legacy rows которые ещё не прошли capability discovery.
    """
    # capabilities хранится как JSON string в SQLite — десериализуем
    capabilities_raw = row.get("capabilities")
    if capabilities_raw:
        try:
            caps = json.loads(capabilities_raw)
            capabilities = caps if isinstance(caps, list) else []
        except (json.JSONDecodeError, TypeError):
            capabilities = []
    else:
        capabilities = []

    return MCPConnectionFull(
        id=row["id"],
        name=row["name"],
        endpoint=row["endpoint"],
        channel=row["channel"],
        anon_enabled=bool(row["anon_enabled"]),
        kind=(row.get("kind") or "embedded"),  # backward compat для старых записей
        last_seen_at=row["last_seen_at"],
        created_at=row["created_at"],
        # M-K1.6 (v11) capability fields
        mode=(row.get("mode") or "mcp_only"),
        configuration=row.get("configuration"),
        configuration_source=row.get("configuration_source"),
        platform=row.get("platform"),
        ext_version=row.get("ext_version"),
        capabilities=capabilities,
        fingerprint=row.get("fingerprint"),
    )


# Колонки в фиксированном порядке для всех SELECT — гарантирует, что
# _row_to_full получает одинаковую структуру независимо от cursor.
# M-K1.6 (v11): добавлены mode, configuration, platform, ext_version,
# capabilities, fingerprint.
_CONNECTION_COLUMNS = (
    "id, name, endpoint, channel, anon_enabled, kind, last_seen_at, created_at, "
    "mode, configuration, platform, ext_version, capabilities, fingerprint, "
    "configuration_source"
)


def _row_tuple_to_dict(row: tuple) -> dict:
    """M-K1.6 (v11): добавлены 6 capability fields в конец tuple.

    Порядок индексов жёстко привязан к `_CONNECTION_COLUMNS` — не менять
    отдельно от SELECT.
    """
    return {
        "id": row[0],
        "name": row[1],
        "endpoint": row[2],
        "channel": row[3],
        "anon_enabled": row[4],
        "kind": row[5],
        "last_seen_at": row[6],
        "created_at": row[7],
        # v11 capability fields (порядок из _CONNECTION_COLUMNS)
        "mode": row[8] if len(row) > 8 else None,
        "configuration": row[9] if len(row) > 9 else None,
        "platform": row[10] if len(row) > 10 else None,
        "ext_version": row[11] if len(row) > 11 else None,
        "capabilities": row[12] if len(row) > 12 else None,
        "fingerprint": row[13] if len(row) > 13 else None,
        # v24 (Multi-base онбординг): источник детекции конфигурации
        "configuration_source": row[14] if len(row) > 14 else None,
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


async def _validate_endpoint_ssrf(endpoint: str) -> None:
    """SEC-1 SSRF guard. Запускается в thread pool — DNS resolve blocking.

    Бросает HTTPException(400) если endpoint небезопасный — приватный IP,
    link-local (AWS metadata), loopback (кроме 127.0.0.1), reserved, etc.
    """
    try:
        # validate_mcp_endpoint делает socket.getaddrinfo — blocking I/O.
        # Прячем в thread pool чтобы не блокировать event loop.
        await asyncio.to_thread(validate_mcp_endpoint, endpoint)
    except MCPEndpointError as exc:
        logger.warning("SEC-1: rejected endpoint %s — %s", endpoint, exc)
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "unsafe_endpoint",
                "message": exc.user_message,
            },
        ) from exc


@router.post("", response_model=MCPConnectionFull, status_code=201)
@chat_limiter.limit("30/minute")  # B-03: DoS-защита (DNS-lookup в thread pool)
async def create_connection(
    body: MCPConnectionCreate,
    request: Request,
) -> MCPConnectionFull:
    """Создаёт новое MCP-подключение.

    Проверяет uniqueness: одного и того же `endpoint` достаточно — UI не должен
    создавать N копий «Моя база → http://localhost:6010/mcp». При совпадении —
    возвращаем 409 Conflict с указанием уже существующей записи, чтобы клиент
    мог предложить «Редактировать существующее» вместо «Создать ещё одно».

    SEC-1: SSRF guard на endpoint до записи в БД.
    """
    # SSRF guard — до DB writes, чтобы не оставлять «ядовитые» записи в БД.
    await _validate_endpoint_ssrf(body.endpoint)

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
@chat_limiter.limit("30/minute")  # B-03: DoS-защита (DNS-lookup в thread pool)
async def update_connection(
    conn_id: Annotated[str, Path(description="ID MCP-подключения")],
    body: MCPConnectionUpdate,
    request: Request,
) -> MCPConnectionFull:
    """Обновляет поля MCP-подключения (partial update).

    SEC-1: если endpoint меняется — проходит SSRF guard.
    """
    # SSRF guard на новый endpoint (если он указан).
    if body.endpoint is not None:
        await _validate_endpoint_ssrf(body.endpoint)

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
    if body.configuration is not None:
        updates["configuration"] = body.configuration
    if body.configuration_source is not None:
        updates["configuration_source"] = body.configuration_source

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
@chat_limiter.limit("20/minute")  # B-03: DoS-защита (открывает MCP TCP-коннект)
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
        # 2026-05-25: расширенная диагностика. Раньше тут было `str(exc)[:200]`
        # — обрезок без endpoint, без типа исключения, без подсказки. Клиент
        # присылал backend.log и в нём была только строка
        # «All connection attempts failed» — невозможно понять что чинить.
        # Теперь лог содержит структурированный JSON: класс ошибки, hint,
        # resolved DNS, proxy env, probe соседних портов 1С на 127.0.0.1.
        normalized = normalize_local_endpoint(endpoint)
        failure = classify_ping_error(exc, normalized)
        diag: dict[str, Any] = {
            "conn_id": conn_id,
            "raw_endpoint": endpoint,
            "normalized_endpoint": normalized,
            "exception_type": failure.exception_type,
            "exception_message": failure.exception_message,
            "error_class": failure.error_class,
            "hint": failure.hint,
        }
        if is_local_endpoint(normalized):
            diag.update(collect_local_diagnostics(normalized))
        logger.warning(
            "MCP ping failed: %s",
            json.dumps(diag, ensure_ascii=False, default=str),
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": failure.error_class,
                "message": f"MCP не отвечает: {failure.hint}",
                "hint": failure.hint,
                "diagnostics": diag,
            },
        ) from exc

    duration_ms = int((time.monotonic() - started_at) * 1000)

    # M-K1.7: Capability Discovery — парсим experimental из MCP initialize и
    # сохраняем mode/configuration/platform/ext_version/capabilities/fingerprint
    # в БД (миграция v11). Это позволяет фронту знать какие фичи доступны на
    # данном канале (ADR-004 + useCapability hook в M-K1.10).
    #
    # NB: discover_capabilities() гарантированно возвращает результат (fallback
    # на mcp_only + base 8 caps если experimental пустой) — не блокирует ping.
    discovery = discover_capabilities(session)
    caps_json = json.dumps(discovery.capability_strings, ensure_ascii=False)
    fingerprint_slug = discovery.fingerprint.slug if discovery.fingerprint else None

    # COALESCE(?, configuration): для «сырого» 1С MCP Toolkit discover_capabilities
    # возвращает configuration=None (нет нашего CFE experimental namespace). Без
    # COALESCE каждый ping ОБНУЛЯЛ бы configuration → детект-триггер (should_run_detection
    # = configuration IS NULL) перезапускался бы на КАЖДЫЙ ping (≈40 MCP-проб впустую),
    # бейдж мигал бы, а РУЧНОЙ override затирался бы. COALESCE сохраняет уже
    # установленное значение, если discovery дал None; перезаписывает только когда
    # сервер сам объявил конфигурацию (CFE). To-force re-detect — ручной override.
    await db.execute(
        """
        UPDATE mcp_connections
        SET last_seen_at = CURRENT_TIMESTAMP,
            mode = ?,
            configuration = COALESCE(?, configuration),
            platform = ?,
            ext_version = ?,
            capabilities = ?,
            fingerprint = ?
        WHERE id = ?
        """,
        (
            discovery.mode,
            discovery.configuration,
            discovery.platform,
            discovery.ext_version,
            caps_json,
            fingerprint_slug,
            conn_id,
        ),
    )
    await db.commit()

    async with db.execute(
        "SELECT last_seen_at FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        ts_row = await cursor.fetchone()
    last_seen = ts_row[0] if ts_row else None

    tool_names = [str(t.get("name", "")) for t in tools[:_PING_TOOLS_CAP] if t.get("name")]

    # Multi-base онбординг (B.1): на первом успешном ping новой базы фоном
    # детектируем конфигурацию. НЕ блокирует ответ ping. Только если конфа ещё
    # не установлена (configuration IS NULL) — на «горячих» базах не дёргаем MCP.
    #
    # NB: проверка идёт ПОСЛЕ commit() discovery (UPDATE configuration выше). Если
    # MCP-сервер сам объявил configuration через experimental namespace
    # (наше CFE-расширение АналитикПлюс), discovery.configuration уже не NULL →
    # should_run_detection вернёт False → MCP-пробы не нужны (данные получены
    # бесплатно из capability). Для «сырого» 1С MCP Toolkit configuration=NULL →
    # детект-пробы запускаются. Это намеренный приоритет self-declared над эвристикой.
    try:
        if await should_run_detection(db, conn_id):
            task = asyncio.create_task(
                run_detection_for_channel(db, conn_id, endpoint),
                name=f"onboarding-detect-{conn_id}",
            )
            _DETECTION_TASKS.add(task)
            task.add_done_callback(_DETECTION_TASKS.discard)
    except Exception:  # noqa: BLE001 — детект-триггер не должен ломать ping
        logger.exception("Не удалось запланировать онбординг-детект для %s", conn_id)

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
    """Возвращает объекты метаданных 1С под @-автокомплит.

    Стратегия (2026-06-03, фикс @-mention):
    1. Свежий кеш + совпадение по q → отдаём из кеша локально (cached, не stale).
    2. Иначе — live substring-поиск через MCP get_metadata(meta_type="*",
       name_mask=q). Это нативный поиск 1C — точнее и легче, чем балк-кэш 20K+
       объектов. Результат опционально подогревает кеш (для offline-fallback).
    3. MCP недоступен + есть кеш → stale данные. Пустой кеш → 502.

    Раньше тут был `bulk_refresh_metadata_cache(detail=False)` — он вызывал
    summary-режим (типы+счётчики), парсер не извлекал имён → в кеш писалось
    0 объектов, @-popover всегда показывал «Ничего не найдено».
    """
    # Проверяем существование channel
    rows = await db.execute_fetchall(
        "SELECT id, endpoint FROM mcp_connections WHERE id = ?",
        (channel_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Канал '{channel_id}' не найден")

    endpoint = rows[0][1]

    # 1. Свежий кеш с совпадением — отдаём локально (без обращения к MCP).
    if await _cache_is_fresh(db, channel_id):
        cached_items = await _lookup_cache(db, channel_id, q, limit)
        if cached_items:
            return MetadataSuggestResponse(items=cached_items, cached=True, stale=False)

    # 2. Live substring-поиск через MCP (нативный name_mask).
    from app.knowledge.indexer import live_metadata_suggest, write_cache_batch

    try:
        objects = await live_metadata_suggest(endpoint, q, limit)
    except Exception as exc:  # noqa: BLE001 — граница MCP, дальше fallback на кеш
        logger.warning("metadata_suggest live MCP failed for %s: %s", channel_id, exc)
        stale_items = await _lookup_cache(db, channel_id, q, limit)
        if stale_items:
            return MetadataSuggestResponse(items=stale_items, cached=True, stale=True)
        raise HTTPException(status_code=502, detail="MCP недоступен и кеш пуст") from exc

    # Подогреваем кеш найденными объектами (non-destructive) — чтобы повторные
    # запросы и offline-fallback работали. Best-effort: ошибка записи не фейлит.
    if objects:
        try:
            await write_cache_batch(db, channel_id, objects, replace_existing=False)
        except Exception:  # noqa: BLE001 — кеш-warming некритичен
            logger.exception("metadata_suggest cache warm failed for %s", channel_id)

    items = [
        MetadataSuggestItem(
            object_type=obj.object_type,
            name=obj.name,
            full_path=obj.object_path,
            presentation=obj.presentation,
        )
        for obj in objects
    ]
    return MetadataSuggestResponse(items=items, cached=False, stale=False)


# M-K2.2 (2026-05-26): `_parse_metadata_result` + `_normalize_obj` удалены —
# логика перенесена в `app.knowledge.indexer.parse_metadata_result` +
# `_normalize_metadata_object` (с покрытием unit тестами). См. M-K2-PLAN
# фаза M-K2.1.
# 2026-06-03 (@-mention фикс): `metadata_suggest` перешёл с `bulk_refresh_metadata_cache`
# (full-index summary-режимом — давал 0 объектов) на `live_metadata_suggest`
# (нативный name_mask substring-поиск 1C). Кеш — только offline-fallback.
