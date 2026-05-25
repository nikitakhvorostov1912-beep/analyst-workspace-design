"""Тесты ConnectionPool — PERF-1 (M-K0.3).

Проверяем:
1. Pool корректно инициализируется (N connections с PRAGMAs).
2. Pool схлопывается до 1 для :memory: (защита от тестов с разной БД на connection).
3. acquire/release работают в context-manager, возврат в очередь даже на exception.
4. **Performance contract**: параллельные SELECT'ы через pool НЕ сериализуются
   через единственный thread-queue aiosqlite (это и был корневой PERF-1).
"""

from __future__ import annotations

import asyncio
import time

import aiosqlite
import pytest

from app.storage.pool import (
    DEFAULT_BUSY_TIMEOUT_MS,
    DEFAULT_POOL_SIZE,
    ConnectionPool,
    _is_memory_path,
)


# ===== Базовые свойства =====


def test_is_memory_path_detection():
    assert _is_memory_path(":memory:")
    assert _is_memory_path("/var/run/:memory:")  # aiosqlite URI form
    assert _is_memory_path(":MEMORY:")  # case-insensitive
    assert not _is_memory_path("./app.db")
    assert not _is_memory_path("")


@pytest.mark.asyncio
async def test_pool_initializes_n_connections(tmp_path):
    db_path = str(tmp_path / "pool_test.db")
    pool = ConnectionPool(db_path, size=5)
    await pool.initialize()
    try:
        assert pool.size == 5
        assert len(pool._connections) == 5
        # primary — первое
        assert pool.primary is pool._connections[0]
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pool_memory_path_collapses_to_one():
    """Для :memory: каждое соединение — отдельная БД, pool обязан схлопнуться."""
    pool = ConnectionPool(":memory:", size=5)
    await pool.initialize()
    try:
        assert pool.size == 1
        assert len(pool._connections) == 1
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pool_pragmas_applied_per_connection(tmp_path):
    """Каждое соединение должно иметь WAL/foreign_keys/busy_timeout."""
    db_path = str(tmp_path / "pragmas.db")
    pool = ConnectionPool(db_path, size=3)
    await pool.initialize()
    try:
        for conn in pool._connections:
            async with conn.execute("PRAGMA foreign_keys") as cur:
                row = await cur.fetchone()
                assert row[0] == 1, "foreign_keys должен быть ON на каждом connection"
            async with conn.execute("PRAGMA busy_timeout") as cur:
                row = await cur.fetchone()
                assert row[0] == DEFAULT_BUSY_TIMEOUT_MS
        # WAL — общее свойство БД (включается единожды), проверяем что включён
        async with pool.primary.execute("PRAGMA journal_mode") as cur:
            row = await cur.fetchone()
            assert row[0].lower() == "wal"
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pool_invalid_size_raises():
    with pytest.raises(ValueError, match="pool size must be >= 1"):
        ConnectionPool(":memory:", size=0)


# ===== acquire/release контракт =====


@pytest.mark.asyncio
async def test_acquire_returns_connection_to_queue(tmp_path):
    db_path = str(tmp_path / "acq.db")
    pool = ConnectionPool(db_path, size=2)
    await pool.initialize()
    try:
        # Берём оба, возвращаем
        async with pool.acquire() as c1:
            async with pool.acquire() as c2:
                assert c1 is not c2
                assert pool._queue.qsize() == 0
            assert pool._queue.qsize() == 1
        assert pool._queue.qsize() == 2
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_acquire_returns_connection_on_exception(tmp_path):
    """Connection возвращается в pool даже если корутина внутри упала."""
    db_path = str(tmp_path / "acq_exc.db")
    pool = ConnectionPool(db_path, size=2)
    await pool.initialize()
    try:
        with pytest.raises(RuntimeError, match="boom"):
            async with pool.acquire() as _conn:
                raise RuntimeError("boom")
        # Connection должен вернуться, иначе queue.qsize() == 1
        assert pool._queue.qsize() == 2
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pool_close_idempotent(tmp_path):
    db_path = str(tmp_path / "close.db")
    pool = ConnectionPool(db_path, size=2)
    await pool.initialize()
    await pool.close()
    await pool.close()  # второй раз — no-op, не падать


@pytest.mark.asyncio
async def test_acquire_after_close_raises(tmp_path):
    db_path = str(tmp_path / "after_close.db")
    pool = ConnectionPool(db_path, size=1)
    await pool.initialize()
    await pool.close()
    with pytest.raises(RuntimeError, match="closed"):
        async with pool.acquire():
            pass


