"""Тесты для incremental refresh — M-K2.3.

Покрытие:
- compute_cache_diff: pure function (added/updated/removed/unchanged)
- write_cache_batch_incremental: применение diff к metadata_cache
- bulk_refresh_metadata_cache(incremental=True): integration
- bulk_refresh_metadata_cache(incremental=False): legacy режим
- fetched_at preservation для unchanged rows
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.indexer import (
    CacheDiff,
    NormalizedMetadata,
    bulk_refresh_metadata_cache,
    compute_cache_diff,
    write_cache_batch,
    write_cache_batch_incremental,
)
from app.storage.migrations import apply_migrations


@pytest_asyncio.fixture
async def db_ready():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


def _nm(name: str, *, obj_type: str = "Документ", presentation: str | None = None) -> NormalizedMetadata:
    return NormalizedMetadata(
        object_path=f"{obj_type}.{name}",
        object_type=obj_type,
        name=name,
        presentation=presentation,
    )


# ---------- compute_cache_diff (pure) ----------


def test_diff_empty_existing_all_added():
    objs = [_nm("A"), _nm("B"), _nm("C")]
    diff = compute_cache_diff([], objs)
    assert len(diff.added) == 3
    assert diff.updated == []
    assert diff.removed == []
    assert diff.unchanged == []
    assert diff.total_changes == 3


def test_diff_empty_new_all_removed():
    existing = [
        ("Документ.A", "Документ", "A", None),
        ("Документ.B", "Документ", "B", None),
    ]
    diff = compute_cache_diff(existing, [])
    assert diff.added == []
    assert diff.updated == []
    assert set(diff.removed) == {"Документ.A", "Документ.B"}


def test_diff_unchanged_when_identical():
    existing = [
        ("Документ.A", "Документ", "A", "Презент"),
    ]
    objs = [_nm("A", presentation="Презент")]
    diff = compute_cache_diff(existing, objs)
    assert diff.added == []
    assert diff.updated == []
    assert diff.removed == []
    assert diff.unchanged == ["Документ.A"]
    assert diff.total_changes == 0


def test_diff_updated_when_presentation_changed():
    existing = [
        ("Документ.A", "Документ", "A", "Старое"),
    ]
    objs = [_nm("A", presentation="Новое")]
    diff = compute_cache_diff(existing, objs)
    assert len(diff.updated) == 1
    assert diff.updated[0].presentation == "Новое"


def test_diff_updated_when_type_changed():
    existing = [
        ("Документ.A", "Справочник", "A", None),  # был справочник
    ]
    objs = [_nm("A", obj_type="Документ")]
    diff = compute_cache_diff(existing, objs)
    assert len(diff.updated) == 1


def test_diff_mixed():
    existing = [
        ("Документ.A", "Документ", "A", None),     # unchanged
        ("Документ.B", "Документ", "B", "Old"),    # updated
        ("Документ.C", "Документ", "C", None),     # removed
    ]
    objs = [
        _nm("A"),  # unchanged
        _nm("B", presentation="New"),  # updated
        _nm("D"),  # added
    ]
    diff = compute_cache_diff(existing, objs)
    assert [o.name for o in diff.added] == ["D"]
    assert [o.name for o in diff.updated] == ["B"]
    assert diff.removed == ["Документ.C"]
    assert diff.unchanged == ["Документ.A"]
    assert diff.total_changes == 3


# ---------- write_cache_batch_incremental ----------


@pytest.mark.asyncio
async def test_incremental_writes_added_into_empty_cache(db_ready):
    diff = await write_cache_batch_incremental(
        db_ready, "ch-1", [_nm("A"), _nm("B")]
    )
    assert len(diff.added) == 2
    assert diff.updated == []
    assert diff.removed == []

    cursor = await db_ready.execute(
        "SELECT object_path FROM metadata_cache WHERE channel_id = ? ORDER BY object_path",
        ("ch-1",),
    )
    rows = await cursor.fetchall()
    assert [r[0] for r in rows] == ["Документ.A", "Документ.B"]


@pytest.mark.asyncio
async def test_incremental_removes_objects_not_in_new_set(db_ready):
    # Заполняем cache
    await write_cache_batch(
        db_ready, "ch-1",
        [_nm("A"), _nm("B"), _nm("C")],
        replace_existing=True,
    )

    # Apply diff где C удалён, A unchanged, B unchanged
    diff = await write_cache_batch_incremental(
        db_ready, "ch-1", [_nm("A"), _nm("B")],
    )
    assert diff.removed == ["Документ.C"]
    assert sorted([o.object_path for o in diff.unchanged_objects()] if hasattr(diff, "unchanged_objects") else diff.unchanged) == ["Документ.A", "Документ.B"]

    # Cache содержит только A и B
    cursor = await db_ready.execute(
        "SELECT object_path FROM metadata_cache WHERE channel_id = ? ORDER BY object_path",
        ("ch-1",),
    )
    rows = await cursor.fetchall()
    assert [r[0] for r in rows] == ["Документ.A", "Документ.B"]


@pytest.mark.asyncio
async def test_incremental_updates_presentation(db_ready):
    await write_cache_batch(
        db_ready, "ch-1",
        [_nm("A", presentation="Старое")],
        replace_existing=True,
    )

    diff = await write_cache_batch_incremental(
        db_ready, "ch-1",
        [_nm("A", presentation="Новое")],
    )
    assert len(diff.updated) == 1

    cursor = await db_ready.execute(
        "SELECT presentation FROM metadata_cache WHERE channel_id = ? AND object_path = ?",
        ("ch-1", "Документ.A"),
    )
    row = await cursor.fetchone()
    assert row[0] == "Новое"


@pytest.mark.asyncio
async def test_incremental_isolates_channels(db_ready):
    """Diff на ch-A не должен трогать ch-B."""
    await write_cache_batch(
        db_ready, "ch-A", [_nm("A")], replace_existing=True,
    )
    await write_cache_batch(
        db_ready, "ch-B", [_nm("B")], replace_existing=True,
    )

    # Diff на ch-A заменяет A на C
    diff = await write_cache_batch_incremental(
        db_ready, "ch-A", [_nm("C")],
    )
    assert diff.removed == ["Документ.A"]
    assert [o.name for o in diff.added] == ["C"]

    # ch-B нетронут
    cursor = await db_ready.execute(
        "SELECT object_path FROM metadata_cache WHERE channel_id = 'ch-B'",
    )
    rows = await cursor.fetchall()
    assert [r[0] for r in rows] == ["Документ.B"]


@pytest.mark.asyncio
async def test_incremental_preserves_fetched_at_for_unchanged(db_ready):
    """fetched_at unchanged-row'ов сохраняется при incremental refresh."""
    await write_cache_batch(
        db_ready, "ch-1", [_nm("A")], replace_existing=True,
    )

    cursor = await db_ready.execute(
        "SELECT fetched_at FROM metadata_cache WHERE object_path = ?",
        ("Документ.A",),
    )
    fetched_before = (await cursor.fetchone())[0]

    # Подождать чуть — fetched_at имеет CURRENT_TIMESTAMP precision до сек
    await asyncio.sleep(1.1)

    # Incremental с тем же объектом — unchanged
    diff = await write_cache_batch_incremental(
        db_ready, "ch-1", [_nm("A")],
    )
    assert diff.unchanged == ["Документ.A"]
    assert diff.added == []
    assert diff.updated == []

    cursor = await db_ready.execute(
        "SELECT fetched_at FROM metadata_cache WHERE object_path = ?",
        ("Документ.A",),
    )
    fetched_after = (await cursor.fetchone())[0]
    # Время не изменилось — мы не делали UPSERT
    assert fetched_after == fetched_before


