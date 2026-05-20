"""Идемпотентный seed дефолтных записей в БД при первом запуске.

Цель: после установки Electron-инсталлера пользователь открывает приложение
и сразу может вводить вопросы в чат — без обхода Настроек руками.

Что сидим:
  • llm_settings (id=1) — endpoint/model/temperature из config.py.
    API-ключ НЕ хранится в backend (sessionStorage в браузере — security
    trade-off из v1.0, см. memory/llm-providers.md). Пользователь вводит
    его сам через /settings.
  • mcp_connections — одна запись «Транзит» / http://localhost:6010/mcp,
    kind=embedded. Если у аналитика свой MCP — отредактирует.

Идемпотентность: повторный вызов не плодит записи и не перезаписывает
существующие — INSERT OR IGNORE + проверка наличия.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import aiosqlite

from app.config import Settings

logger = logging.getLogger(__name__)


async def seed_defaults(db: aiosqlite.Connection, settings: Settings) -> None:
    """Сидит llm_settings + mcp_connections дефолтами если они ещё не заданы.

    Идемпотентно: при повторном вызове ничего не делает.
    """
    seeded_llm = await _seed_llm_settings(db, settings)
    seeded_mcp = await _seed_mcp_connection(db, settings)

    if seeded_llm or seeded_mcp:
        await db.commit()
        logger.info(
            "Seed defaults применён: llm_settings=%s, mcp_connections=%s",
            seeded_llm,
            seeded_mcp,
        )
    else:
        logger.debug("Seed defaults: записи уже есть, ничего не сидим")


async def _seed_llm_settings(db: aiosqlite.Connection, settings: Settings) -> bool:
    """Создаёт llm_settings(id=1) если его нет. Возвращает True если вставил."""
    async with db.execute("SELECT 1 FROM llm_settings WHERE id = 1") as cursor:
        existing = await cursor.fetchone()

    if existing is not None:
        return False

    await db.execute(
        "INSERT INTO llm_settings (id, endpoint, model, temperature, max_tokens) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            1,
            settings.default_llm_endpoint,
            settings.default_llm_model,
            settings.default_llm_temperature,
            4096,
        ),
    )
    return True


async def _seed_mcp_connection(db: aiosqlite.Connection, settings: Settings) -> bool:
    """Создаёт дефолтное MCP-подключение если ни одного ещё нет.

    Проверяем "пусто ли в таблице" а не дубликат по endpoint — если пользователь
    свой профиль уже добавил и удалил наш дефолтный, пересоздавать его не нужно.
    """
    async with db.execute("SELECT COUNT(*) FROM mcp_connections") as cursor:
        row = await cursor.fetchone()

    count = row[0] if row else 0
    if count > 0:
        return False

    conn_id = str(uuid4())
    channel = settings.default_mcp_channel or None
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, channel, anon_enabled, kind) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            conn_id,
            settings.default_mcp_name,
            settings.default_mcp_endpoint,
            channel,
            int(settings.default_mcp_anon_enabled),
            settings.default_mcp_kind,
        ),
    )
    return True
