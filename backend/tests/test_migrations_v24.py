"""Тесты миграции v24 (Multi-base онбординг, B.3): configuration_source в mcp_connections.

Покрытие:
- v24 добавляет колонку configuration_source (TEXT, NULL = ещё не детектировали)
- версия схемы == CURRENT_VERSION >= 24
- идемпотентный повторный вызов apply_migrations
"""

from __future__ import annotations

import aiosqlite
import pytest

from app.storage.migrations import apply_migrations, CURRENT_VERSION


@pytest.mark.asyncio
async def test_v24_adds_configuration_source_column():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cur = await conn.execute("PRAGMA table_info(mcp_connections)")
        cols = {row[1] for row in await cur.fetchall()}
        assert "configuration_source" in cols
        ver = await conn.execute_fetchall("SELECT MAX(version) FROM schema_version")
        assert ver[0][0] == CURRENT_VERSION
        assert CURRENT_VERSION >= 24
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migrations_idempotent_second_run():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await apply_migrations(conn)  # не должно бросить / дублировать
        ver = await conn.execute_fetchall("SELECT MAX(version) FROM schema_version")
        assert ver[0][0] == CURRENT_VERSION
    finally:
        await conn.close()