# ---------- CacheDiff helpers ----------


def test_diff_total_changes_counts_correctly():
    diff = CacheDiff(
        added=[_nm("A"), _nm("B")],
        updated=[_nm("C")],
        removed=["Документ.D"],
        unchanged=["Документ.E", "Документ.F"],
    )
    # 2 + 1 + 1 = 4
    assert diff.total_changes == 4


# ---------- bulk_refresh_metadata_cache integration ----------


def _make_mcp_result(*names: str) -> list[dict]:
    """Минимальный MCP get_metadata response."""
    return [
        {"name": n, "type": "Документ", "presentation": f"Презент {n}"}
        for n in names
    ]


def _patch_mcp(monkeypatch, *, tools: list[dict], result: object):
    class _Fake:
        async def initialize(self):
            pass

        async def list_tools(self):
            return tools

        async def call_tool(self, name, arguments):
            return result

    @asynccontextmanager
    async def fake_client(endpoint, headers=None):
        yield _Fake()

    monkeypatch.setattr("app.knowledge.indexer.MCPClient", fake_client)


@pytest.mark.asyncio
async def test_bulk_refresh_incremental_skips_unchanged(db_ready, monkeypatch):
    """Второй вызов с теми же данными должен показать objects_skipped > 0."""
    _patch_mcp(
        monkeypatch,
        tools=[{"name": "get_metadata"}],
        result=_make_mcp_result("A", "B", "C"),
    )

    # 1-й вызов — все новые
    p1 = await bulk_refresh_metadata_cache(db_ready, "ch-1", "http://fake")
    assert p1.is_success
    assert p1.objects_written == 3
    assert p1.objects_skipped == 0

    # 2-й вызов с теми же объектами — все unchanged
    p2 = await bulk_refresh_metadata_cache(db_ready, "ch-1", "http://fake")
    assert p2.is_success
    assert p2.objects_written == 0
    assert p2.objects_skipped == 3


