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

CURRENT_VERSION = 21

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


# Миграция v12 (M-K2.2): таблица index_runs для state machine indexer'а.
# Каждый запуск bulk_refresh_metadata_cache (M-K2.1) создаёт строку:
#   pending → running → done | failed
# Endpoint POST /knowledge/{ch}/index/start проверяет нет ли уже running
# (защита от double-start), GET /knowledge/{ch}/index/status возвращает
# последний (по started_at DESC) row + текущий running если есть.
#
# Индекс по (channel_id, started_at DESC) — основной hot path для status:
# «дай мне последний run этого канала».
#
# ADR-005: DDL без alembic, миграции необратимы. Если потребуется откат —
# delete from index_runs + DROP TABLE из новой миграции v13.
MIGRATIONS_V12 = [
    """
    CREATE TABLE IF NOT EXISTS index_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'done', 'failed')),
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP,
        duration_ms INTEGER,
        objects_total INTEGER DEFAULT 0,
        objects_written INTEGER DEFAULT 0,
        objects_skipped INTEGER DEFAULT 0,
        error TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_index_runs_channel ON index_runs(channel_id, started_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_index_runs_status ON index_runs(status)",
]


# Миграция v13 (M-K2.5): vector store backing table.
# vec0 virtual table из `sqlite-vec` создаётся динамически после
# `sqlite_vec.load(conn)` — миграция её не управляет. Здесь только
# обвязочная таблица для маппинга rowid → (channel_id, object_path)
# плюс embedding metadata (модель, размерность, дата).
#
# vec_objects.id используется как rowid для vec0 таблицы, чтобы JOIN был
# тривиальный: `vec_objects_embeddings.rowid = vec_objects.id`.
MIGRATIONS_V13 = [
    """
    CREATE TABLE IF NOT EXISTS vec_objects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT NOT NULL,
        object_path TEXT NOT NULL,
        embedding_model TEXT NOT NULL,
        embedding_dim INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(channel_id, object_path, embedding_model)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_vec_objects_channel ON vec_objects(channel_id)",
    "CREATE INDEX IF NOT EXISTS idx_vec_objects_path ON vec_objects(channel_id, object_path)",
]


# Миграция v14 (M-K2.7): обвязочная таблица для ИТС RAG.
# Хранит content + metadata каждого чанка стандарта/паттерна/диагностики.
# Vector в vec_objects (channel_id="_its", object_path="its:{doc_id}#{chunk_index}"),
# а текст и категория — здесь. JOIN по object_path даёт LLM-friendly результат
# с цитатой и ссылкой на исходный файл.
#
# Ключи:
#   - PRIMARY KEY (id) — autoincrement, для удобства внутри backend
#   - UNIQUE (object_path) — для JOIN с vec_objects по строке
#   - UNIQUE (doc_id, chunk_index) — natural-key защита от двойной вставки
#   - chunk_hash SHA-256 — позволяет idempotent re-index пропустить
#     неизменившиеся чанки (без повторного embedding'а — экономия $)
#
# Категории: 'std' | 'patterns' | 'diagnostics' | 'metod8dev' | 'lang'.
# Source — zeegin/v8std (CC-BY-4.0).
MIGRATIONS_V14 = [
    """
    CREATE TABLE IF NOT EXISTS its_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        object_path TEXT NOT NULL UNIQUE,
        doc_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        title TEXT NOT NULL,
        section_title TEXT,
        content TEXT NOT NULL,
        category TEXT NOT NULL,
        source_path TEXT NOT NULL,
        char_count INTEGER NOT NULL,
        chunk_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(doc_id, chunk_index)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_its_chunks_category ON its_chunks(category)",
    "CREATE INDEX IF NOT EXISTS idx_its_chunks_doc ON its_chunks(doc_id)",
]


# Миграция v15 (M-K2.8): обвязочная таблица для БСП RAG.
# Хранит content + metadata каждого Экспорт-метода БСП CommonModules.
# Vector в vec_objects (channel_id="_bsp", object_path="bsp:<ver>:<Mod>.<Method>"),
# а текст и сигнатура — здесь. JOIN по object_path даёт LLM-friendly результат.
#
# Ключи:
#   - PRIMARY KEY (id)
#   - UNIQUE (object_path) — для JOIN с vec_objects
#   - UNIQUE (module_name, method_name, version) — natural key защита от дублей
#   - chunk_hash SHA-256 для idempotent re-index
#
# Версии: '3.1' | '3.2' (источник: zeegin/ssl_3_1, ssl_3_2 — CC-BY-4.0).
MIGRATIONS_V15 = [
    """
    CREATE TABLE IF NOT EXISTS bsp_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        object_path TEXT NOT NULL UNIQUE,
        module_name TEXT NOT NULL,
        method_name TEXT NOT NULL,
        method_kind TEXT NOT NULL,
        signature TEXT NOT NULL,
        doc_comment TEXT NOT NULL,
        content TEXT NOT NULL,
        version TEXT NOT NULL,
        source_path TEXT NOT NULL,
        char_count INTEGER NOT NULL,
        chunk_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(module_name, method_name, version)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_bsp_chunks_module ON bsp_chunks(module_name)",
    "CREATE INDEX IF NOT EXISTS idx_bsp_chunks_method ON bsp_chunks(method_name)",
    "CREATE INDEX IF NOT EXISTS idx_bsp_chunks_version ON bsp_chunks(version)",
]


