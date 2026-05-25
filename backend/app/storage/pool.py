"""SQLite connection pool — PERF-1 (M-K0.3).

Раньше у нас было ОДНО aiosqlite.Connection на весь backend (`app.state.db`).
aiosqlite — это thread+queue wrapper над stdlib sqlite3: каждый вызов попадает
в очередь одного фонового потока. Все корутины, дёргающие БД, сериализуются
через эту очередь — даже параллельные SELECT'ы. На hot path (chat orchestrator
loop сохраняет messages + cards + читает историю + sessions list + insights
обновляется) это создаёт сериализованную бутылку, хотя WAL давно включён и
SQLite готов параллелить readers.

Решение — небольшой пул из N одинаковых соединений. Каждое — свой thread queue,
свой connection-handle. WAL mode разруливает concurrency: readers идут
параллельно, writers сериализуются на уровне SQLite через `busy_timeout`.

Сложного writer/reader split не делаем (`Simplicity First`): в нашем профиле
нагрузки одновременных writers мало, ROI на разделение низкий, риск регрессий
выше.

Для `:memory:` БД (используется в тестах) pool схлопывается до 1 connection —
каждое отдельное соединение к `:memory:` это **разная** база, миграции на
одной не видны на другой. Это известная особенность sqlite3, не наш баг.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite

logger = logging.getLogger(__name__)


# По умолчанию 5 connections — компромисс между параллелизмом и резидентной
# памятью. Каждое соединение ест ~2 МБ (cache_size=-64000 = 64 МБ страничный
# кеш разделяется между connections через shared mmap при WAL, но handles +
# prepared-statement caches per-connection). Для desktop приложения хватит.
DEFAULT_POOL_SIZE = 5

# busy_timeout — сколько SQLite ждёт освобождения write-lock'а перед SQLITE_BUSY.
# Поднимаем с дефолтных 0 (мгновенно фейлится) до 10 секунд. С 5 writers и
# короткими транзакциями (commit < 50 мс на messages save) такого окна хватает.
DEFAULT_BUSY_TIMEOUT_MS = 10_000


def _is_memory_path(db_path: str) -> bool:
    """Проверяет, что путь указывает на in-memory SQLite (тестовый сценарий)."""
    if not db_path:
        return False
    normalized = db_path.lower().strip()
    return normalized == ":memory:" or normalized.endswith("/:memory:")


async def _configure_connection(conn: aiosqlite.Connection) -> None:
    """Применяет PRAGMAs к connection. PRAGMA settings per-connection, не global.

    journal_mode=WAL применяется единожды на БД (общее свойство файла), но
    повторный вызов на остальных connections безопасен (no-op).
    """
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA synchronous=NORMAL")
    await conn.execute("PRAGMA cache_size=-64000")
    await conn.execute("PRAGMA temp_store=MEMORY")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute(f"PRAGMA busy_timeout={DEFAULT_BUSY_TIMEOUT_MS}")
    await conn.commit()


class ConnectionPool:
    """Простой FIFO-пул aiosqlite соединений на asyncio.Queue.

    Использование:
        pool = ConnectionPool(db_path, size=5)
        await pool.initialize()
        # ...
        async with pool.acquire() as db:
            await db.execute("SELECT 1")
        # ...
        await pool.close()
    """

    def __init__(self, db_path: str, size: int = DEFAULT_POOL_SIZE) -> None:
        if size < 1:
            raise ValueError("pool size must be >= 1")
        # Для :memory: каждое соединение = отдельная БД → схлопываем до 1.
        if _is_memory_path(db_path) and size > 1:
            logger.info("In-memory SQLite detected: pool size принудительно = 1")
            size = 1
        self._db_path = db_path
        self._size = size
        self._queue: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(maxsize=size)
        self._connections: list[aiosqlite.Connection] = []
        self._initialized = False
        self._closed = False

    @property
    def size(self) -> int:
        return self._size

    @property
    def primary(self) -> aiosqlite.Connection:
        """Первое соединение пула — используется для миграций и backward-compat
        `app.state.db` (для маршрутов, ещё не переведённых на acquire())."""
        if not self._connections:
            raise RuntimeError("Pool not initialized")
        return self._connections[0]

    async def initialize(self) -> None:
        """Создаёт N соединений, применяет PRAGMAs к каждому."""
        if self._initialized:
            return
        for idx in range(self._size):
            conn = await aiosqlite.connect(self._db_path)
            await _configure_connection(conn)
            self._connections.append(conn)
            await self._queue.put(conn)
            logger.debug("Pool connection #%d ready", idx)
        self._initialized = True
        logger.info("SQLite pool готов: %d connections на %s", self._size, self._db_path)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[aiosqlite.Connection]:
        """Берёт соединение из пула, возвращает в finally — даже при exception
        или CancelledError. Без timeout: если все 5 заняты, корутина ждёт."""
        if self._closed:
            raise RuntimeError("Pool is closed")
        if not self._initialized:
            raise RuntimeError("Pool not initialized")
        conn = await self._queue.get()
        try:
            yield conn
        finally:
            # put_nowait безопасен: maxsize == size, мы только что взяли — место есть.
            try:
                self._queue.put_nowait(conn)
            except asyncio.QueueFull:
                # Защита от теоретически невозможного: если кто-то добавил
                # лишний connection вручную — лучше залогировать чем потерять.
                logger.error("Pool queue full при возврате connection — connection потерян")

    async def close(self) -> None:
        """Закрывает все соединения. После close() pool неюзабелен."""
        if self._closed:
            return
        self._closed = True
        for conn in self._connections:
            try:
                await conn.close()
            except Exception:
                logger.exception("Ошибка при закрытии connection из pool")
        self._connections.clear()
        logger.info("SQLite pool закрыт")
