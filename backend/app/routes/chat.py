"""POST /chat — SSE streaming через orchestrator tool-calling loop.
POST /chat/confirm — подтверждение опасного execute_code (SEC-01).
"""

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.clients.llm_provider_resolver import detect_provider_id as _detect_provider_id
from app.config import get_settings
from app.models import ChatRequest, ConfirmRequest
from app.orchestrator.interrupt import INTERRUPTS
from app.orchestrator.loop import run_chat_loop
from app.orchestrator.safety import resolve_pending_confirmation
from app.storage.db import get_db
from app.storage.user_secrets_store import get_secret as get_user_secret

# P2.1 (2026-05-23): mapping endpoint → provider_id переехал в
# app.clients.llm_provider_resolver — теперь им пользуется и /llm-config/test
# для fallback на user_secrets. Подробнее — в docstring модуля.

logger = logging.getLogger(__name__)
router = APIRouter()

# W1.4: chat rate-limit. Лимит из settings.chat_rate_limit (env CHAT_RATE_LIMIT).
# Module-level Limiter — переиспользуется между requests. Между тестами вызывать
# chat_limiter.reset() через monkeypatch для изоляции счётчиков.
# RateLimitExceeded handler зарегистрирован в main.py.
chat_limiter = Limiter(key_func=get_remote_address)


def _resolve_chat_rate_limit() -> str:
    """Лениво считывает лимит из Settings. Через functools для slowapi:
    @limiter.limit(callable) — slowapi вызывает callable на каждый request.
    Это позволяет менять лимит через env без рестарта приложения.
    """
    return get_settings().chat_rate_limit


@router.post("/chat")
@chat_limiter.limit(_resolve_chat_rate_limit)
async def chat(
    request: Request,  # noqa: ARG001 — нужен slowapi для key_func(remote_address)
    body: ChatRequest,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    x_llm_api_key: str | None = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_endpoint: str | None = Header(default=None, alias="X-LLM-Endpoint"),
    x_llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    x_anon_enabled: str | None = Header(default=None, alias="X-Anon-Enabled"),
) -> StreamingResponse:
    """Принимает сообщение и стримит SSE-ответ от LLM через tool-calling loop.

    Headers:
        X-LLM-API-Key (optional): API ключ провайдера. Если пуст — backend
            берёт ключ из env DEFAULT_LLM_API_KEY (settings.default_llm_api_key).
            Если и env пуст — 400.
        X-LLM-Endpoint (optional): URL endpoint (default из Settings).
        X-LLM-Model (optional): модель (default из Settings).
        X-Anon-Enabled (optional): "true" → анонимизация включена.

    Body:
        channel_id (required): идентификатор MCP-подключения.
    """
    settings = get_settings()
    llm_endpoint = x_llm_endpoint or settings.default_llm_endpoint
    llm_model = x_llm_model or settings.default_llm_model

    # P2.1 (2026-05-23): новая стратегия резолва ключа (приоритет сверху-вниз):
    #
    #   1. POST /user-secrets с provider_id — backend-only AES-GCM ключ из БД
    #      (это рекомендованный путь, защищён от XSS в localStorage)
    #   2. header X-LLM-API-Key — backward compat для frontend пока migration
    #      идёт. После v1.4.0 этот путь будет удалён.
    #   3. env DEFAULT_LLM_API_KEY_* — embed-ключ в installer (NVIDIA общий ключ)
    #
    # provider_id определяется из endpoint URL — если домен не известен,
    # шаг 1 пропускается и мы идём сразу к header/env.
    provider_id = _detect_provider_id(llm_endpoint)
    stored_key: str | None = None
    if provider_id is not None:
        try:
            stored_key = await get_user_secret(db, provider_id)
        except Exception as exc:  # noqa: BLE001 — БД может быть недоступна на старте
            logger.warning("get_user_secret(%s) failed: %s", provider_id, exc)

    # SEC-12 (M-K0, 2026-05-25): отслеживаем какой путь сработал, чтобы
    # отдать Deprecation header если это header path.
    header_key_used = False
    stripped_header_key = (x_llm_api_key or "").strip()
    if stored_key:
        effective_api_key = stored_key
    elif stripped_header_key:
        effective_api_key = stripped_header_key
        header_key_used = True
    else:
        effective_api_key = settings.resolve_default_api_key(llm_endpoint)

    if not effective_api_key:
        raise HTTPException(status_code=400, detail="missing api key")

    anon_enabled = (x_anon_enabled or "").strip().lower() == "true"

    # SEC-12: response headers — Cache-Control + opt-in Deprecation hint.
    response_headers: dict[str, str] = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    if header_key_used:
        # RFC 8594 (Sunset Header) + Deprecation indicator. Frontend / админ
        # видит warning в Network tab и в response headers. После v1.5.0
        # этот path удалится — мигрируйте на POST /user-secrets.
        # Дата sunset = 31.12.2026 — даёт ~7 месяцев на миграцию клиентов.
        response_headers["Deprecation"] = "true"
        response_headers["Sunset"] = "Thu, 31 Dec 2026 00:00:00 GMT"
        response_headers["Link"] = (
            '</user-secrets>; rel="successor-version"; '
            'title="Migrate to POST /user-secrets (backend-only encrypted storage)"'
        )
        logger.warning(
            "SEC-12 deprecated path: X-LLM-API-Key header used (provider=%s). "
            "Migrate to POST /user-secrets before v1.5.0 / 2026-12-31.",
            provider_id or "unknown",
        )

    return StreamingResponse(
        run_chat_loop(db, body, effective_api_key, llm_endpoint, llm_model, x_anon_enabled=anon_enabled),
        media_type="text/event-stream",
        headers=response_headers,
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


@router.post("/chat/{session_id}/interrupt", status_code=202)
async def interrupt(session_id: str) -> dict:
    """Sprint 2 (Hermes C9): запрос на прерывание активного tool-calling loop.

    Loop проверяет флаг между LLM-вызовами и завершается gracefully — частичный
    ответ + cards уже сохранены в БД, frontend получит done(interrupted=true).

    Идемпотентен: повторный запрос на ту же сессию — то же что один.

    Returns:
        202 Accepted с {"session_id": str, "interrupted": true}.
        Loop может уже завершиться к моменту получения — это OK, no-op.
    """
    if not session_id or not session_id.strip():
        raise HTTPException(status_code=400, detail="session_id обязателен")
    INTERRUPTS.request_interrupt(session_id)
    return {"session_id": session_id, "interrupted": True}
