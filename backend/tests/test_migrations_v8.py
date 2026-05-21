"""Тесты миграции v8: backfill sessions с битым channel_id.

Контекст. v1.2.10 могла записать SQL placeholder '?1' в sessions.channel_id
вместо UUID (seed-bug). Юзер видел красный баннер «Канал не найден» при
открытии такой сессии. Фронт v1.2.16 ставит fallback на лету, v8 чистит БД
один раз и идемпотентно.

Правила миграции:
- если в mcp_connections нет ни одной строки → ничего не трогаем
- если channel_id NULL / пуст / начинается с '?' / не существует в mcp_connections
  → подставляем самый старый mcp_connections.id (ORDER BY created_at ASC)
- валидные channel_id не трогаются
"""

from __future__ import annotations

import aiosqlite
import pytest
import pytest_asyncio

from app.storage.migrations import (
    DDL_STATEMENTS,
    MIGRATIONS_V2,
    MIGRATIONS_V3,
    MIGRATIONS_V4,
    MIGRATIONS_V5,
    MIGRATIONS_V6,
    MIGRATIONS_V7,
    MIGRATIONS_V8,
    apply_migrations,
)


@pytest_asyncio.fixture
async def db_at_v7():
    """In-memory БД с применёнными миграциями до v7 — но не v8.

    Имитирует приложение на v1.2.16, в БД которого ещё может быть мусор
    от v1.2.10 (channel_id='?1').
    """
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row

    # Применяем всё кроме v8 вручную, чтобы протестировать v8 изолированно
    await conn.execute(DDL_STATEMENTS[0])  # schema_version
    for stmt in DDL_STATEMENTS[1:]:
        await conn.execute(stmt)
    for stmt in MIGRATIONS_V2 + MIGRATIONS_V3 + MIGRATIONS_V4 + MIGRATIONS_V5 + MIGRATIONS_V6 + MIGRATIONS_V7:
        await conn.execute(stmt)
    await conn.execute("INSERT INTO schema_version (version) VALUES (7)")
    await conn.commit()

    yield conn
    await conn.close()


async def _apply_v8(conn: aiosqlite.Connection) -> None:
    for stmt in MIGRATIONS_V8:
        await conn.execute(stmt)
    await conn.commit()


@pytest.mark.asyncio
async def test_v8_backfills_question_mark_channel_id(db_at_v7: aiosqlite.Connection):
    """Сессия с channel_id='?1' получает id первого подключения."""
    # arrange: добавляем валидное подключение и битую сессию
    await db_at_v7.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, created_at) "
        "VALUES ('conn-good', 'КА демка', 'http://localhost:6010/mcp', 'embedded', '2026-05-01')"
    )
    await db_at_v7.execute(
        "INSERT INTO sessions (id, title, channel_id, created_at, updated_at) "
        "VALUES ('s-broken', 'Старая сессия', '?1', '2026-04-01', '2026-04-01')"
    )
    await db_at_v7.commit()

    # act
    await _apply_v8(db_at_v7)

    # assert
    row = await db_at_v7.execute_fetchall(
        "SELECT channel_id FROM sessions WHERE id = ?", ("s-broken",)
    )
    assert row[0]["channel_id"] == "conn-good"


@pytest.mark.asyncio
async def test_v8_backfills_empty_channel_id(db_at_v7: aiosqlite.Connection):
    """Пустая строка в channel_id считается битой.

    NULL не тестируем — схема sessions объявлена NOT NULL, реально получить
    его в БД нельзя. Оставили в WHERE миграции как defensive — мало ли что
    придёт после очередной правки схемы.
    """
    await db_at_v7.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, created_at) "
        "VALUES ('conn-A', 'A', 'http://a/mcp', 'embedded', '2026-05-01')"
    )
    await db_at_v7.execute(
        "INSERT INTO sessions (id, title, channel_id, created_at, updated_at) "
        "VALUES ('s-empty', 'empty', '', '2026-04-01', '2026-04-01')"
    )
    await db_at_v7.commit()

    await _apply_v8(db_at_v7)

    row = await db_at_v7.execute_fetchall(
        "SELECT channel_id FROM sessions WHERE id = ?", ("s-empty",)
    )
    assert row[0]["channel_id"] == "conn-A"


