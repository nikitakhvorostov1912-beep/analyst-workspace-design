"""Тесты миграции v5: FTS5 virtual table + 3 triggers + metadata_cache."""

import aiosqlite
import pytest
import pytest_asyncio

from app.storage.migrations import apply_migrations


@pytest_asyncio.fixture
async def fresh_db():
    """Чистое in-memory соединение без применённых миграций."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def migrated_db():
    """In-memory база с применёнными миграциями до v5."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)
    yield conn
    await conn.close()


async def _get_schema_names(conn: aiosqlite.Connection, type_filter: str | None = None) -> set[str]:
    if type_filter:
        rows = await conn.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type = ?",
            (type_filter,),
        )
    else:
        rows = await conn.execute_fetchall("SELECT name FROM sqlite_master")
    return {row[0] for row in rows}


@pytest.mark.asyncio
async def test_migration_v5_creates_fts5_virtual_table(fresh_db):
    """FTS5 virtual table messages_fts должна быть создана."""
    await apply_migrations(fresh_db)
    rows = await fresh_db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE name = 'messages_fts'"
    )
    assert len(rows) == 1, "messages_fts не найдена в sqlite_master"


@pytest.mark.asyncio
async def test_migration_v5_creates_3_triggers(fresh_db):
    """Три триггера messages_ai, messages_au, messages_ad должны быть созданы."""
    await apply_migrations(fresh_db)
    rows = await fresh_db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'messages_%'"
    )
    trigger_names = {row[0] for row in rows}
    assert "messages_ai" in trigger_names
    assert "messages_au" in trigger_names
    assert "messages_ad" in trigger_names


@pytest.mark.asyncio
async def test_migration_v5_creates_metadata_cache_table(fresh_db):
    """Таблица metadata_cache должна быть создана."""
    await apply_migrations(fresh_db)
    rows = await fresh_db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'metadata_cache'"
    )
    assert len(rows) == 1, "metadata_cache не найдена"


@pytest.mark.asyncio
async def test_migration_v5_creates_index_metadata_cache(fresh_db):
    """Индекс idx_metadata_cache_channel_name должен быть создан."""
    await apply_migrations(fresh_db)
    rows = await fresh_db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_metadata_cache_channel_name'"
    )
    assert len(rows) == 1, "idx_metadata_cache_channel_name не найден"


@pytest.mark.asyncio
async def test_migration_v5_backfill_messages_into_fts(fresh_db):
    """Backfill: существующие messages должны попасть в FTS5 после миграции."""
    # Сначала создаём базовую схему v1-v4 вручную (упрощённо)
    await fresh_db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version INTEGER PRIMARY KEY, "
        "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    await fresh_db.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, title TEXT, channel_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await fresh_db.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL, content TEXT, tool_calls JSON, tool_call_id TEXT,
            cards JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, duration_ms INTEGER
        )
        """
    )
    await fresh_db.execute(
        "INSERT INTO sessions (id, channel_id) VALUES ('sess-1', 'ch-1')"
    )
    await fresh_db.execute(
        "INSERT INTO messages (id, session_id, role, content) VALUES ('msg-1', 'sess-1', 'user', 'тестовое сообщение')"
    )
    await fresh_db.commit()

    # Применяем миграции (они определят v1-4 как уже выполненные через версию)
    # Выставляем версию как будто v4 уже применена
    await fresh_db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (4)")
    await fresh_db.commit()

    # Применяем только v5 через apply_migrations
    await apply_migrations(fresh_db)

    # Проверяем что сообщение перешло в FTS
    rows = await fresh_db.execute_fetchall(
        "SELECT message_id FROM messages_fts WHERE messages_fts MATCH 'тестовое'"
    )
    assert len(rows) >= 1, "Backfill не сработал — сообщение не найдено в FTS"


@pytest.mark.asyncio
async def test_migration_v5_idempotent(fresh_db):
    """Применение миграций дважды не должно вызывать ошибку."""
    await apply_migrations(fresh_db)
    # Второй вызов не должен упасть
    await apply_migrations(fresh_db)


@pytest.mark.asyncio
async def test_insert_message_after_v5_propagates_to_fts(migrated_db):
    """Триггер messages_ai: INSERT сообщения → FTS5 обновляется автоматически."""
    # Создаём сессию
    await migrated_db.execute(
        "INSERT INTO sessions (id, channel_id) VALUES ('sess-ai', 'ch-test')"
    )
    await migrated_db.execute(
        "INSERT INTO messages (id, session_id, role, content) "
        "VALUES ('msg-ai', 'sess-ai', 'user', 'поиск по тексту')"
    )
    await migrated_db.commit()

    rows = await migrated_db.execute_fetchall(
        "SELECT message_id FROM messages_fts WHERE messages_fts MATCH 'поиск'"
    )
    assert any(row[0] == "msg-ai" for row in rows), "Триггер messages_ai не сработал"


@pytest.mark.asyncio
async def test_update_message_content_propagates_to_fts(migrated_db):
    """Триггер messages_au: UPDATE content → FTS5 обновляется."""
    await migrated_db.execute(
        "INSERT INTO sessions (id, channel_id) VALUES ('sess-au', 'ch-test')"
    )
    await migrated_db.execute(
        "INSERT INTO messages (id, session_id, role, content) "
        "VALUES ('msg-au', 'sess-au', 'user', 'старый текст')"
    )
    await migrated_db.commit()

    # Обновляем content
    await migrated_db.execute(
        "UPDATE messages SET content = 'новый обновлённый текст' WHERE id = 'msg-au'"
    )
    await migrated_db.commit()

    # Старый текст не должен находиться
    rows_old = await migrated_db.execute_fetchall(
        "SELECT message_id FROM messages_fts WHERE messages_fts MATCH 'старый'"
    )
    assert not any(row[0] == "msg-au" for row in rows_old), "Старый текст всё ещё в FTS"

    # Новый должен находиться
    rows_new = await migrated_db.execute_fetchall(
        "SELECT message_id FROM messages_fts WHERE messages_fts MATCH 'обновлённый'"
    )
    assert any(row[0] == "msg-au" for row in rows_new), "Триггер messages_au не обновил FTS"


@pytest.mark.asyncio
async def test_delete_message_propagates_to_fts(migrated_db):
    """Триггер messages_ad: DELETE сообщения → удаляется из FTS5."""
    await migrated_db.execute(
        "INSERT INTO sessions (id, channel_id) VALUES ('sess-ad', 'ch-test')"
    )
    await migrated_db.execute(
        "INSERT INTO messages (id, session_id, role, content) "
        "VALUES ('msg-ad', 'sess-ad', 'user', 'удаляемый контент')"
    )
    await migrated_db.commit()

    # Проверяем что добавилось
    rows_before = await migrated_db.execute_fetchall(
        "SELECT message_id FROM messages_fts WHERE messages_fts MATCH 'удаляемый'"
    )
    assert any(row[0] == "msg-ad" for row in rows_before)

    # Удаляем сообщение
    await migrated_db.execute("DELETE FROM messages WHERE id = 'msg-ad'")
    await migrated_db.commit()

    # Не должно быть в FTS
    rows_after = await migrated_db.execute_fetchall(
        "SELECT message_id FROM messages_fts WHERE messages_fts MATCH 'удаляемый'"
    )
    assert not any(row[0] == "msg-ad" for row in rows_after), "Триггер messages_ad не удалил из FTS"
