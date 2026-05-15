import aiosqlite
import pytest


@pytest.mark.asyncio
async def test_migrations_create_all_tables(db: aiosqlite.Connection):
    """apply_migrations создаёт ожидаемые user-таблицы (включая v3 card_states + v5 metadata_cache + FTS5)."""
    rows = await db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = {row[0] for row in rows}
    # v1+v2: sessions, messages, mcp_connections, llm_settings, schema_version
    # v3: card_states
    # v5: metadata_cache + FTS5 (messages_fts + shadow tables messages_fts_*)
    expected_core = {
        "sessions", "messages", "mcp_connections", "llm_settings",
        "schema_version", "card_states", "metadata_cache", "messages_fts",
    }
    assert expected_core.issubset(table_names), f"Не хватает таблиц. Получено: {table_names}"


@pytest.mark.asyncio
async def test_migrations_are_idempotent(db: aiosqlite.Connection):
    """Повторный вызов apply_migrations не вызывает исключений и не плодит таблиц."""
    from app.storage.migrations import apply_migrations

    rows_before = await db.execute_fetchall(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
    )
    count_before = rows_before[0][0]

    # Второй вызов поверх уже существующей схемы
    await apply_migrations(db)

    rows_after = await db.execute_fetchall(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
    )
    count_after = rows_after[0][0]
    assert count_before == count_after, "Повторный apply_migrations плодит таблицы"


@pytest.mark.asyncio
async def test_sessions_table_has_correct_columns(db: aiosqlite.Connection):
    """Таблица sessions содержит ожидаемые колонки."""
    rows = await db.execute_fetchall("PRAGMA table_info(sessions)")
    columns = {row[1] for row in rows}
    assert {"id", "title", "channel_id", "created_at", "updated_at"} == columns


@pytest.mark.asyncio
async def test_messages_table_has_correct_columns(db: aiosqlite.Connection):
    """Таблица messages содержит ожидаемые колонки."""
    rows = await db.execute_fetchall("PRAGMA table_info(messages)")
    columns = {row[1] for row in rows}
    expected = {
        "id", "session_id", "role", "content", "tool_calls",
        "tool_call_id", "cards", "created_at", "duration_ms",
    }
    assert expected == columns
