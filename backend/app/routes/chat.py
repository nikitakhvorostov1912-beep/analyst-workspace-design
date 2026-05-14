"""POST /chat — SSE streaming через LLM-клиент."""

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.clients.llm import LLMClient
from app.config import get_settings
from app.models import ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter()


async def _sse_event(event: str, data: dict) -> str:
    """Форматирует SSE-строку."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _chat_generator(
    request: ChatRequest,
    api_key: str,
    llm_endpoint: str,
    llm_model: str,
) -> AsyncIterator[str]:
    """Async-генератор SSE-событий для одного запроса.

    Последовательность: status → delta(×N) → done.
    При ошибке: error.
    """
    # Первый байт — статус (NFR-1: ≤ 500 мс)
    yield await _sse_event("status", {"stage": "thinking"})

    messages = [{"role": "user", "content": request.message}]

    try:
        llm = LLMClient(endpoint=llm_endpoint, model=llm_model)
        try:
            async for chunk in llm.stream_chat_completion(
                messages=messages,
                api_key=api_key,
            ):
                delta = chunk.get("delta", {})
                content = delta.get("content")
                if content:
                    yield await _sse_event("delta", {"content": content})
        finally:
            await llm.aclose()
    except Exception:
        logger.exception("Ошибка при вызове LLM")
        # T-01-01: не пробрасываем детали исключения (может содержать api_key)
        yield await _sse_event("error", {"message": "Ошибка при обращении к LLM", "code": "llm_error"})
        return

    yield await _sse_event("done", {})


@router.post("/chat")
async def chat(
    request: ChatRequest,
    x_llm_api_key: str | None = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_endpoint: str | None = Header(default=None, alias="X-LLM-Endpoint"),
    x_llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
) -> StreamingResponse:
    """Принимает сообщение и стримит SSE-ответ от LLM.

    Headers:
        X-LLM-API-Key (required): API ключ провайдера, не персистируется.
        X-LLM-Endpoint (optional): URL endpoint (default из Settings).
        X-LLM-Model (optional): модель (default из Settings).
    """
    if not x_llm_api_key:
        raise HTTPException(status_code=400, detail="missing api key")

    settings = get_settings()
    llm_endpoint = x_llm_endpoint or settings.default_llm_endpoint
    llm_model = x_llm_model or settings.default_llm_model

    return StreamingResponse(
        _chat_generator(request, x_llm_api_key, llm_endpoint, llm_model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