# Миграция v16 (M-K3.17.1a): Knowledge Graph storage (ADR-002).
#
# Хранит L2 Relational layer: nodes (модули, методы, типы метаданных) и
# edges (CALLS, CONTAINS, USES, WRITES_TO, READS_FROM). SQLite + recursive
# CTE для traversal — не Neo4j (per ADR-002 рассуждения: embed-friendly,
# нет дополнительной зависимости).
#
# Ключи:
#   - graph_nodes.id INTEGER PRIMARY KEY AUTOINCREMENT (для edges FK)
#   - UNIQUE (channel_id, qualified_name, node_kind) — natural key.
#     Один и тот же qualified_name может существовать в разных channel'ах
#     (например `ОбщегоНазначения.ЗначениеРеквизитаОбъекта` в УТ vs ERP).
#   - graph_edges.src_id / dst_id — FK на graph_nodes.id с CASCADE delete.
#   - UNIQUE (src_id, dst_id, edge_kind) — нет дублей edges одного типа.
#
# Индексы оптимизированы под основные query patterns:
#   - get_node by qualified_name (idx_graph_nodes_qname)
#   - get_neighbors src_id (idx_graph_edges_src)
#   - get_neighbors dst_id (idx_graph_edges_dst) — reverse traversal
#   - filter by node_kind (idx_graph_nodes_kind)
#   - per-channel queries (idx_graph_nodes_channel)
#
# `attributes` JSON column — расширяемый bag для node-specific properties
# (line number, signature, is_exported, etc.). Запросы по нему — через
# JSON1 extension (есть в Python 3.11+ SQLite).
MIGRATIONS_V16 = [
    """
    CREATE TABLE IF NOT EXISTS graph_nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT NOT NULL,
        node_kind TEXT NOT NULL,
        qualified_name TEXT NOT NULL,
        source_path TEXT,
        attributes TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(channel_id, qualified_name, node_kind)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_graph_nodes_channel ON graph_nodes(channel_id)",
    "CREATE INDEX IF NOT EXISTS idx_graph_nodes_qname ON graph_nodes(channel_id, qualified_name)",
    "CREATE INDEX IF NOT EXISTS idx_graph_nodes_kind ON graph_nodes(channel_id, node_kind)",
    """
    CREATE TABLE IF NOT EXISTS graph_edges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        src_id INTEGER NOT NULL,
        dst_id INTEGER NOT NULL,
        edge_kind TEXT NOT NULL,
        attributes TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (src_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
        FOREIGN KEY (dst_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
        UNIQUE(src_id, dst_id, edge_kind)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_graph_edges_src ON graph_edges(src_id)",
    "CREATE INDEX IF NOT EXISTS idx_graph_edges_dst ON graph_edges(dst_id)",
    "CREATE INDEX IF NOT EXISTS idx_graph_edges_kind ON graph_edges(edge_kind)",
]


# Миграция v17 (M-K2.5.0): Typical Configurations infrastructure (ADR-003).
#
# Реестр снапшотов типовых конфигураций (УТ/ERP/КА/БП/ЗУП/УСО/Документооборот)
# + журнал индексационных прогонов. Контент (modules, methods, queries,
# object cards) будут жить в отдельных таблицах в следующих phases (M-K2.5.1+).
#
# Ключи:
#   - typical_configurations.id INTEGER PRIMARY KEY AUTOINCREMENT
#   - UNIQUE (config_kind, config_version) — один snapshot на версию
#   - UNIQUE (channel_id) — namespace `_ut115_18_193` зарезервирован глобально
#     (не пересекается с реальными MCP-каналами UUID v4)
#   - typical_indexing_runs.config_id FK CASCADE — удаление конфигурации
#     уносит весь её журнал
#
# `status` lifecycle для typical_configurations:
#   pending → extracted → parsed → graph_built → enriched → ready
#                                                          → failed
#
# `phase` enum для typical_indexing_runs:
#   extract | parse_bsl | parse_queries | parse_metadata | graph | cards | embed
MIGRATIONS_V17 = [
    """
    CREATE TABLE IF NOT EXISTS typical_configurations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_kind TEXT NOT NULL,
        config_version TEXT NOT NULL,
        channel_id TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        source_path TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        indexed_at TIMESTAMP,
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(config_kind, config_version)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_typical_configs_kind ON typical_configurations(config_kind)",
    "CREATE INDEX IF NOT EXISTS idx_typical_configs_channel ON typical_configurations(channel_id)",
    "CREATE INDEX IF NOT EXISTS idx_typical_configs_status ON typical_configurations(status)",
    """
    CREATE TABLE IF NOT EXISTS typical_indexing_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_id INTEGER NOT NULL,
        phase TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        progress_pct INTEGER NOT NULL DEFAULT 0,
        items_processed INTEGER NOT NULL DEFAULT 0,
        items_total INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        started_at TIMESTAMP,
        finished_at TIMESTAMP,
        metadata TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY (config_id) REFERENCES typical_configurations(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_typical_runs_config ON typical_indexing_runs(config_id)",
    "CREATE INDEX IF NOT EXISTS idx_typical_runs_phase ON typical_indexing_runs(phase)",
    "CREATE INDEX IF NOT EXISTS idx_typical_runs_status ON typical_indexing_runs(status)",
]


# Миграция v18 — Object Cards (M-K2.5.5, ADR-003 секция 3 "Embedding").
#
# Карточки — это LLM-генерируемые описания на русском языке для каждого
# ключевого объекта типовой (Документ.X, Справочник.Y, Регистр.Z и т.д.).
# Хранятся отдельно от графа, ссылаются на объект через
# `channel_id + object_qualified_name`. Эмбедится **только** summary +
# purpose + posting_flow (не сам код) — это политика legal-clean
# embedding'а из ADR-003.
#
# `card_payload` — JSON со структурой:
#   {
#     "summary": "Документ продажи товаров...",
#     "purpose": "Регистрирует факт реализации в БУ...",
#     "key_attributes": [{"name": "Контрагент", "role": "получатель"}, ...],
#     "movements": [{"register": "...", "direction": "расход", "condition": "..."}],
#     "posting_flow": ["шаг 1", "шаг 2", ...],
#     "typical_scenarios": ["...", "..."],
#     "preconditions": ["..."],
#     "related_objects": ["Документ.X", "Регистр.Y"],
#     "its_links": [...]
#   }
#
# `source_hash` — SHA-256 от концентрата (MetadataObject XML hash +
# children edges из графа). При повторной генерации с тем же hash —
# карточка идемпотентна (skip LLM call).
#
# `embedding_model` / `embedding_dim` — служебные поля чтобы при смене
# embedding-провайдера пере-эмбедить старые карточки.
MIGRATIONS_V18 = [
    """
    CREATE TABLE IF NOT EXISTS typical_object_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT NOT NULL,
        object_qualified_name TEXT NOT NULL,
        object_kind TEXT NOT NULL,
        card_payload TEXT NOT NULL DEFAULT '{}',
        source_hash TEXT NOT NULL,
        prompt_version TEXT NOT NULL DEFAULT 'v1',
        llm_model TEXT,
        token_usage_in INTEGER,
        token_usage_out INTEGER,
        embedding_model TEXT,
        embedding_dim INTEGER,
        status TEXT NOT NULL DEFAULT 'pending',
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(channel_id, object_qualified_name)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_typical_cards_channel ON typical_object_cards(channel_id)",
    "CREATE INDEX IF NOT EXISTS idx_typical_cards_kind ON typical_object_cards(channel_id, object_kind)",
    "CREATE INDEX IF NOT EXISTS idx_typical_cards_status ON typical_object_cards(status)",
    "CREATE INDEX IF NOT EXISTS idx_typical_cards_hash ON typical_object_cards(source_hash)",
]


# v19 — Mock isolation (M-K2.5.9.2).
#
# `is_mock` — флаг что карточка сгенерирована Mock LLM провайдером
# (`llm_model='mock-generator-v1'`), а не реальной моделью. UI показывает
# бейдж «Mock data — не верифицировано экспертом», retrieval может
# фильтровать. Backfill — UPDATE для llm_model='mock-generator-v1'.
MIGRATIONS_V19 = [
    "ALTER TABLE typical_object_cards ADD COLUMN is_mock INTEGER NOT NULL DEFAULT 0",
    "UPDATE typical_object_cards SET is_mock = 1 WHERE llm_model = 'mock-generator-v1'",
    "CREATE INDEX IF NOT EXISTS idx_typical_cards_is_mock ON typical_object_cards(channel_id, is_mock)",
]

# v20 — Card validation against graph (M-K2.5.9.5, GraphEval-стиль).
#
# Карточка валидируется против семантического графа (граф = ground truth).
# Если LLM выдумала register которого нет в WRITES_TO edges объекта —
# это hallucination, бот должен видеть в payload и предупреждать
# пользователя.
#
# Поля:
#   validation_status — 'valid' | 'issues_found' | 'object_not_in_graph' | NULL (не валидирована)
#   validation_issues — JSON массив CardValidationIssue (severity/code/detail/field)
#   validated_at      — timestamp последней валидации
MIGRATIONS_V20 = [
    "ALTER TABLE typical_object_cards ADD COLUMN validation_status TEXT",
    "ALTER TABLE typical_object_cards ADD COLUMN validation_issues TEXT",
    "ALTER TABLE typical_object_cards ADD COLUMN validated_at TIMESTAMP",
    "CREATE INDEX IF NOT EXISTS idx_typical_cards_validation_status ON typical_object_cards(channel_id, validation_status)",
]

# v21 — Embedding model versioning (M-K2.5.9.6).
#
# `embedding_model_version` — семантическая версия embedding-пайплайна
# (например "v1.0", "v2.0"). Отличается от `embedding_model` (имя
# провайдера) тем, что фиксирует прошлые правила нарезки текста,
# постпроцессинга, etc.
#
# Use case: при смене embedding-провайдера (text-embedding-3-small →
# text-embedding-3-large) или правил text-extraction нужно явно
# пере-эмбедить старые карточки. Скрипт `scripts/typical_cards_reembed.py`
# фильтрует по версии и обновляет.
MIGRATIONS_V21 = [
    "ALTER TABLE typical_object_cards ADD COLUMN embedding_model_version TEXT",
    "CREATE INDEX IF NOT EXISTS idx_typical_cards_embedding_version ON typical_object_cards(embedding_model_version)",
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

    if current < 12:
        # index_runs table (v12, M-K2.2) — state machine для indexer'а.
        # Один row = одна попытка bulk_refresh. Status переходы:
        # pending → running → done | failed.
        # Используется POST/GET /knowledge/{ch}/index/* endpoints.
        for stmt in MIGRATIONS_V12:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (12,),
        )
        await db.commit()

    if current < 13:
        # vec_objects backing table (v13, M-K2.5) — обвязка для vec0 virtual
        # table из sqlite-vec. Сама vec0 создаётся в `vector_store.init_vector_store`
        # после `sqlite_vec.load(conn)`. Здесь только mapping таблица.
        for stmt in MIGRATIONS_V13:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (13,),
        )
        await db.commit()

    if current < 14:
        # its_chunks (v14, M-K2.7) — обвязочная таблица для ИТС RAG.
        # Чанки v8std (std/patterns/diagnostics/metod8dev/lang) хранят content
        # и metadata для JOIN с vec_objects по object_path.
        for stmt in MIGRATIONS_V14:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (14,),
        )
        await db.commit()

    if current < 15:
        # bsp_chunks (v15, M-K2.8) — обвязочная таблица для БСП RAG.
        # Экспортные методы CommonModules БСП 3.1/3.2 — для JOIN с vec_objects
        # по object_path = "bsp:<ver>:<Mod>.<Method>".
        for stmt in MIGRATIONS_V15:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (15,),
        )
        await db.commit()

    if current < 16:
        # Knowledge Graph (v16, M-K3.17.1a) — L2 Relational layer.
        # graph_nodes / graph_edges с recursive CTE для traversal.
        for stmt in MIGRATIONS_V16:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (16,),
        )
        await db.commit()

    if current < 17:
        # Typical Configurations infrastructure (v17, M-K2.5.0) — ADR-003.
        # typical_configurations реестр снапшотов УТ/ERP/КА/БП/ЗУП/УСО +
        # typical_indexing_runs журнал индексационных прогонов с FK CASCADE.
        for stmt in MIGRATIONS_V17:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (17,),
        )
        await db.commit()

    if current < 18:
        # Object Cards (v18, M-K2.5.5) — typical_object_cards с UNIQUE
        # на (channel_id, object_qualified_name) для idempotent generation.
        # source_hash для skip-если-неизменился. Эмбеддинг через embedding_*
        # поля (само значение в vec_objects через cross-reference).
        for stmt in MIGRATIONS_V18:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (18,),
        )
        await db.commit()

    if current < 19:
        # Mock isolation (v19, M-K2.5.9.2) — флаг is_mock + backfill
        # для существующих 63 197 карточек с llm_model='mock-generator-v1'.
        # Защита production: LLM/UI видят «не верифицировано экспертом»
        # для всех mock-карточек, чтобы аналитики не приняли stub за факт.
        for stmt in MIGRATIONS_V19:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (19,),
        )
        await db.commit()

    if current < 20:
        # Card validation against graph (v20, M-K2.5.9.5) — GraphEval-стиль.
        # Добавляет validation_status / validation_issues / validated_at для
        # хранения результата валидации карточки против семантического графа.
        # Граф = ground truth: если карточка ссылается на register которого
        # нет в WRITES_TO для объекта, это hallucination.
        for stmt in MIGRATIONS_V20:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (20,),
        )
        await db.commit()

    if current < 21:
        # Embedding model versioning (v21, M-K2.5.9.6). Фиксирует
        # семантическую версию embedding-пайплайна, чтобы при смене
        # модели или правил text-extraction можно было найти старые
        # карточки и пере-эмбедить через scripts/typical_cards_reembed.py.
        for stmt in MIGRATIONS_V21:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (21,),
        )
        await db.commit()
