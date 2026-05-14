"""Маршрут POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more.

Обеспечивает пагинацию LogCard через get_event_log MCP-инструмент.
Plan 03-04 (закрытие Phase 2 deferred: CARD-03 LogCard cursor-fetch).
"""

import json
import logging
from collections.abc import AsyncIterator

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request

from app.clients.mcp import MCPClient
from app.models import LoadMoreRequest, LogPagePayload
from app.orchestrator.cards import build_card_from_tool_result
from app.orchestrator.persistence import get_card_state, lookup_mcp_endpoint

logger = logging.getLogger(__name__)

router = APIRouter(tags=["log_cards"])


async def get_app_db(request: Request) -> AsyncIterator[aiosqlite.Connection]:
    """FastAPI dependency — возвращает aiosqlite соединение из app.state.

    Отдельная функция (не из storage.db) чтобы тесты могли легко override через
    app.dependency_overrides[get_app_db] = lambda: fresh_db.
    """
    yield request.app.state.db


@router.post(
    "/sessions/{sid}/messages/{mid}/cards/{cid}/load-more",
    response_model=LogPagePayload,
    summary="Загрузить следующую страницу LogCard",
)
async def load_more(
    sid: str,
    mid: str,
    cid: str,
    body: LoadMoreRequest,
    db: aiosqlite.Connection = Depends(get_app_db),  # noqa: B008
) -> LogPagePayload:
    """Загружает следующую страницу записей журнала для LogCard.

    Lookup card_state по cid, проверяет ownership (sid+mid),
    вызывает get_event_log через MCPClient с добавленным cursor,
    возвращает {entries, next_cursor}.
    """
    state = await get_card_state(db, cid)
    if state is None or state["session_id"] != sid or state["message_id"] != mid:
        raise HTTPException(status_code=404, detail="card state not found")

    endpoint = await lookup_mcp_endpoint(db, state["channel_id"])
    if endpoint is None:
        raise HTTPException(status_code=502, detail="Канал недоступен")

    original_args = json.loads(state["original_args"])
    args = {**original_args, "cursor": body.cursor}

    try:
        mcp = MCPClient(endpoint)
        await mcp.initialize()
        result = await mcp.call_tool(state["tool_name"], args)
        await mcp.aclose()
    except Exception as exc:
        logger.warning("MCP error в load-more для card %s: %s", cid, exc)
        raise HTTPException(status_code=502, detail=f"MCP error: {str(exc)[:120]}") from exc

    card = build_card_from_tool_result(state["tool_name"], args, result)
    if card is None or card["type"] != "log":
        raise HTTPException(status_code=500, detail="не удалось построить страницу")

    return LogPagePayload(
        entries=card["payload"]["entries"],
        next_cursor=card["payload"].get("next_cursor"),
    )
