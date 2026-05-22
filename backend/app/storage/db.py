import logging
from collections.abc import AsyncIterator

import aiosqlite
from fastapi import Request

from app.config import get_settings
from app.storage.migrations import apply_migrations
from app.storage.seed import seed_defaults

logger = logging.getLogger(__name__)


async def init_db(app: object) -> None:
    """Открывает соединение с SQLite, включает WAL, прогоняет миграции, сидит дефолты."""
    settings = get_settings()
    db_path = settings.sqlite_path
    logger.info("Открываем SQLite: %s", db_path)

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    # W3.3 (2026-05-22): SQLite PRAGMA tuning для production.
    # - journal_mode=WAL — write-ahead logging, параллельные readers, минус
    #   write-lock на reads (уже было).
    # - synchronous=NORMAL — fsync только на checkpoint, не на каждой записи.
    #   FULL (дефолт) даёт +20-40% устойчивости к crash'у системы, но мы и
    #   так в Electron desktop и WAL покрывает большинство сценариев.
    # - cache_size=-64000 — 64 MB страничного кеша (отрицательное число = KB).
    #   По умолчанию 2 MB — слишком мало для realtime full-text search по
    #   messages_fts при большой истории сессий.
    # - temp_store=MEMORY — временные таблицы (для CTE/UNION) держим в RAM.
    # - foreign_keys=ON — SQLite по умолчанию ИГНОРИРУЕТ FK constraints.
    #   Без этого ON DELETE CASCADE не работает и при удалении сессий
    #   могут оставаться orphan messages.
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    await db.execute("PRAGMA cache_size=-64000")
    await db.execute("PRAGMA temp_store=MEMORY")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.commit()

    await apply_migrations(db)

    if settings.seed_on_startup:
        await seed_defaults(db, settings)

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
