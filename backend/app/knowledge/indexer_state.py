"""Indexer state machine — управление таблицей `index_runs` (M-K2.2).

CRUD над одной "записью одного indexing запуска". Чистые async-функции,
ничего о HTTP/SSE/background не знают — caller (route в knowledge.py +
background task) сам оркеструет.

Состояния перехода:
    pending  → running → done
                     ↘ failed
    pending  → failed  (если стартовали + не успели начать MCP-вызов)

«Текущий running» — это row со status='running' и channel_id=X.
По бизнес-правилу М-K2.2 может быть **максимум один running** на канал
(защита от двойного start). Проверка через `is_running()`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import aiosqlite

from app.knowledge.indexer import IndexerProgress

logger = logging.getLogger(__name__)


IndexRunStatus = Literal["pending", "running", "done", "failed"]


@dataclass(frozen=True, slots=True)
class IndexRun:
    """Snapshot одной row из index_runs."""

    id: int
    channel_id: str
    status: IndexRunStatus
    started_at: str | None
    finished_at: str | None
    duration_ms: int | None
    objects_total: int
    objects_written: int
    objects_skipped: int
    error: str | None

    def to_response_dict(self) -> dict:
        """JSON-friendly dict для HTTP endpoint."""
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "objects_total": self.objects_total,
            "objects_written": self.objects_written,
            "objects_skipped": self.objects_skipped,
            "error": self.error,
        }


class IndexerAlreadyRunningError(Exception):
    """Канал уже имеет активный (status='running') indexer run."""


def _row_to_run(row: tuple) -> IndexRun:
    """row из SELECT → IndexRun. Порядок колонок фиксирован в SELECT'е ниже."""
    return IndexRun(
        id=row[0],
        channel_id=row[1],
        status=row[2],
        started_at=row[3],
        finished_at=row[4],
        duration_ms=row[5],
        objects_total=row[6] or 0,
        objects_written=row[7] or 0,
        objects_skipped=row[8] or 0,
        error=row[9],
    )


_SELECT_COLUMNS = (
    "id, channel_id, status, started_at, finished_at, duration_ms, "
    "objects_total, objects_written, objects_skipped, error"
)


async def is_running(db: aiosqlite.Connection, channel_id: str) -> bool:
    """Возвращает True если у канала уже есть row со status='running'."""
    cursor = await db.execute(
        "SELECT 1 FROM index_runs WHERE channel_id = ? AND status = 'running' LIMIT 1",
        (channel_id,),
    )
    row = await cursor.fetchone()
    return row is not None


async def start_run(
    db: aiosqlite.Connection,
    channel_id: str,
    *,
    raise_if_running: bool = True,
) -> IndexRun:
    """Создаёт новый row со status='running' для канала.

    Args:
        db: aiosqlite connection
        channel_id: канал
        raise_if_running: True → IndexerAlreadyRunningError если уже running.
                          False → создаст ещё одну running строку (не рекомендуется).

    Returns:
        IndexRun свежесозданной row.

    Raises:
        IndexerAlreadyRunningError если raise_if_running=True и уже есть running.
    """
    if raise_if_running and await is_running(db, channel_id):
        raise IndexerAlreadyRunningError(
            f"Канал {channel_id!r} уже имеет активный indexer run. "
            "Дождитесь завершения или используйте GET /knowledge/{channel_id}/index/status."
        )

    cursor = await db.execute(
        """
        INSERT INTO index_runs (channel_id, status)
        VALUES (?, 'running')
        """,
        (channel_id,),
    )
    await db.commit()

    new_id = cursor.lastrowid
    if new_id is None:
        # Не должно случиться — но если случилось, читаем по channel_id.
        raise RuntimeError("Не удалось получить ID новой index_runs строки")

    return await _fetch_by_id(db, new_id)


async def complete_run(
    db: aiosqlite.Connection,
    run_id: int,
    progress: IndexerProgress,
) -> IndexRun:
    """Обновляет row до status из progress (done | failed).

    Args:
        db: aiosqlite connection
        run_id: ID row из start_run()
        progress: результат bulk_refresh_metadata_cache

    Returns:
        Обновлённый IndexRun.
    """
    if progress.status not in ("done", "failed"):
        raise ValueError(
            f"complete_run: invalid status в progress: {progress.status!r}. "
            "Допустимы только 'done' | 'failed'."
        )

    await db.execute(
        """
        UPDATE index_runs
        SET status = ?,
            started_at = ?,
            finished_at = ?,
            duration_ms = ?,
            objects_total = ?,
            objects_written = ?,
            objects_skipped = ?,
            error = ?
        WHERE id = ?
        """,
        (
            progress.status,
            progress.started_at,
            progress.finished_at,
            progress.duration_ms,
            progress.objects_total,
            progress.objects_written,
            progress.objects_skipped,
            progress.error,
            run_id,
        ),
    )
    await db.commit()

    return await _fetch_by_id(db, run_id)


async def fail_run_with_error(
    db: aiosqlite.Connection,
    run_id: int,
    error: str,
) -> IndexRun:
    """Помечает row как failed с заданным error. Для случаев когда исключение
    случилось ВНЕ bulk_refresh (не вернул IndexerProgress).
    """
    finished_iso = datetime.now().isoformat()
    await db.execute(
        """
        UPDATE index_runs
        SET status = 'failed',
            finished_at = ?,
            error = ?
        WHERE id = ?
        """,
        (finished_iso, error, run_id),
    )
    await db.commit()
    return await _fetch_by_id(db, run_id)


async def get_latest_run(
    db: aiosqlite.Connection,
    channel_id: str,
) -> IndexRun | None:
    """Возвращает последний (по started_at DESC) run для канала или None."""
    cursor = await db.execute(
        f"""
        SELECT {_SELECT_COLUMNS}
        FROM index_runs
        WHERE channel_id = ?
        ORDER BY started_at DESC, id DESC
        LIMIT 1
        """,
        (channel_id,),
    )
    row = await cursor.fetchone()
    return _row_to_run(row) if row else None


async def get_current_running(
    db: aiosqlite.Connection,
    channel_id: str,
) -> IndexRun | None:
    """Возвращает текущий running run для канала или None."""
    cursor = await db.execute(
        f"""
        SELECT {_SELECT_COLUMNS}
        FROM index_runs
        WHERE channel_id = ? AND status = 'running'
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (channel_id,),
    )
    row = await cursor.fetchone()
    return _row_to_run(row) if row else None


async def _fetch_by_id(db: aiosqlite.Connection, run_id: int) -> IndexRun:
    cursor = await db.execute(
        f"SELECT {_SELECT_COLUMNS} FROM index_runs WHERE id = ?",
        (run_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise RuntimeError(f"index_runs row id={run_id} не найдена после INSERT/UPDATE")
    return _row_to_run(row)
