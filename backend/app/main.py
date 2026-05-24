import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.log_setup import setup_file_logging
from app.routes import admin as admin_router
from app.routes import chat as chat_router
from app.routes import clarify as clarify_router
from app.routes import connections as connections_router
from app.routes import diagnostics as diagnostics_router
from app.routes import health as health_router
from app.routes import insights as insights_router
from app.routes import llm_config as llm_config_router
from app.routes import log_cards as log_cards_router
from app.routes import mcp as mcp_router
from app.routes import memory as memory_router
from app.routes import search as search_router
from app.routes import sessions as sessions_router
from app.routes import skills as skills_router
from app.routes import user_secrets as user_secrets_router
from app.storage.db import close_db, init_db

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)
    # Подключаем файловый логгер для диагностики на машине пользователя
    # (stdout backend.exe из Electron уходит в никуда). См. log_setup.py.
    log_path = setup_file_logging()
    if log_path:
        logger.info("Лог-файл: %s", log_path)
    logger.info("Запуск 1С Аналитик backend v%s", settings.app_version)
    # SEC-04: предупреждение если production без CORS origins
    if settings.environment == "prod" and not settings.cors_origins_list:
        logger.warning(
            "CORS origins пустые в production. "
            "Установите BACKEND_ALLOWED_ORIGINS=https://your-frontend.example.com"
        )
    await init_db(app)
    yield
    await close_db(app)
    logger.info("Backend остановлен")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="1С Аналитик",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # W1.4: rate-limit на /chat (slowapi). Защита от DoS: UI-баг или
    # злонамеренный спам не должны положить backend. Лимит per IP, дефолт
    # 30/minute из settings.chat_rate_limit (env CHAT_RATE_LIMIT).
    # Декоратор + Limiter живут в routes/chat.py. Здесь только handler 429.
    from app.routes.chat import chat_limiter
    app.state.limiter = chat_limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        # Отдаём 429 в формате аналогичном fastapi-error: detail + retry hint.
        # Frontend `parseError` уже умеет обрабатывать 429 → user-friendly toast.
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Слишком много запросов. Подождите минуту и повторите.",
                "code": "rate_limit_exceeded",
            },
            headers={"Retry-After": "60"},
        )

    # W3.15 (2026-05-22): сузили allow_methods с "*" до явного списка
    # фактически используемых: GET, POST, PATCH, DELETE, OPTIONS. Раньше "*" с
    # allow_credentials=True давало wider CSRF-surface (любой PUT/HEAD/TRACE
    # из браузера атакующего был бы пропущен через CORS). credentials нужны
    # для localhost dev-режима (cookies для session, если включится),
    # поэтому allow_credentials оставлен True.
    #
    # 2026-05-24 (QA finding-11): PATCH добавлен — без него frontend смена
    # модели ИИ (ModelBadge popover) и редактирование LLM-конфига падали с
    # CORS preflight 400 и сам PATCH 503. Бизнес-логика PATCH использовалась
    # давно (lib/api.ts:updateLLMConfig), но прошёл регресс при W3.15.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health_router.router)
    app.include_router(chat_router.router)
    app.include_router(mcp_router.router)
    app.include_router(sessions_router.router)
    app.include_router(connections_router.router)
    app.include_router(llm_config_router.router)
    app.include_router(log_cards_router.router)
    app.include_router(search_router.router)
    app.include_router(admin_router.router)
    app.include_router(diagnostics_router.router)
    app.include_router(memory_router.router)
    app.include_router(skills_router.router)
    app.include_router(clarify_router.router)
    app.include_router(insights_router.router)
    # P2.1 (2026-05-23): backend-only API key store
    app.include_router(user_secrets_router.router)

    return app


app = create_app()
