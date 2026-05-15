"""Маршруты для карточек:
- POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more — пагинация LogCard (Plan 03-04)
- POST /sessions/{sid}/messages/{mid}/cards/{cid}/deanonymize — раскрытие токенов (Plan 04-01)
"""

import json
import logging
from collections.abc import AsyncIterator

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.clients.mcp import MCPClient, MCPDisconnectedError, MCPError
from app.models import DeanonymizeRequest, DeanonymizeResponse, LoadMoreRequest, LogPagePayload
from app.orchestrator.cards import _extract_mcp_content, build_card_from_tool_result
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


@router.post(
    "/sessions/{sid}/messages/{mid}/cards/{cid}/deanonymize",
    response_model=DeanonymizeResponse,
    summary="Раскрыть anon-токены в карточке",
    responses={
        404: {"description": "card state not found"},
        422: {"description": "invalid token format"},
        502: {"description": "MCP error"},
    },
)
async def deanonymize_card(
    sid: str,
    mid: str,
    cid: str,
    body: DeanonymizeRequest,
    db: aiosqlite.Connection = Depends(get_app_db),  # noqa: B008
) -> Response:
    """Раскрывает anon-токены для карточки через MCP submit_for_deanonymization.

    Ownership check: session_id + message_id должны совпасть (как в load-more).
    Реальные значения НЕ сохраняются в DB — только возвращаются клиенту.

    Returns:
        DeanonymizeResponse(mapping={"[ORG-001]": "ООО Ромашка", ...})
    """
    state = await get_card_state(db, cid)
    if state is None or state["session_id"] != sid or state["message_id"] != mid:
        raise HTTPException(status_code=404, detail="card state not found")

    endpoint = await lookup_mcp_endpoint(db, state["channel_id"])
    if endpoint is None:
        raise HTTPException(status_code=502, detail="Канал недоступен")

    try:
        mcp = MCPClient(endpoint, headers={"X-Anon-Enabled": "true"})
        await mcp.initialize()
        result = await mcp.call_tool("submit_for_deanonymization", {"tokens": body.tokens})
        await mcp.aclose()
    except (MCPDisconnectedError, MCPError) as exc:
        logger.warning("MCP error в deanonymize для card %s: %s", cid, exc)
        raise HTTPException(status_code=502, detail=f"MCP error: {str(exc)[:120]}") from exc
    except Exception as exc:
        logger.warning("Ошибка deanonymize для card %s: %s", cid, exc)
        raise HTTPException(status_code=502, detail=f"MCP error: {str(exc)[:120]}") from exc

    # Парсим MCP response — несколько форматов на случай вариаций MCP server
    mapping: dict[str, str] = {}

    # Попытка 1: прямой dict
    if isinstance(result, dict):
        for key in ("mapping", "map", "replacements"):
            candidate = result.get(key)
            if isinstance(candidate, dict):
                mapping = {str(k): str(v) for k, v in candidate.items()}
                break

    # Попытка 2: MCP content[0].text формат
    if not mapping:
        parsed = _extract_mcp_content(result) if isinstance(result, dict) else None
        if parsed:
            for key in ("mapping", "map", "replacements"):
                candidate = parsed.get(key)
                if isinstance(candidate, dict):
                    mapping = {str(k): str(v) for k, v in candidate.items()}
                    break

    deanon_response = DeanonymizeResponse(mapping=mapping)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=deanon_response.model_dump(),
        headers={"Cache-Control": "no-store, private"},
    )