# ===== Performance contract — это и был корневой PERF-1 =====


@pytest.mark.asyncio
async def test_parallel_reads_use_pool_capacity(tmp_path):
    """5 параллельных SELECT'ов через pool НЕ сериализуются на thread queue.

    Берём CPU-bound CTE (recursive count) — SQLite держит GIL released в sqlite3
    C-коде, поэтому 5 разных connections с 5 разных потоков должны идти
    параллельно. На ОДНОМ connection (как было до PERF-1) все 5 пошли бы через
    один thread queue aiosqlite — строго последовательно.

    Сравниваем sequential на одном connection (== поведение до PERF-1) с
    parallel через pool. Не абсолютное время (CI-машины разные) — отношение.
    На multi-core машине pool должен дать заметное ускорение.

    Порог 0.75 (а не идеальный 0.2) выбран консервативно: SQLite WAL parallel
    reads имеют небольшой overhead на page cache mutex; randomblob в Python
    wrapper'ах добавляет sync; ratio 0.5–0.7 — типичный реальный выигрыш.
    """
    db_path = str(tmp_path / "perf.db")
    pool = ConnectionPool(db_path, size=5)
    await pool.initialize()
    try:
        # CPU-bound recursive CTE — sqlite3 considers это работой С-кода,
        # релизит GIL → реальный параллелизм между потоками connections.
        # 200000 итераций → ~30-80 мс на одно выполнение, достаточно чтобы
        # overhead aiosqlite Python wrapper'ов не доминировал.
        query = (
            "WITH RECURSIVE c(x) AS ("
            "  SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < 200000"
            ") SELECT COUNT(*), SUM(x) FROM c"
        )

        # 1. Прогрев: первый запрос дороже из-за prepare + page cache miss.
        async with pool.acquire() as conn:
            await conn.execute_fetchall(query)

        # 2. Sequential: 5 запросов на ОДНОМ connection (поведение до PERF-1).
        async with pool.acquire() as conn:
            t0 = time.perf_counter()
            for _ in range(5):
                await conn.execute_fetchall(query)
            sequential_time = time.perf_counter() - t0

        # 3. Parallel через pool: 5 запросов на 5 разных connections.
        # Каждый async with получит свой connection из FIFO queue.
        seen_connections: set[int] = set()

        async def _run_one() -> None:
            async with pool.acquire() as conn:
                seen_connections.add(id(conn))
                await conn.execute_fetchall(query)

        t0 = time.perf_counter()
        await asyncio.gather(*[_run_one() for _ in range(5)])
        parallel_time = time.perf_counter() - t0

        # Sanity: должны были задействовать все 5 connections (gather'ом).
        assert len(seen_connections) == 5, (
            f"Pool не отдал 5 разных connections, только {len(seen_connections)}"
        )

        # Sanity: запрос должен быть заметным (> 10 мс), иначе overhead доминирует.
        assert sequential_time > 0.05, (
            f"Sequential {sequential_time*1000:.2f} мс — слишком быстро для бенчмарка"
        )

        # PERF-1 contract: parallel < 75% от sequential.
        # На single connection было бы ~100% (всё через один thread queue).
        ratio = parallel_time / sequential_time
        assert ratio < 0.75, (
            f"Параллелизм pool не работает: parallel={parallel_time*1000:.1f} мс, "
            f"sequential={sequential_time*1000:.1f} мс, ratio={ratio:.2f} "
            f"(ожидали < 0.75)"
        )
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_parallel_writes_serialize_safely(tmp_path):
    """5 параллельных INSERT'ов через pool корректно сериализуются на уровне SQLite.

    SQLite WAL даёт parallel reads + 1 writer. busy_timeout=10s обеспечивает
    что 5 writers корректно становятся в очередь без SQLITE_BUSY ошибок.
    """
    db_path = str(tmp_path / "writes.db")
    pool = ConnectionPool(db_path, size=5)
    await pool.initialize()
    try:
        # Setup
        async with pool.acquire() as conn:
            await conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v INTEGER)")
            await conn.commit()

        async def _insert(value: int) -> None:
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO t (v) VALUES (?)", (value,))
                await conn.commit()

        await asyncio.gather(*[_insert(i) for i in range(50)])

        # Все 50 записей должны быть. Без busy_timeout некоторые упали бы.
        async with pool.acquire() as conn:
            async with conn.execute("SELECT COUNT(*) FROM t") as cur:
                row = await cur.fetchone()
                assert row[0] == 50
    finally:
        await pool.close()
