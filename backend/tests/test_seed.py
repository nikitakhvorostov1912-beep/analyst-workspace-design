"""Тесты для app.storage.seed.seed_defaults().

Стратегия: используем фикстуру `db` (in-memory SQLite с применёнными migrations,
БЕЗ seed — потому что conftest проставил SEED_ON_STARTUP=false).
"""

from __future__ import annotations

import aiosqlite
import pytest

from app.config import Settings
from app.storage.seed import seed_defaults


def _make_settings(**overrides) -> Settings:
    """Создаёт Settings с тестовыми дефолтами (можно перебить через kwargs)."""
    defaults = {
        "default_llm_endpoint": "https://api.xiaomimimo.com/v1",
        "default_llm_model": "mimo-v2.5-pro",
        "default_llm_temperature": 0.3,
        "default_mcp_name": "Транзит",
        "default_mcp_endpoint": "http://localhost:6010/mcp",
        "default_mcp_kind": "embedded",
        "default_mcp_channel": "",
        "default_mcp_anon_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.asyncio
async def test_seed_creates_defaults_on_empty_db(db: aiosqlite.Connection):
    """На пустой БД seed создаёт ровно одну запись в llm_settings и одну в mcp_connections."""
    settings = _make_settings()

    await seed_defaults(db, settings)

    async with db.execute(
        "SELECT endpoint, model, temperature FROM llm_settings WHERE id = 1"
    ) as cursor:
        llm_row = await cursor.fetchone()

    assert llm_row is not None
    assert llm_row[0] == "https://api.xiaomimimo.com/v1"
    assert llm_row[1] == "mimo-v2.5-pro"
    assert llm_row[2] == pytest.approx(0.3)

    async with db.execute(
        "SELECT name, endpoint, kind, channel, anon_enabled FROM mcp_connections"
    ) as cursor:
        mcp_rows = await cursor.fetchall()

    assert len(mcp_rows) == 1
    name, endpoint, kind, channel, anon = mcp_rows[0]
    assert name == "Транзит"
    assert endpoint == "http://localhost:6010/mcp"
    assert kind == "embedded"
    assert channel is None  # default_mcp_channel="" → None в БД
    assert anon == 0


@pytest.mark.asyncio
async def test_seed_is_idempotent(db: aiosqlite.Connection):
    """Повторный вызов seed не плодит дубликатов и не перезаписывает данные."""
    settings = _make_settings()

    await seed_defaults(db, settings)
    await seed_defaults(db, settings)
    await seed_defaults(db, settings)

    async with db.execute("SELECT COUNT(*) FROM llm_settings") as cursor:
        llm_count = (await cursor.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM mcp_connections") as cursor:
        mcp_count = (await cursor.fetchone())[0]

    assert llm_count == 1
    assert mcp_count == 1


@pytest.mark.asyncio
async def test_seed_respects_existing_llm_settings(db: aiosqlite.Connection):
    """Если llm_settings уже есть — seed не перезаписывает (пользователь правил руками)."""
    await db.execute(
        "INSERT INTO llm_settings (id, endpoint, model, temperature, max_tokens) "
        "VALUES (?, ?, ?, ?, ?)",
        (1, "https://api.openai.com/v1", "gpt-4o", 0.7, 8192),
    )
    await db.commit()

    settings = _make_settings()
    await seed_defaults(db, settings)

    async with db.execute(
        "SELECT endpoint, model, temperature FROM llm_settings WHERE id = 1"
    ) as cursor:
        row = await cursor.fetchone()

    # Должен остаться custom-конфиг, а не наш MiMo дефолт
    assert row[0] == "https://api.openai.com/v1"
    assert row[1] == "gpt-4o"
    assert row[2] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_seed_respects_existing_mcp_connection(db: aiosqlite.Connection):
    """Если хоть одно MCP-подключение есть — наш дефолт не добавляется."""
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, channel, anon_enabled, kind) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("custom-id", "Тестовая", "http://localhost:7777/mcp", None, 0, "embedded"),
    )
    await db.commit()

    settings = _make_settings()
    await seed_defaults(db, settings)

    async with db.execute("SELECT name, endpoint FROM mcp_connections") as cursor:
        rows = await cursor.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "Тестовая"
    assert rows[0][1] == "http://localhost:7777/mcp"


@pytest.mark.asyncio
async def test_seed_respects_custom_env_overrides(db: aiosqlite.Connection):
    """Пользователь может переопределить дефолты через env (Electron инсталлер)."""
    settings = _make_settings(
        default_llm_endpoint="https://api.example.com/v1",
        default_llm_model="custom-model",
        default_mcp_name="Прод",
        default_mcp_endpoint="https://prod.example.com/mcp",
        default_mcp_kind="proxy",
        default_mcp_channel="prod-1",
        default_mcp_anon_enabled=True,
    )

    await seed_defaults(db, settings)

    async with db.execute(
        "SELECT endpoint, model FROM llm_settings WHERE id = 1"
    ) as cursor:
        llm = await cursor.fetchone()
    async with db.execute(
        "SELECT name, endpoint, kind, channel, anon_enabled FROM mcp_connections"
    ) as cursor:
        mcp = await cursor.fetchone()

    assert llm[0] == "https://api.example.com/v1"
    assert llm[1] == "custom-model"
    assert mcp[0] == "Прод"
    assert mcp[1] == "https://prod.example.com/mcp"
    assert mcp[2] == "proxy"
    assert mcp[3] == "prod-1"
    assert mcp[4] == 1
