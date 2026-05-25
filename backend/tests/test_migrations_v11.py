"""Tests for migration v11 — MCPConnection capability-aware fields (M-K1.6)."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from app.storage.migrations import CURRENT_VERSION, MIGRATIONS_V11, apply_migrations


@pytest.mark.asyncio
async def test_current_version_is_11() -> None:
    """ADR-005: продолжаем DDL миграции, v11 = M-K1.6."""
    assert CURRENT_VERSION == 11


@pytest.mark.asyncio
async def test_migration_v11_adds_6_columns(tmp_path: Path) -> None:
    """v11 добавляет mode/configuration/platform/ext_version/capabilities/fingerprint."""
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await apply_migrations(db)
        cursor = await db.execute("PRAGMA table_info(mcp_connections)")
        rows = await cursor.fetchall()
        col_names = {row[1] for row in rows}

    # 6 новых колонок из v11:
    assert "mode" in col_names
    assert "configuration" in col_names
    assert "platform" in col_names
    assert "ext_version" in col_names
    assert "capabilities" in col_names
    assert "fingerprint" in col_names


@pytest.mark.asyncio
async def test_migration_v11_mode_default_mcp_only(tmp_path: Path) -> None:
    """Default value для mode = 'mcp_only' (backfill для existing rows)."""
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await apply_migrations(db)
        # Создаём connection без указания mode
        await db.execute(
            "INSERT INTO mcp_connections (id, name, endpoint, kind) "
            "VALUES ('test-id', 'Test', 'http://127.0.0.1:6010/mcp', 'embedded')"
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT mode FROM mcp_connections WHERE id = 'test-id'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "mcp_only"


@pytest.mark.asyncio
async def test_migration_v11_fingerprint_index_created(tmp_path: Path) -> None:
    """Index idx_mcp_connections_fingerprint создаётся для группировки по типовой."""
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await apply_migrations(db)
        cursor = await db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_mcp_connections_fingerprint'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "idx_mcp_connections_fingerprint"


@pytest.mark.asyncio
async def test_migration_v11_idempotent(tmp_path: Path) -> None:
    """Повторный запуск apply_migrations не падает (schema_version проверка)."""
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await apply_migrations(db)
        await apply_migrations(db)  # no-op второй вызов

        cursor = await db.execute("SELECT MAX(version) FROM schema_version")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 11


@pytest.mark.asyncio
async def test_migration_v11_capability_storage_as_json(tmp_path: Path) -> None:
    """capabilities — JSON-сериализованный list, хранится в TEXT колонке."""
    import json

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await apply_migrations(db)
        caps = ["mcp.execute_query", "mcp.get_metadata", "cfe.activity_stream"]
        await db.execute(
            "INSERT INTO mcp_connections (id, name, endpoint, kind, mode, capabilities) "
            "VALUES ('cfe-test', 'CFE', 'http://localhost:6010/mcp', 'embedded', 'cfe', ?)",
            (json.dumps(caps),),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT capabilities FROM mcp_connections WHERE id = 'cfe-test'"
        )
        row = await cursor.fetchone()
        assert row is not None
        stored = json.loads(row[0])
        assert stored == caps


@pytest.mark.asyncio
async def test_migration_v11_fingerprint_storage(tmp_path: Path) -> None:
    """fingerprint — 12-char slug из compute_fingerprint()."""
    from app.knowledge.fingerprint import compute_fingerprint

    fp = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5",
        platform_version="8.3.27.1989",
    )

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await apply_migrations(db)
        await db.execute(
            "INSERT INTO mcp_connections "
            "(id, name, endpoint, kind, mode, configuration, platform, fingerprint) "
            "VALUES ('ut-test', 'УТ 11.5', 'http://localhost:6010/mcp', 'embedded', "
            "'mcp_only', 'УТ 11.5', '8.3.27.1989', ?)",
            (fp.slug,),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT fingerprint FROM mcp_connections WHERE id = 'ut-test'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == fp.slug
        assert len(row[0]) == 12


@pytest.mark.asyncio
async def test_migration_v11_backfill_existing_rows(tmp_path: Path) -> None:
    """Если row была создана ДО v11 (e.g. v10), mode должен заполниться 'mcp_only'.

    Симулируем: создаём БД с v10, добавляем row без mode, потом применяем v11.
    """
    db_path = tmp_path / "test.db"

    # Шаг 1: применяем миграции но обрываемся на v10 (искусственно перезапишем CURRENT_VERSION)
    from app.storage import migrations as m

    original_cv = m.CURRENT_VERSION
    try:
        m.CURRENT_VERSION = 10
        async with aiosqlite.connect(db_path) as db:
            await m.apply_migrations(db)
            # Создаём connection без mode (т.к. v11 ещё не применена)
            await db.execute(
                "INSERT INTO mcp_connections (id, name, endpoint, kind) "
                "VALUES ('legacy', 'Legacy', 'http://127.0.0.1:6010/mcp', 'embedded')"
            )
            await db.commit()
    finally:
        m.CURRENT_VERSION = original_cv

    # Шаг 2: применяем v11. Backfill должен обнулить mode → 'mcp_only'
    async with aiosqlite.connect(db_path) as db:
        await m.apply_migrations(db)
        cursor = await db.execute(
            "SELECT mode FROM mcp_connections WHERE id = 'legacy'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "mcp_only"


def test_migration_v11_sql_uses_text_columns() -> None:
    """Все 6 новых колонок — TEXT (никаких INTEGER / BLOB, чтобы не пугать аналитика)."""
    for stmt in MIGRATIONS_V11:
        if "ADD COLUMN" not in stmt:
            continue
        # Каждый ALTER TABLE должен содержать `TEXT` или быть UPDATE/CREATE INDEX
        assert " TEXT" in stmt or stmt.startswith("ALTER") is False, (
            f"Migration v11 ALTER statement must use TEXT column: {stmt}"
        )
