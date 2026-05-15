import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import chat as chat_router
from app.routes import connections as connections_router
from app.routes import health as health_router
from app.routes import log_cards as log_cards_router
from app.routes import mcp as mcp_router
from app.routes import search as search_router
from app.routes import sessions as sessions_router
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router.router)
    app.include_router(chat_router.router)
    app.include_router(mcp_router.router)
    app.include_router(sessions_router.router)
    app.include_router(connections_router.router)
    app.include_router(log_cards_router.router)
    app.include_router(search_router.router)

    return app


app = create_app()
