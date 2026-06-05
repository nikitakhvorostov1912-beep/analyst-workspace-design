"""Тесты онбординг-детекции на коннекте (Phase 4)."""
from __future__ import annotations

import aiosqlite
import pytest

from app.knowledge.config_detection import KNOWN_CONFIGURATIONS, detect_configuration_type
from app.knowledge.onboarding import run_detection_for_channel, should_run_detection
from app.storage.migrations import apply_migrations


@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await apply_migrations(conn)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_should_run_detection_when_configuration_null(db):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind) "
        "VALUES ('c1','C','http://x/mcp','embedded')"
    )
    await db.commit()
    assert await should_run_detection(db, "c1") is True


@pytest.mark.asyncio
async def test_should_not_run_when_already_detected(db):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, configuration, configuration_source) "
        "VALUES ('c2','C','http://x/mcp','embedded','КА 2.5','auto')"
    )
    await db.commit()
    assert await should_run_detection(db, "c2") is False


@pytest.mark.asyncio
async def test_run_detection_writes_auto_for_confident(db, monkeypatch):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind) "
        "VALUES ('c3','C','http://x/mcp','embedded')"
    )
    await db.commit()
    ka = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ka_2_5")
    ut = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ut_11_5")
    present = set(ut.characteristic_objects) | set(ka.characteristic_objects) \
        | set(ka.discriminative_objects)

    async def fake_detect(endpoint, *, anon_headers=None):
        return detect_configuration_type(present)

    monkeypatch.setattr("app.knowledge.onboarding.detect_from_live", fake_detect)
    await run_detection_for_channel(db, "c3", "http://x/mcp")
    cur = await db.execute(
        "SELECT configuration, configuration_source FROM mcp_connections WHERE id='c3'"
    )
    row = await cur.fetchone()
    assert row[0] == "КА 2.5"
    assert row[1] == "auto"


@pytest.mark.asyncio
async def test_run_detection_writes_failed_on_mcp_error(db, monkeypatch):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind) "
        "VALUES ('c4','C','http://x/mcp','embedded')"
    )
    await db.commit()

    async def boom(endpoint, *, anon_headers=None):
        raise RuntimeError("MCP недоступен")

    monkeypatch.setattr("app.knowledge.onboarding.detect_from_live", boom)
    await run_detection_for_channel(db, "c4", "http://x/mcp")
    cur = await db.execute(
        "SELECT configuration_source FROM mcp_connections WHERE id='c4'"
    )
    assert (await cur.fetchone())[0] == "failed"
