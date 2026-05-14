import aiosqlite
import pytest


@pytest.mark.asyncio
async def test_migrations_create_all_tables(db: aiosqlite.Connection):
    """apply_migrations создаёт все 5 таблиц (4 + schema_version)."""
    rows = await db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = {row[0] for row in rows}
    expected = {"sessions", "messages", "mcp_connections", "llm_settings", "schema_version"}
    assert expected == table_names, f"Таблицы: {table_names}"


@pytest.mark.asyncio
async def test_migrations_are_idempotent(db: aiosqlite.Connection):
    """Повторный вызов apply_migrations не вызывает исключений."""
    from app.storage.migrations import apply_migrations

    # Второй вызов поверх уже существующей схемы
    await apply_migrations(db)

    # Таблицы всё ещё на месте
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
    )
    count = rows[0][0]
    assert count == 5


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
