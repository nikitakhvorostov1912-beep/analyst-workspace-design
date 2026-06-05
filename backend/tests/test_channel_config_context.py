"""Тесты моста detected-конфа → typical channel_id (Phase 5)."""
from __future__ import annotations

import aiosqlite
import pytest

from app.orchestrator.channel_config import resolve_channel_typical_context
from app.storage.migrations import apply_migrations


@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await apply_migrations(conn)
    try:
        yield conn
    finally:
        await conn.close()


async def _seed_ka_typical(db):
    await db.execute(
        "INSERT INTO typical_configurations "
        "(config_kind, config_version, channel_id, display_name, status) "
        "VALUES ('KA_2','2.5.25.92','_ka2_25_92','Комплексная автоматизация 2.5','graph_built')"
    )
    await db.commit()


@pytest.mark.asyncio
async def test_resolve_maps_ka_display_to_typical_channel(db):
    await _seed_ka_typical(db)
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, configuration, configuration_source) "
        "VALUES ('ch','C','http://x/mcp','embedded','КА 2.5','auto')"
    )
    await db.commit()
    ctx = await resolve_channel_typical_context(db, "ch")
    assert ctx.display_name == "КА 2.5"
    assert ctx.typical_channel_id == "_ka2_25_92"
    assert ctx.buddy_config_name == "Комплексная автоматизация"
    assert ctx.source == "auto"


@pytest.mark.asyncio
async def test_resolve_none_when_no_configuration(db):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind) "
        "VALUES ('ch2','C','http://x/mcp','embedded')"
    )
    await db.commit()
    ctx = await resolve_channel_typical_context(db, "ch2")
    assert ctx.display_name is None
    assert ctx.typical_channel_id is None


@pytest.mark.asyncio
async def test_resolve_typical_none_when_not_loaded(db):
    """Конфа детектнута, но типовая КА не загружена → typical_channel_id None."""
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, configuration, configuration_source) "
        "VALUES ('ch3','C','http://x/mcp','embedded','КА 2.5','auto')"
    )
    await db.commit()
    ctx = await resolve_channel_typical_context(db, "ch3")
    assert ctx.display_name == "КА 2.5"
    assert ctx.typical_channel_id is None  # типовая не загружена
    assert ctx.buddy_config_name == "Комплексная автоматизация"  # для buddy всё равно есть


@pytest.mark.asyncio
async def test_resolve_custom_returns_no_typical(db):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, configuration, configuration_source) "
        "VALUES ('ch4','C','http://x/mcp','embedded','Самописная','custom')"
    )
    await db.commit()
    ctx = await resolve_channel_typical_context(db, "ch4")
    assert ctx.typical_channel_id is None
    assert ctx.buddy_config_name is None


@pytest.mark.asyncio
async def test_resolve_bgu_has_buddy_name_but_no_typical(db):
    """БГУ 2.0 детектируется, buddy-имя есть, typical-снапшота нет → typical_channel_id None."""
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, configuration, configuration_source) "
        "VALUES ('ch5','C','http://x/mcp','embedded','БГУ 2.0','auto')"
    )
    await db.commit()
    ctx = await resolve_channel_typical_context(db, "ch5")
    assert ctx.display_name == "БГУ 2.0"
    assert ctx.buddy_config_name == "Бухгалтерия государственного учреждения"
    assert ctx.typical_channel_id is None
