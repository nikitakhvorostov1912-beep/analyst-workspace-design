import logging
from collections.abc import AsyncIterator

import aiosqlite
from fastapi import Request

from app.config import get_settings
from app.storage.migrations import apply_migrations

logger = logging.getLogger(__name__)


async def init_db(app: object) -> None:
    """Открывает соединение с SQLite, включает WAL, прогоняет миграции."""
    settings = get_settings()
    db_path = settings.sqlite_path
    logger.info("Открываем SQLite: %s", db_path)

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    await db.execute("PRAGMA journal_mode=WAL")
    await db.commit()

    await apply_migrations(db)

    app.state.db = db  # type: ignore[attr-defined]
    logger.info("SQLite готова")


async def close_db(app: object) -> None:
    """Закрывает соединение с SQLite."""
    db: aiosqlite.Connection | None = getattr(app.state, "db", None)  # type: ignore[attr-defined]
    if db is not None:
        await db.close()
        logger.info("SQLite соединение закрыто")


async def get_db(request: Request) -> AsyncIterator[aiosqlite.Connection]:
    """FastAPI dependency — возвращает aiosqlite соединение из app.state."""
    yield request.app.state.db
