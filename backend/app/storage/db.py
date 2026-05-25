import logging
from collections.abc import AsyncIterator

import aiosqlite
from fastapi import Request

from app.config import get_settings
from app.storage.migrations import apply_migrations
from app.storage.pool import DEFAULT_POOL_SIZE, ConnectionPool
from app.storage.seed import seed_defaults

logger = logging.getLogger(__name__)


async def init_db(app: object) -> None:
    """Создаёт SQLite connection pool, прогоняет миграции, сидит дефолты.

    PERF-1 (M-K0.3): раньше было одно aiosqlite.Connection в `app.state.db`,
    что сериализовало все запросы через единственный thread-queue aiosqlite.
    Теперь pool из N connections (по умолчанию 5) — параллельные SELECT'ы
    идут параллельно (WAL разруливает concurrency на уровне SQLite).

    Миграции и seed выполняются на primary connection (первое в пуле). Это
    единственное место, где обращаемся к connection напрямую через атрибут
    pool.primary — миграции должны быть однократны и не пересекаться с другими
    операциями (на старте приложения других нет).
    """
    settings = get_settings()
    db_path = settings.sqlite_path
    logger.info("Открываем SQLite pool: %s", db_path)

    pool = ConnectionPool(db_path, size=DEFAULT_POOL_SIZE)
    await pool.initialize()

    # Миграции и seed — на primary, до начала работы маршрутов.
    primary = pool.primary
    await apply_migrations(primary)

    if settings.seed_on_startup:
        await seed_defaults(primary, settings)

    app.state.db_pool = pool  # type: ignore[attr-defined]
    # Backward-compat: маршруты, ещё не переведённые на pool.acquire(),
    # читают `app.state.db`. Им мы отдаём primary — конкуренции с pool
    # не будет, потому что primary при init попадает в очередь и достаётся
    # обратно через acquire() как обычное соединение. Но если кто-то держит
    # ссылку на `app.state.db` и одновременно дёргает `acquire()`, может
    # получить тот же handle и сериализоваться. Это допустимая регрессия
    # для незатронутых маршрутов — PERF-1 чинит hot path (chat).
    app.state.db = primary  # type: ignore[attr-defined]
    logger.info("SQLite готова (pool size=%d)", pool.size)


async def close_db(app: object) -> None:
    """Закрывает pool. Идемпотентно."""
    pool: ConnectionPool | None = getattr(app.state, "db_pool", None)  # type: ignore[attr-defined]
    if pool is not None:
        await pool.close()
        logger.info("SQLite соединения закрыты")


async def get_db(request: Request) -> AsyncIterator[aiosqlite.Connection]:
    """FastAPI dependency — берёт connection из pool через acquire/release.

    Каждый запрос получает СВОЙ connection из pool на время обработки.
    Это включает параллелизм для всех маршрутов через `Depends(get_db)`:
    chat (hot path), admin, sessions, health и т.д.
    """
    pool: ConnectionPool = request.app.state.db_pool
    async with pool.acquire() as conn:
        yield conn