@pytest.mark.asyncio
async def test_v8_backfills_orphaned_channel_id(db_at_v7: aiosqlite.Connection):
    """Если channel_id ссылается на удалённое подключение — переключаем на живое."""
    await db_at_v7.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, created_at) "
        "VALUES ('conn-live', 'Живое', 'http://live/mcp', 'embedded', '2026-05-01')"
    )
    # sessions ссылается на UUID, которого нет в mcp_connections
    await db_at_v7.execute(
        "INSERT INTO sessions (id, title, channel_id, created_at, updated_at) "
        "VALUES ('s-orphan', 'orphan', '11111111-2222-3333-4444-555555555555', "
        "'2026-04-01', '2026-04-01')"
    )
    await db_at_v7.commit()

    await _apply_v8(db_at_v7)

    row = await db_at_v7.execute_fetchall(
        "SELECT channel_id FROM sessions WHERE id = ?", ("s-orphan",)
    )
    assert row[0]["channel_id"] == "conn-live"


@pytest.mark.asyncio
async def test_v8_preserves_valid_channel_id(db_at_v7: aiosqlite.Connection):
    """Валидный channel_id остаётся как есть — миграция не трогает живые сессии."""
    await db_at_v7.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, created_at) "
        "VALUES ('conn-1', 'Первое', 'http://1/mcp', 'embedded', '2026-05-01')"
    )
    await db_at_v7.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, created_at) "
        "VALUES ('conn-2', 'Второе', 'http://2/mcp', 'embedded', '2026-05-02')"
    )
    await db_at_v7.execute(
        "INSERT INTO sessions (id, title, channel_id, created_at, updated_at) "
        "VALUES ('s-ok', 'ok', 'conn-2', '2026-04-01', '2026-04-01')"
    )
    await db_at_v7.commit()

    await _apply_v8(db_at_v7)

    row = await db_at_v7.execute_fetchall(
        "SELECT channel_id FROM sessions WHERE id = ?", ("s-ok",)
    )
    # conn-2 валиден — миграция должна оставить его, а не подменить на самый старый conn-1
    assert row[0]["channel_id"] == "conn-2"


@pytest.mark.asyncio
async def test_v8_noop_when_no_connections(db_at_v7: aiosqlite.Connection):
    """Если в mcp_connections пусто — миграция ничего не делает (некуда переключать)."""
    await db_at_v7.execute(
        "INSERT INTO sessions (id, title, channel_id, created_at, updated_at) "
        "VALUES ('s-broken', 'broken', '?1', '2026-04-01', '2026-04-01')"
    )
    await db_at_v7.commit()

    await _apply_v8(db_at_v7)

    row = await db_at_v7.execute_fetchall(
        "SELECT channel_id FROM sessions WHERE id = ?", ("s-broken",)
    )
    # Не на что переключать — оставляем '?1', фронт-fallback это разрулит на лету
    assert row[0]["channel_id"] == "?1"


@pytest.mark.asyncio
async def test_v8_idempotent_via_apply_migrations():
    """apply_migrations при повторном вызове не плодит изменений (CURRENT_VERSION≥8)."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row

    # Полная цепочка миграций (v1..v8 включительно)
    await apply_migrations(conn)

    # Готовим стабильный набор данных
    await conn.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, created_at) "
        "VALUES ('conn-1', 'A', 'http://a/mcp', 'embedded', '2026-05-01')"
    )
    await conn.execute(
        "INSERT INTO sessions (id, title, channel_id, created_at, updated_at) "
        "VALUES ('s-1', 't', 'conn-1', '2026-05-01', '2026-05-01')"
    )
    await conn.commit()

    # Повторный apply_migrations — не должен ничего менять (channel_id валиден)
    await apply_migrations(conn)

    row = await conn.execute_fetchall(
        "SELECT channel_id FROM sessions WHERE id = ?", ("s-1",)
    )
    assert row[0]["channel_id"] == "conn-1"

    await conn.close()
