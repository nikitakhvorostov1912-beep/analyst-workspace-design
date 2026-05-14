"""POST /chat — SSE streaming через orchestrator tool-calling loop."""

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models import ChatRequest
from app.orchestrator.loop import run_chat_loop
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
) -> StreamingResponse:
    """Принимает сообщение и стримит SSE-ответ от LLM через tool-calling loop.

    Headers:
        X-LLM-API-Key (required): API ключ провайдера.
        X-LLM-Endpoint (optional): URL endpoint (default из Settings).
        X-LLM-Model (optional): модель (default из Settings).

    Body:
        channel_id (required): идентификатор MCP-подключения.
    """
    if not x_llm_api_key:
        raise HTTPException(status_code=400, detail="missing api key")

    settings = get_settings()
    llm_endpoint = x_llm_endpoint or settings.default_llm_endpoint
    llm_model = x_llm_model or settings.default_llm_model

    return StreamingResponse(
        run_chat_loop(db, request, x_llm_api_key, llm_endpoint, llm_model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
