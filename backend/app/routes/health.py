import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends

from app.config import get_settings
from app.models import HealthResponse
from app.storage.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

DbDep = Annotated[aiosqlite.Connection, Depends(get_db)]


@router.get("/health", response_model=HealthResponse)
async def health(db: DbDep) -> HealthResponse:
    """Проверяет состояние сервиса и соединение с БД."""
    settings = get_settings()
    db_status: str = "ok"
    try:
        await db.execute("SELECT 1")
    except Exception:
        logger.exception("Ошибка проверки БД")
        db_status = "error"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version=settings.app_version,
        db=db_status,  # type: ignore[arg-type]
    )


@router.get("/")
async def root() -> dict:
    """Корневой эндпоинт — информация о сервисе."""
    settings = get_settings()
    return {"name": "1c-analyst-backend", "version": settings.app_version}
