import aiosqlite

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        title TEXT,
        channel_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT,
        tool_calls JSON,
        tool_call_id TEXT,
        cards JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        duration_ms INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mcp_connections (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        channel TEXT,
        anon_enabled BOOLEAN DEFAULT 0,
        last_seen_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS llm_settings (
        id INTEGER PRIMARY KEY,
        endpoint TEXT NOT NULL,
        model TEXT NOT NULL,
        temperature REAL DEFAULT 0.3,
        max_tokens INTEGER DEFAULT 4096,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
]

CURRENT_VERSION = 1


async def apply_migrations(db: aiosqlite.Connection) -> None:
    """Идемпотентно применяет миграции схемы БД."""
    # Создаём schema_version первым делом
    await db.execute(DDL_STATEMENTS[0])
    await db.commit()

    row = await db.execute_fetchall("SELECT MAX(version) FROM schema_version")
    current = row[0][0] if row and row[0][0] is not None else 0

    if current >= CURRENT_VERSION:
        return

    # Применяем оставшиеся DDL
    for stmt in DDL_STATEMENTS[1:]:
        await db.execute(stmt)

    await db.execute(
        "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
        (CURRENT_VERSION,),
    )
    await db.commit()
