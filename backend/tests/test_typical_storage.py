"""Тесты для backend/app/knowledge/typical/storage.py + migration v17.

Покрытие:
- Migration v17: typical_configurations / typical_indexing_runs tables + индексы + FK CASCADE
- create_configuration: новый snapshot + автоматический channel_id + дубликат
- get_configuration_by_* (id / channel / kind_version)
- list_configurations + фильтры
- update_configuration_status + indexed_at + metadata merge
- delete_configuration + cascade на runs
- create_run / update_run_progress / list_runs
- Lifecycle: PENDING → IN_PROGRESS (auto-fill started_at) → COMPLETED (finished_at)
- Enums: ConfigurationStatus / IndexingPhase / IndexingRunStatus
"""

from __future__ import annotations

from datetime import datetime

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.typical.registry import TypicalConfigKind
from app.knowledge.typical.storage import (
    ConfigurationStatus,
    IndexingPhase,
    IndexingRunStatus,
    TypicalConfiguration,
    TypicalIndexingRun,
    create_configuration,
    create_run,
    delete_configuration,
    get_configuration_by_channel,
    get_configuration_by_id,
    get_configuration_by_kind_version,
    get_run_by_id,
    list_configurations,
    list_runs,
    update_configuration_status,
    update_run_progress,
)
from app.storage.migrations import apply_migrations


@pytest_asyncio.fixture
async def db_ready():
    conn = await aiosqlite.connect(":memory:")
    try:
        await conn.execute("PRAGMA foreign_keys = ON")
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


# ---------- Migration v17 ----------


@pytest.mark.asyncio
async def test_migration_v17_creates_typical_tables():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('typical_configurations', 'typical_indexing_runs')"
        )
        rows = await cursor.fetchall()
        names = {r[0] for r in rows}
        assert names == {"typical_configurations", "typical_indexing_runs"}
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v17_indexes_created():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_typical_%'"
        )
        rows = await cursor.fetchall()
        names = {r[0] for r in rows}
        expected = {
            "idx_typical_configs_kind",
            "idx_typical_configs_channel",
            "idx_typical_configs_status",
            "idx_typical_runs_config",
            "idx_typical_runs_phase",
            "idx_typical_runs_status",
        }
        assert expected <= names, f"Missing: {expected - names}"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v17_idempotent():
    """Повторный apply_migrations не падает и не создаёт дублей."""
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await apply_migrations(conn)  # повторно
        cursor = await conn.execute(
            "SELECT version FROM schema_version ORDER BY version"
        )
        versions = [r[0] for r in await cursor.fetchall()]
        # Версия 17 — последняя
        assert max(versions) == 17
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v17_unique_kind_version(db_ready):
    """UNIQUE (config_kind, config_version) защищает от дубликатов snapshot'ов."""
    await create_configuration(db_ready, TypicalConfigKind.UT_115, "11.5.18.193")
    with pytest.raises(aiosqlite.IntegrityError):
        await create_configuration(db_ready, TypicalConfigKind.UT_115, "11.5.18.193")


@pytest.mark.asyncio
async def test_migration_v17_unique_channel_id(db_ready):
    """UNIQUE channel_id защищает от пересечения namespace'ов."""
    # Две разные пары kind+version, но если бы кто-то вручную inserted
    # одинаковый channel_id — UNIQUE должен ловить.
    await db_ready.execute(
        """
        INSERT INTO typical_configurations
            (config_kind, config_version, channel_id, display_name, status)
        VALUES ('UT_115', '11.5.18.193', '_test_channel_x', 'УТ 11.5.18.193', 'pending')
        """
    )
    await db_ready.commit()
    with pytest.raises(aiosqlite.IntegrityError):
        await db_ready.execute(
            """
            INSERT INTO typical_configurations
                (config_kind, config_version, channel_id, display_name, status)
            VALUES ('ERP_25', '2.5.18.245', '_test_channel_x', 'ERP 2.5.18.245', 'pending')
            """
        )
        await db_ready.commit()


# ---------- create_configuration ----------


