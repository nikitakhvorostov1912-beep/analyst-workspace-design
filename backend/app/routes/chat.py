"""POST /chat — SSE streaming через orchestrator tool-calling loop.
POST /chat/confirm — подтверждение опасного execute_code (SEC-01).
"""

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.config import get_settings
from app.models import ChatRequest, ConfirmRequest
from app.orchestrator.loop import run_chat_loop
from app.orchestrator.safety import resolve_pending_confirmation
from app.storage.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    x_llm_api_key: str | None = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_endpoint: str | None = Header(default=None, alias="X-LLM-Endpoint"),
    x_llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    x_anon_enabled: str | None = Header(default=None, alias="X-Anon-Enabled"),
) -> StreamingResponse:
    """Принимает сообщение и стримит SSE-ответ от LLM через tool-calling loop.

    Headers:
        X-LLM-API-Key (required): API ключ провайдера.
        X-LLM-Endpoint (optional): URL endpoint (default из Settings).
        X-LLM-Model (optional): модель (default из Settings).
        X-Anon-Enabled (optional): "true" → анонимизация включена.

    Body:
        channel_id (required): идентификатор MCP-подключения.
    """
    if not x_llm_api_key:
        raise HTTPException(status_code=400, detail="missing api key")

    settings = get_settings()
    llm_endpoint = x_llm_endpoint or settings.default_llm_endpoint
    llm_model = x_llm_model or settings.default_llm_model
    anon_enabled = (x_anon_enabled or "").strip().lower() == "true"

    return StreamingResponse(
        run_chat_loop(db, request, x_llm_api_key, llm_endpoint, llm_model, x_anon_enabled=anon_enabled),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/confirm", status_code=204)
async def confirm(request: ConfirmRequest) -> Response:
    """Подтверждает или отклоняет выполнение dangerous execute_code (SEC-01).

    Body:
        tool_call_id (required): ID инструмента из event confirm_required.
        approved (required): True — выполнить, False — отменить.

    Returns:
        204 при успехе.
        404 если tool_call_id не найден или истёк.
    """
    resolved = resolve_pending_confirmation(request.tool_call_id, request.approved)
    if not resolved:
        raise HTTPException(status_code=404, detail="tool_call_id не найден или истёк")
    return Response(status_code=204)
