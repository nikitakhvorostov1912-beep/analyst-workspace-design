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

CURRENT_VERSION = 11

# Миграция v4: расширение card_states — добавление колонки anon_tokens JSON
MIGRATIONS_V4 = [
    "ALTER TABLE card_states ADD COLUMN anon_tokens TEXT",
]

# Миграция v5: FTS5 виртуальная таблица + триггеры + metadata_cache
MIGRATIONS_V5 = [
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        content,
        session_id UNINDEXED,
        message_id UNINDEXED,
        tokenize = 'porter unicode61'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(rowid, content, session_id, message_id)
        VALUES (new.rowid, COALESCE(new.content, ''), new.session_id, new.id);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE OF content ON messages BEGIN
        UPDATE messages_fts SET content = COALESCE(new.content, '') WHERE rowid = old.rowid;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
        DELETE FROM messages_fts WHERE rowid = old.rowid;
    END
    """,
    """
    CREATE TABLE IF NOT EXISTS metadata_cache (
        channel_id TEXT NOT NULL,
        object_path TEXT NOT NULL,
        object_type TEXT NOT NULL,
        name TEXT NOT NULL,
        presentation TEXT,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (channel_id, object_path)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_metadata_cache_channel_name ON metadata_cache(channel_id, name)",
]

# Миграция v6: reasoning_content для thinking-mode LLM (Xiaomi MiMo, DeepSeek R1)
# Reasoning должен возвращаться в LLM в следующем round вместе с assistant message,
# иначе MiMo возвращает 400 "reasoning_content in thinking mode must be passed back".
MIGRATIONS_V6 = [
    "ALTER TABLE messages ADD COLUMN reasoning_content TEXT",
]

# Миграция v7: тип подключения (embedded — локальный встроенный MCP сервер EPF,
# proxy — через HF Spaces / Cloudflare Tunnel когда EPF на удалённом сервере).
# Аналитик должен видеть тип в UI и не путать localhost EPF с прокси.
# Backfill heuristic: endpoint содержит "?channel=" или "proxy" → proxy, иначе embedded.
MIGRATIONS_V7 = [
    "ALTER TABLE mcp_connections ADD COLUMN kind TEXT DEFAULT 'embedded'",
    """
    UPDATE mcp_connections
    SET kind = 'proxy'
    WHERE kind IS NULL
       OR endpoint LIKE '%?channel=%'
       OR endpoint LIKE '%proxy%'
    """,
    # Заполняем NULL для строк, которые backfill пропустил (endpoint без proxy-маркеров)
    "UPDATE mcp_connections SET kind = 'embedded' WHERE kind IS NULL",
]

# Миграция v8: backfill sessions с битым channel_id.
# Эра v1.2.10 (seed-bug) могла записать SQL placeholder '?1' вместо UUID —
# такие сессии при открытии падали в 404 «Канал не найден». Фронтенд v1.2.16
# уже обрабатывает fallback на лету, но в БД эти строки остаются «грязными»:
# дропдаун подключений вкладки показывает «Выберите подключение» вместо имени.
# Миграция чинит БД разово, при последующих запусках бездействует (идемпотентна).
#
# Логика: любой sessions.channel_id, которого нет в mcp_connections.id,
# заменяется на самое старое подключение. Если mcp_connections пуст —
# миграция ничего не трогает (некуда переключать).
MIGRATIONS_V8 = [
    """
    UPDATE sessions
    SET channel_id = (
        SELECT id FROM mcp_connections
        ORDER BY created_at ASC
        LIMIT 1
    )
    WHERE EXISTS (SELECT 1 FROM mcp_connections)
      AND (
        channel_id IS NULL
        OR channel_id = ''
        OR channel_id LIKE '?%'
        OR channel_id NOT IN (SELECT id FROM mcp_connections)
      )
    """,
]

# P2.1 (2026-05-23): backend-only API key storage.
# Раньше LLM API ключ хранился в browser localStorage и передавался в header
# X-LLM-API-Key для каждого /chat запроса. XSS через render Prism / Markdown
# мог вынести ключи всех пользователей. Теперь — на сервере, AES-256 GCM,
# в локальной SQLite + Electron user data dir.
#
# Шифрование: app_secret генерируется при первом запуске и сохраняется в
# system keyring через user_secrets_crypto.py. Без app_secret БД нельзя
# прочитать.
#
# Provider_id — короткий идентификатор каталога (cloud-ru-qwen3, nvidia-nim,
# xiaomi-mimo, deepseek). UNIQUE INDEX гарантирует один ключ на провайдера.
# Миграция v10 (2026-05-24): апгрейд legacy LLM config с устаревших endpoint'ов
# на новый дефолт NVIDIA NIM + DeepSeek V4 Flash.
#
# Контекст: до v1.3.0 дефолтом был Xiaomi MiMo. Пользователи которые работали
# через MiMo при апгрейде увидят в шапке «MIMO V2.5 PRO» — но MiMo ключа в
# embedded.env НЕТ (только NVIDIA). Frontend будет требовать ввод ключа.
#
# Логика идемпотентная:
# - Если в llm_settings есть запись с устаревшим endpoint
#   (api.xiaomimimo.com / api.deepseek.com со старыми моделями chat/reasoner)
#   → обновляем на NVIDIA NIM + DeepSeek V4 Flash, temperature сохраняется.
# - Запись с любым другим endpoint (Cloud.ru, NVIDIA уже, OpenAI, etc.) —
#   НЕ трогаем.
# - Пустая таблица — НЕ создаём дефолт (это сделает get_llm_config fallback).
MIGRATIONS_V10 = [
    """
    UPDATE llm_settings
    SET endpoint = 'https://integrate.api.nvidia.com/v1',
        model = 'deepseek-ai/deepseek-v4-flash',
        updated_at = CURRENT_TIMESTAMP
    WHERE endpoint LIKE '%xiaomimimo.com%'
       OR model IN ('mimo-v2.5-mini', 'deepseek-chat', 'deepseek-reasoner')
    """,
]


# Миграция v11: M-K1 capability-aware MCP connections (M6 Phase 12 / ADR-004).
# Добавляет 6 полей в mcp_connections для дискриминации EPF vs CFE vs raw MCP
# Toolkit и хранения capability response от MCP initialize:
#
#   - mode             TEXT   — 'mcp_only' | 'epf' | 'cfe' (ChannelMode)
#   - configuration    TEXT   — "УТ 11.5" / "ERP 2.5" / ... (отображение)
#   - platform         TEXT   — "8.3.27.1989" (полная версия)
#   - ext_version      TEXT   — версия нашего расширения АналитикПлюс (1.0.0)
#   - capabilities     TEXT   — JSON array of capability strings из experimental.*
#   - fingerprint      TEXT   — 12-char slug от compute_fingerprint() (см. M-K1.5)
#
# Backfill: для существующих connections — mode='mcp_only' (по умолчанию,
# когда capability discovery ещё не запускался). Остальные NULL — заполнятся
# при первом /connections/{id}/ping после M-K1.7 (Capability Discovery Service).
#
# ADR-005 рекомендация: продолжать DDL миграции, без alembic.
MIGRATIONS_V11 = [
    "ALTER TABLE mcp_connections ADD COLUMN mode TEXT DEFAULT 'mcp_only'",
    "ALTER TABLE mcp_connections ADD COLUMN configuration TEXT",
    "ALTER TABLE mcp_connections ADD COLUMN platform TEXT",
    "ALTER TABLE mcp_connections ADD COLUMN ext_version TEXT",
    "ALTER TABLE mcp_connections ADD COLUMN capabilities TEXT",  # JSON array
    "ALTER TABLE mcp_connections ADD COLUMN fingerprint TEXT",
    # Backfill mode для существующих NULL → 'mcp_only' (защита от строк где
    # ALTER TABLE по какой-то причине пропустил DEFAULT)
    "UPDATE mcp_connections SET mode = 'mcp_only' WHERE mode IS NULL",
    # Индекс по fingerprint — будет использоваться для группировки connections
    # одной типовой (один knowledge corpus shared)
    "CREATE INDEX IF NOT EXISTS idx_mcp_connections_fingerprint ON mcp_connections(fingerprint)",
]


MIGRATIONS_V9 = [
    """
    CREATE TABLE IF NOT EXISTS user_secrets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id TEXT NOT NULL,
        api_key_encrypted BLOB NOT NULL,
        nonce BLOB NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_secrets_provider ON user_secrets(provider_id)",
]


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

    if current < 4:
        # Добавляем колонку anon_tokens в card_states (v4)
        for stmt in MIGRATIONS_V4:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (4,),
        )
        await db.commit()

    if current < 5:
        # FTS5 virtual table + 3 triggers + metadata_cache (v5)
        for stmt in MIGRATIONS_V5:
            await db.execute(stmt)
        # Backfill: перенос существующих сообщений в FTS5 (один раз)
        await db.execute(
            "INSERT INTO messages_fts(rowid, content, session_id, message_id) "
            "SELECT rowid, COALESCE(content, ''), session_id, id FROM messages"
        )
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (5,),
        )
        await db.commit()

    if current < 6:
        # Колонка reasoning_content для thinking-mode моделей (v6)
        for stmt in MIGRATIONS_V6:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (6,),
        )
        await db.commit()

    if current < 7:
        # Колонка kind в mcp_connections + backfill (v7)
        for stmt in MIGRATIONS_V7:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (7,),
        )
        await db.commit()

    if current < 8:
        # Backfill sessions с битым channel_id ('?1' / NULL / удалённое подключение) (v8)
        for stmt in MIGRATIONS_V8:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (8,),
        )
        await db.commit()

    if current < 9:
        # user_secrets для backend-only API key storage (v9, P2.1)
        for stmt in MIGRATIONS_V9:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (9,),
        )
        await db.commit()

    if current < 10:
        # Апгрейд legacy MiMo / DeepSeek-chat → NVIDIA + DeepSeek V4 Flash (v10)
        for stmt in MIGRATIONS_V10:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (10,),
        )
        await db.commit()

    if current < 11:
        # Capability-aware MCP connections (v11, M-K1.6 / M6 Phase 12 / ADR-004)
        # Добавляет mode/configuration/platform/ext_version/capabilities/fingerprint
        # в mcp_connections + backfill mode='mcp_only' + индекс по fingerprint
        for stmt in MIGRATIONS_V11:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (11,),
        )
        await db.commit()
