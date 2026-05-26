"""Tests for backend/app/knowledge/indexer_state.py (M-K2.2).

Покрытие:
- Migration v12 — таблица создаётся, индексы есть
- start_run — создаёт row со status='running', double-start raises
- complete_run — переход done | failed, валидация status
- fail_run_with_error — manual failure path
- get_latest_run / get_current_running — фильтрация по статусу
- is_running — корректно ловит running rows
"""

from __future__ import annotations

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.indexer import IndexerProgress
from app.knowledge.indexer_state import (
    IndexerAlreadyRunningError,
    complete_run,
    fail_run_with_error,
    get_current_running,
    get_latest_run,
    is_running,
    start_run,
)
from app.storage.migrations import apply_migrations


@pytest_asyncio.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


def _make_progress(
    status: str,
    *,
    written: int = 0,
    error: str | None = None,
    channel_id: str = "ch-1",
) -> IndexerProgress:
    return IndexerProgress(
        channel_id=channel_id,
        objects_total=written,
        objects_written=written,
        objects_skipped=0,
        duration_ms=42,
        started_at="2026-05-26T09:00:00+00:00",
        finished_at="2026-05-26T09:00:01+00:00",
        status=status,
        error=error,
    )


# ---------- Migration v12 ----------


@pytest.mark.asyncio
async def test_migration_v12_creates_index_runs_table(db):
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='index_runs'"
    )
    row = await cursor.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_migration_v12_creates_channel_index(db):
    """Индекс по (channel_id, started_at DESC) должен существовать."""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_index_runs_channel'"
    )
    row = await cursor.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_migration_v12_status_check_constraint(db):
    """CHECK CONSTRAINT блокирует невалидный status."""
    with pytest.raises(aiosqlite.IntegrityError):
        await db.execute(
            "INSERT INTO index_runs (channel_id, status) VALUES (?, ?)",
            ("ch-1", "BOGUS"),
        )
        await db.commit()


# ---------- start_run ----------


@pytest.mark.asyncio
async def test_start_run_creates_running_row(db):
    run = await start_run(db, "ch-1")
    assert run.channel_id == "ch-1"
    assert run.status == "running"
    assert run.started_at is not None
    assert run.finished_at is None
    assert run.id > 0


@pytest.mark.asyncio
async def test_start_run_raises_when_already_running(db):
    await start_run(db, "ch-1")
    with pytest.raises(IndexerAlreadyRunningError):
        await start_run(db, "ch-1")


@pytest.mark.asyncio
async def test_start_run_different_channels_dont_conflict(db):
    run_a = await start_run(db, "ch-A")
    run_b = await start_run(db, "ch-B")
    assert run_a.id != run_b.id
    assert await is_running(db, "ch-A") is True
    assert await is_running(db, "ch-B") is True


@pytest.mark.asyncio
async def test_start_run_with_raise_disabled_allows_double(db):
    await start_run(db, "ch-1")
    run2 = await start_run(db, "ch-1", raise_if_running=False)
    assert run2.status == "running"


# ---------- complete_run ----------


@pytest.mark.asyncio
async def test_complete_run_done_path(db):
    run = await start_run(db, "ch-1")
    progress = _make_progress("done", written=42)
    completed = await complete_run(db, run.id, progress)

    assert completed.id == run.id
    assert completed.status == "done"
    assert completed.objects_written == 42
    assert completed.duration_ms == 42
    assert completed.finished_at == "2026-05-26T09:00:01+00:00"
    assert completed.error is None
    assert await is_running(db, "ch-1") is False


@pytest.mark.asyncio
async def test_complete_run_failed_path(db):
    run = await start_run(db, "ch-1")
    progress = _make_progress("failed", error="MCP timeout")
    completed = await complete_run(db, run.id, progress)

    assert completed.status == "failed"
    assert completed.error == "MCP timeout"
    assert completed.objects_written == 0
    assert await is_running(db, "ch-1") is False


@pytest.mark.asyncio
async def test_complete_run_rejects_invalid_status(db):
    run = await start_run(db, "ch-1")
    progress = _make_progress("running")  # неправильно — running это start, не complete
    with pytest.raises(ValueError, match="invalid status"):
        await complete_run(db, run.id, progress)


# ---------- fail_run_with_error ----------


@pytest.mark.asyncio
async def test_fail_run_with_error_marks_failed(db):
    """Когда исключение случилось вне bulk_refresh (нет IndexerProgress)."""
    run = await start_run(db, "ch-1")
    failed = await fail_run_with_error(db, run.id, "DB connection lost")

    assert failed.status == "failed"
    assert failed.error == "DB connection lost"
    assert failed.finished_at is not None
    assert await is_running(db, "ch-1") is False


# ---------- get_latest_run / get_current_running ----------


@pytest.mark.asyncio
async def test_get_latest_run_returns_most_recent(db):
    r1 = await start_run(db, "ch-1")
    await complete_run(db, r1.id, _make_progress("done", written=10))
    r2 = await start_run(db, "ch-1")
    await complete_run(db, r2.id, _make_progress("done", written=20))

    latest = await get_latest_run(db, "ch-1")
    assert latest is not None
    assert latest.id == r2.id
    assert latest.objects_written == 20


@pytest.mark.asyncio
async def test_get_latest_run_returns_none_for_unknown_channel(db):
    assert await get_latest_run(db, "ghost") is None


@pytest.mark.asyncio
async def test_get_current_running_filters_to_running(db):
    """get_current_running должен игнорировать done/failed строки."""
    r1 = await start_run(db, "ch-1")
    await complete_run(db, r1.id, _make_progress("done", written=10))

    # Нет running → None
    assert await get_current_running(db, "ch-1") is None

    r2 = await start_run(db, "ch-1")
    current = await get_current_running(db, "ch-1")
    assert current is not None
    assert current.id == r2.id
    assert current.status == "running"


@pytest.mark.asyncio
async def test_get_current_running_returns_none_when_no_runs(db):
    assert await get_current_running(db, "ch-1") is None


# ---------- to_response_dict ----------


@pytest.mark.asyncio
async def test_to_response_dict_includes_all_fields(db):
    run = await start_run(db, "ch-1")
    completed = await complete_run(db, run.id, _make_progress("done", written=7))
    payload = completed.to_response_dict()

    assert set(payload.keys()) == {
        "id", "channel_id", "status",
        "started_at", "finished_at", "duration_ms",
        "objects_total", "objects_written", "objects_skipped",
        "error",
    }
    assert payload["status"] == "done"
    assert payload["objects_written"] == 7
