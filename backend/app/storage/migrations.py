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

# Новые DDL для schema_version=2: индексы для быстрого поиска истории
MIGRATIONS_V2 = [
    "CREATE INDEX IF NOT EXISTS idx_messages_session_created ON messages(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC)",
]

# Миграция v3: таблица card_states для хранения состояния LogCard (load-more)
MIGRATIONS_V3 = [
    """
    CREATE TABLE IF NOT EXISTS card_states (
        card_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        message_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        original_args TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )
    """,
]

CURRENT_VERSION = 3


async def apply_migrations(db: aiosqlite.Connection) -> None:
    """Идемпотентно применяет миграции схемы БД."""
    # Создаём schema_version первым делом
    await db.execute(DDL_STATEMENTS[0])
    await db.commit()

    row = await db.execute_fetchall("SELECT MAX(version) FROM schema_version")
    current = row[0][0] if row and row[0][0] is not None else 0

    if current >= CURRENT_VERSION:
        return

    if current < 1:
        # Применяем базовые таблицы (v1)
        for stmt in DDL_STATEMENTS[1:]:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (1,),
        )
        await db.commit()

    if current < 2:
        # Применяем индексы v2
        for stmt in MIGRATIONS_V2:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (2,),
        )
        await db.commit()

    if current < 3:
        # Создаём таблицу card_states для load-more (v3)
        for stmt in MIGRATIONS_V3:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (3,),
        )
        await db.commit()