@pytest.mark.asyncio
async def test_create_configuration_minimal(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    assert isinstance(config, TypicalConfiguration)
    assert config.id > 0
    assert config.config_kind == "UT_115"
    assert config.config_version == "11.5.18.193"
    assert config.channel_id == "_ut115_18_193"
    assert config.display_name == "Управление торговлей 11.5 (11.5.18.193)"
    assert config.source_path is None
    assert config.status == ConfigurationStatus.PENDING.value
    assert config.indexed_at is None
    assert config.metadata == {}
    assert isinstance(config.created_at, datetime)


@pytest.mark.asyncio
async def test_create_configuration_with_full_args(db_ready):
    config = await create_configuration(
        db_ready,
        TypicalConfigKind.ERP_25,
        "2.5.18.245",
        source_path="/snapshots/erp_25.dt",
        display_name="ERP кастомное имя",
        metadata={"build": 245, "release_date": "2026-03-15"},
    )
    assert config.source_path == "/snapshots/erp_25.dt"
    assert config.display_name == "ERP кастомное имя"
    assert config.metadata == {"build": 245, "release_date": "2026-03-15"}


@pytest.mark.asyncio
async def test_create_configuration_metadata_cyrillic(db_ready):
    """ensure_ascii=False сохраняет русский в JSON metadata."""
    config = await create_configuration(
        db_ready,
        TypicalConfigKind.BP_30,
        "3.0.158.18",
        metadata={"описание": "Релизная версия"},
    )
    refetched = await get_configuration_by_channel(db_ready, config.channel_id)
    assert refetched is not None
    assert refetched.metadata == {"описание": "Релизная версия"}


# ---------- get / list ----------


@pytest.mark.asyncio
async def test_get_configuration_by_channel_found(db_ready):
    created = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    fetched = await get_configuration_by_channel(db_ready, "_ut115_18_193")
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.channel_id == "_ut115_18_193"


@pytest.mark.asyncio
async def test_get_configuration_by_channel_not_found(db_ready):
    fetched = await get_configuration_by_channel(db_ready, "_ut115_99_999")
    assert fetched is None


@pytest.mark.asyncio
async def test_get_configuration_by_kind_version(db_ready):
    await create_configuration(db_ready, TypicalConfigKind.UT_115, "11.5.18.193")
    fetched = await get_configuration_by_kind_version(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    assert fetched is not None
    assert fetched.channel_id == "_ut115_18_193"


@pytest.mark.asyncio
async def test_get_configuration_by_id_not_found(db_ready):
    fetched = await get_configuration_by_id(db_ready, 99999)
    assert fetched is None


@pytest.mark.asyncio
async def test_list_configurations_empty(db_ready):
    assert await list_configurations(db_ready) == []


@pytest.mark.asyncio
async def test_list_configurations_all(db_ready):
    await create_configuration(db_ready, TypicalConfigKind.UT_115, "11.5.18.193")
    await create_configuration(db_ready, TypicalConfigKind.BP_30, "3.0.158.18")
    await create_configuration(db_ready, TypicalConfigKind.ERP_25, "2.5.18.245")
    configs = await list_configurations(db_ready)
    assert len(configs) == 3
    # Order by config_kind, version
    kinds = [c.config_kind for c in configs]
    assert kinds == sorted(kinds)


@pytest.mark.asyncio
async def test_list_configurations_filter_by_kind(db_ready):
    await create_configuration(db_ready, TypicalConfigKind.UT_115, "11.5.18.193")
    await create_configuration(db_ready, TypicalConfigKind.UT_115, "11.5.20.5")
    await create_configuration(db_ready, TypicalConfigKind.BP_30, "3.0.158.18")
    ut_only = await list_configurations(db_ready, kind=TypicalConfigKind.UT_115)
    assert len(ut_only) == 2
    assert all(c.config_kind == "UT_115" for c in ut_only)


@pytest.mark.asyncio
async def test_list_configurations_filter_by_status(db_ready):
    c1 = await create_configuration(db_ready, TypicalConfigKind.UT_115, "11.5.18.193")
    await create_configuration(db_ready, TypicalConfigKind.BP_30, "3.0.158.18")
    await update_configuration_status(
        db_ready, c1.channel_id, ConfigurationStatus.READY
    )
    ready = await list_configurations(db_ready, status=ConfigurationStatus.READY)
    assert len(ready) == 1
    assert ready[0].channel_id == "_ut115_18_193"


# ---------- update_configuration_status ----------


@pytest.mark.asyncio
async def test_update_configuration_status_simple(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    ok = await update_configuration_status(
        db_ready, config.channel_id, ConfigurationStatus.EXTRACTED
    )
    assert ok is True
    refetched = await get_configuration_by_channel(db_ready, config.channel_id)
    assert refetched is not None
    assert refetched.status == "extracted"


@pytest.mark.asyncio
async def test_update_configuration_status_with_indexed_at(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    now = datetime(2026, 6, 1, 10, 0, 0)
    await update_configuration_status(
        db_ready,
        config.channel_id,
        ConfigurationStatus.READY,
        indexed_at=now,
    )
    refetched = await get_configuration_by_channel(db_ready, config.channel_id)
    assert refetched is not None
    assert refetched.indexed_at == now


@pytest.mark.asyncio
async def test_update_configuration_status_metadata_merge(db_ready):
    config = await create_configuration(
        db_ready,
        TypicalConfigKind.UT_115,
        "11.5.18.193",
        metadata={"build": 193, "platform": "8.3.27"},
    )
    await update_configuration_status(
        db_ready,
        config.channel_id,
        ConfigurationStatus.PARSED,
        metadata_patch={"modules_count": 5234, "build": 199},  # overwrite + add
    )
    refetched = await get_configuration_by_channel(db_ready, config.channel_id)
    assert refetched is not None
    # platform сохранён, build обновлён, modules_count добавлен
    assert refetched.metadata == {
        "build": 199,
        "platform": "8.3.27",
        "modules_count": 5234,
    }


@pytest.mark.asyncio
async def test_update_configuration_status_not_found(db_ready):
    ok = await update_configuration_status(
        db_ready, "_ghost_99_99", ConfigurationStatus.READY
    )
    assert ok is False


# ---------- delete_configuration ----------


@pytest.mark.asyncio
async def test_delete_configuration_success(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    ok = await delete_configuration(db_ready, config.channel_id)
    assert ok is True
    assert await get_configuration_by_channel(db_ready, config.channel_id) is None


@pytest.mark.asyncio
async def test_delete_configuration_not_found(db_ready):
    ok = await delete_configuration(db_ready, "_ghost_99_99")
    assert ok is False


@pytest.mark.asyncio
async def test_delete_configuration_cascades_runs(db_ready):
    """FK CASCADE: удаление конфигурации сносит её runs."""
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    run1 = await create_run(db_ready, config.id, IndexingPhase.EXTRACT)
    run2 = await create_run(db_ready, config.id, IndexingPhase.PARSE_BSL)

    await delete_configuration(db_ready, config.channel_id)

    assert await get_run_by_id(db_ready, run1.id) is None
    assert await get_run_by_id(db_ready, run2.id) is None


# ---------- create_run + update_run_progress ----------


@pytest.mark.asyncio
async def test_create_run_pending_state(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    run = await create_run(db_ready, config.id, IndexingPhase.EXTRACT, items_total=1500)
    assert isinstance(run, TypicalIndexingRun)
    assert run.config_id == config.id
    assert run.phase == "extract"
    assert run.status == IndexingRunStatus.PENDING.value
    assert run.progress_pct == 0
    assert run.items_processed == 0
    assert run.items_total == 1500
    assert run.error is None
    assert run.started_at is None
    assert run.finished_at is None


@pytest.mark.asyncio
async def test_update_run_progress_to_in_progress_auto_fills_started_at(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    run = await create_run(db_ready, config.id, IndexingPhase.EXTRACT)
    assert run.started_at is None

    await update_run_progress(
        db_ready, run.id, status=IndexingRunStatus.IN_PROGRESS, progress_pct=10
    )
    refetched = await get_run_by_id(db_ready, run.id)
    assert refetched is not None
    assert refetched.status == "in_progress"
    assert refetched.started_at is not None
    assert refetched.progress_pct == 10


@pytest.mark.asyncio
async def test_update_run_progress_finished(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    run = await create_run(db_ready, config.id, IndexingPhase.EXTRACT)
    await update_run_progress(
        db_ready,
        run.id,
        status=IndexingRunStatus.COMPLETED,
        progress_pct=100,
        items_processed=1500,
        finished=True,
    )
    refetched = await get_run_by_id(db_ready, run.id)
    assert refetched is not None
    assert refetched.status == "completed"
    assert refetched.progress_pct == 100
    assert refetched.items_processed == 1500
    assert refetched.finished_at is not None


@pytest.mark.asyncio
async def test_update_run_progress_failed_with_error(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    run = await create_run(db_ready, config.id, IndexingPhase.PARSE_BSL)
    await update_run_progress(
        db_ready,
        run.id,
        status=IndexingRunStatus.FAILED,
        error="DESIGNER /DumpConfigToFiles упал на модуле ОбщегоНазначения (LineNumber=5234)",
        finished=True,
    )
    refetched = await get_run_by_id(db_ready, run.id)
    assert refetched is not None
    assert refetched.status == "failed"
    assert "DESIGNER" in refetched.error
    assert refetched.finished_at is not None


@pytest.mark.asyncio
async def test_update_run_progress_clamps_pct(db_ready):
    """progress_pct ограничивается диапазоном [0..100]."""
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    run = await create_run(db_ready, config.id, IndexingPhase.EXTRACT)
    await update_run_progress(db_ready, run.id, progress_pct=150)
    refetched = await get_run_by_id(db_ready, run.id)
    assert refetched is not None
    assert refetched.progress_pct == 100

    await update_run_progress(db_ready, run.id, progress_pct=-5)
    refetched = await get_run_by_id(db_ready, run.id)
    assert refetched is not None
    assert refetched.progress_pct == 0


@pytest.mark.asyncio
async def test_update_run_progress_metadata_merge(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    run = await create_run(
        db_ready, config.id, IndexingPhase.PARSE_BSL, metadata={"parser": "tree-sitter"}
    )
    await update_run_progress(
        db_ready, run.id, metadata_patch={"errors_count": 3, "parser": "bsl-ls"}
    )
    refetched = await get_run_by_id(db_ready, run.id)
    assert refetched is not None
    assert refetched.metadata == {"parser": "bsl-ls", "errors_count": 3}


@pytest.mark.asyncio
async def test_update_run_progress_not_found(db_ready):
    ok = await update_run_progress(db_ready, 99999, progress_pct=50)
    assert ok is False


@pytest.mark.asyncio
async def test_update_run_progress_noop_returns_true(db_ready):
    """Если не передано ни одного поля — apply noop и True."""
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    run = await create_run(db_ready, config.id, IndexingPhase.EXTRACT)
    ok = await update_run_progress(db_ready, run.id)
    assert ok is True


@pytest.mark.asyncio
async def test_update_run_progress_items_total_recalculable(db_ready):
    """items_total можно обновлять после create_run.

    Use case: при создании run мы не знаем сколько объектов будет — fetch
    идёт асинхронно. После discovery вызываем update_run_progress(items_total=N).
    """
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    run = await create_run(db_ready, config.id, IndexingPhase.PARSE_BSL)
    assert run.items_total == 0

    await update_run_progress(db_ready, run.id, items_total=24040)
    refetched = await get_run_by_id(db_ready, run.id)
    assert refetched is not None
    assert refetched.items_total == 24040

    # И повторное обновление работает
    await update_run_progress(db_ready, run.id, items_total=24050)
    refetched = await get_run_by_id(db_ready, run.id)
    assert refetched is not None
    assert refetched.items_total == 24050


# ---------- list_runs ----------


@pytest.mark.asyncio
async def test_list_runs_empty(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    assert await list_runs(db_ready, config.id) == []


@pytest.mark.asyncio
async def test_list_runs_filter_by_phase(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    await create_run(db_ready, config.id, IndexingPhase.EXTRACT)
    await create_run(db_ready, config.id, IndexingPhase.PARSE_BSL)
    await create_run(db_ready, config.id, IndexingPhase.PARSE_BSL)
    bsl_runs = await list_runs(db_ready, config.id, phase=IndexingPhase.PARSE_BSL)
    assert len(bsl_runs) == 2
    assert all(r.phase == "parse_bsl" for r in bsl_runs)


@pytest.mark.asyncio
async def test_list_runs_filter_by_status(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    r1 = await create_run(db_ready, config.id, IndexingPhase.EXTRACT)
    r2 = await create_run(db_ready, config.id, IndexingPhase.PARSE_BSL)
    await update_run_progress(
        db_ready, r1.id, status=IndexingRunStatus.COMPLETED, finished=True
    )
    completed = await list_runs(
        db_ready, config.id, status=IndexingRunStatus.COMPLETED
    )
    assert len(completed) == 1
    assert completed[0].id == r1.id


@pytest.mark.asyncio
async def test_list_runs_only_for_specified_config(db_ready):
    """list_runs не возвращает runs другой конфигурации."""
    c1 = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    c2 = await create_configuration(
        db_ready, TypicalConfigKind.BP_30, "3.0.158.18"
    )
    await create_run(db_ready, c1.id, IndexingPhase.EXTRACT)
    await create_run(db_ready, c2.id, IndexingPhase.EXTRACT)
    c1_runs = await list_runs(db_ready, c1.id)
    assert len(c1_runs) == 1
    assert c1_runs[0].config_id == c1.id


# ---------- to_dict roundtrip ----------


@pytest.mark.asyncio
async def test_configuration_to_dict_shape(db_ready):
    config = await create_configuration(
        db_ready,
        TypicalConfigKind.UT_115,
        "11.5.18.193",
        source_path="/snapshots/ut.dt",
        metadata={"k": "v"},
    )
    d = config.to_dict()
    assert d["id"] == config.id
    assert d["channel_id"] == "_ut115_18_193"
    assert d["source_path"] == "/snapshots/ut.dt"
    assert d["metadata"] == {"k": "v"}
    assert d["indexed_at"] is None
    assert isinstance(d["created_at"], str)


@pytest.mark.asyncio
async def test_run_to_dict_shape(db_ready):
    config = await create_configuration(
        db_ready, TypicalConfigKind.UT_115, "11.5.18.193"
    )
    run = await create_run(
        db_ready,
        config.id,
        IndexingPhase.EXTRACT,
        items_total=100,
        metadata={"src": "/x.dt"},
    )
    d = run.to_dict()
    assert d["id"] == run.id
    assert d["config_id"] == config.id
    assert d["phase"] == "extract"
    assert d["status"] == "pending"
    assert d["items_total"] == 100
    assert d["metadata"] == {"src": "/x.dt"}