@pytest.mark.asyncio
async def test_bulk_refresh_incremental_detects_changes(db_ready, monkeypatch):
    """Изменение в MCP-результате между вызовами → updated."""
    _patch_mcp(
        monkeypatch,
        tools=[{"name": "get_metadata"}],
        result=_make_mcp_result("A", "B"),
    )
    await bulk_refresh_metadata_cache(db_ready, "ch-1", "http://fake")

    # Перезапатчиваем MCP с другим результатом
    _patch_mcp(
        monkeypatch,
        tools=[{"name": "get_metadata"}],
        result=[
            {"name": "A", "type": "Документ", "presentation": "ИзмененнаяA"},
            {"name": "C", "type": "Документ", "presentation": "Презент C"},
        ],
    )
    p = await bulk_refresh_metadata_cache(db_ready, "ch-1", "http://fake")
    assert p.is_success
    # objects_total = 2 (A, C). A updated + C added = 2 written. B removed (не считается в written).
    assert p.objects_total == 2
    assert p.objects_written == 2
    assert p.objects_skipped == 0


@pytest.mark.asyncio
async def test_bulk_refresh_legacy_mode_uses_full_replace(db_ready, monkeypatch):
    """incremental=False → старое поведение DELETE+INSERT, objects_written = total."""
    _patch_mcp(
        monkeypatch,
        tools=[{"name": "get_metadata"}],
        result=_make_mcp_result("A", "B"),
    )
    p1 = await bulk_refresh_metadata_cache(
        db_ready, "ch-1", "http://fake", incremental=False,
    )
    assert p1.objects_written == 2
    assert p1.objects_skipped == 0

    # 2-й вызов в legacy режиме — всё переписывается
    p2 = await bulk_refresh_metadata_cache(
        db_ready, "ch-1", "http://fake", incremental=False,
    )
    assert p2.objects_written == 2
    assert p2.objects_skipped == 0  # legacy не понимает unchanged
