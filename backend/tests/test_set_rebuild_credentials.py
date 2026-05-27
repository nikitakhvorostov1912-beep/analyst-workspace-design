"""Тесты для scripts/set_rebuild_credentials.py (M-K2.5.10.3)."""

from __future__ import annotations

import aiosqlite
import pytest

from app.storage.migrations import apply_migrations
from scripts.set_rebuild_credentials import (
    REBUILD_PROVIDER_ID,
    RebuildCredentials,
    load_rebuild_credentials,
    save_rebuild_credentials,
)


# ─── RebuildCredentials dataclass ─────────────────────────────────────


class TestRebuildCredentials:
    def test_masked_api_key_long(self):
        creds = RebuildCredentials(
            endpoint="https://x.com/v1",
            model="m",
            api_key="sk-s1lyss3hhkwivw0scbyr4183est1sxde2gfkjt28fnbbym49",
        )
        masked = creds.masked_api_key()
        # Маска: первые 5 + **** + последние 4
        assert masked.startswith("sk-s1")
        assert masked.endswith("ym49")
        assert "****" in masked
        # Не должно содержать середину
        assert "lyss3hh" not in masked

    def test_masked_api_key_short(self):
        creds = RebuildCredentials(endpoint="x", model="y", api_key="short")
        assert creds.masked_api_key() == "****"

    def test_masked_api_key_empty(self):
        creds = RebuildCredentials(endpoint="x", model="y", api_key="")
        assert creds.masked_api_key() == "****"

    def test_to_json_roundtrip(self):
        creds1 = RebuildCredentials(
            endpoint="https://api.deepseek.com/v1",
            model="deepseek-chat",
            api_key="sk-test-12345",
        )
        creds2 = RebuildCredentials.from_json(creds1.to_json())
        assert creds2.endpoint == creds1.endpoint
        assert creds2.model == creds1.model
        assert creds2.api_key == creds1.api_key


# ─── Storage integration ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_and_load_credentials():
    """Save → load roundtrip через AES-GCM."""
    db = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(db)

        original = RebuildCredentials(
            endpoint="https://api.deepseek.com/v1",
            model="deepseek-chat",
            api_key="sk-test-secret-12345",
        )
        await save_rebuild_credentials(db, original)

        loaded = await load_rebuild_credentials(db)
        assert loaded is not None
        assert loaded.endpoint == original.endpoint
        assert loaded.model == original.model
        assert loaded.api_key == original.api_key
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_load_returns_none_when_no_credentials():
    db = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(db)
        loaded = await load_rebuild_credentials(db)
        assert loaded is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_save_overwrites_existing():
    """Повторный save обновляет, не дублирует."""
    db = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(db)

        creds1 = RebuildCredentials(
            endpoint="https://a.com/v1", model="a", api_key="sk-a",
        )
        await save_rebuild_credentials(db, creds1)

        creds2 = RebuildCredentials(
            endpoint="https://b.com/v1", model="b", api_key="sk-b",
        )
        await save_rebuild_credentials(db, creds2)

        loaded = await load_rebuild_credentials(db)
        assert loaded.endpoint == "https://b.com/v1"
        assert loaded.model == "b"
        assert loaded.api_key == "sk-b"

        # Проверим что в БД только одна строка
        cursor = await db.execute(
            "SELECT COUNT(*) FROM user_secrets WHERE provider_id = ?",
            (REBUILD_PROVIDER_ID,),
        )
        (count,) = await cursor.fetchone()
        assert count == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_api_key_encrypted_at_rest():
    """Проверка что plain api_key не лежит в БД (хранится AES-GCM)."""
    db = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(db)
        await save_rebuild_credentials(db, RebuildCredentials(
            endpoint="https://x.com/v1",
            model="m",
            api_key="sk-very-secret-12345",
        ))
        # Прямой SELECT из таблицы — ключ должен быть зашифрован
        cursor = await db.execute(
            "SELECT api_key_encrypted FROM user_secrets WHERE provider_id = ?",
            (REBUILD_PROVIDER_ID,),
        )
        row = await cursor.fetchone()
        assert row is not None
        ciphertext = row[0]
        # Plain api_key не должен быть в зашифрованном значении
        assert b"sk-very-secret-12345" not in ciphertext
        assert b"very-secret" not in ciphertext
    finally:
        await db.close()
