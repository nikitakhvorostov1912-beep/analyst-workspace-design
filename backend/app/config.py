from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:////data/app.db"

    # SEC-04: CORS fail-secure — дефолт пустой. Production ДОЛЖЕН задать BACKEND_ALLOWED_ORIGINS.
    # Пустой дефолт означает 0 allowed origins при деплое без env → явный fail-secure.
    # validation_alias позволяет pydantic-settings читать из env BACKEND_ALLOWED_ORIGINS.
    cors_origins: str = Field(default="", validation_alias="BACKEND_ALLOWED_ORIGINS")

    log_level: str = "INFO"
    # Дефолтные параметры LLM — Xiaomi MiMo v2.5-pro (приоритетный провайдер по
    # memory/llm-providers.md). При первом запуске сидятся в llm_settings,
    # пользователю остаётся ввести только API-ключ через UI.
    default_llm_endpoint: str = Field(
        default="https://api.xiaomimimo.com/v1", validation_alias="DEFAULT_LLM_ENDPOINT"
    )
    default_llm_model: str = Field(
        default="mimo-v2.5-pro", validation_alias="DEFAULT_LLM_MODEL"
    )
    default_llm_temperature: float = Field(
        default=0.3, validation_alias="DEFAULT_LLM_TEMPERATURE"
    )
    # API-ключ дефолтного провайдера. Хранится только в env (не в git, не в БД).
    # Если задан — backend подставляет его в LLM-вызовы как fallback, когда
    # frontend не передал X-LLM-API-Key. UI узнаёт о наличии через флаг
    # has_env_api_key в GET /llm-config (значение НЕ раскрывается клиенту).
    default_llm_api_key: str = Field(default="", validation_alias="DEFAULT_LLM_API_KEY")
    app_version: str = "0.1.0"

    # Дефолтное MCP-подключение — встроенный сервер MCP_Toolkit EPF на :6010
    # (см. memory/feedback_1c_transit_mcp_embedded_6010.md). Создаётся при первом
    # запуске чтобы аналитик мог сразу зайти в чат без ручной настройки.
    default_mcp_name: str = Field(default="Транзит", validation_alias="DEFAULT_MCP_NAME")
    default_mcp_endpoint: str = Field(
        default="http://localhost:6010/mcp", validation_alias="DEFAULT_MCP_ENDPOINT"
    )
    default_mcp_kind: Literal["embedded", "proxy"] = Field(
        default="embedded", validation_alias="DEFAULT_MCP_KIND"
    )
    default_mcp_channel: str = Field(
        default="", validation_alias="DEFAULT_MCP_CHANNEL"
    )
    default_mcp_anon_enabled: bool = Field(
        default=False, validation_alias="DEFAULT_MCP_ANON_ENABLED"
    )

    # Сидирование дефолтов в БД при старте. True по умолчанию — Electron инсталлер
    # должен создавать рабочий профиль из коробки. False — для unit-тестов, где
    # нужна пустая БД (см. tests/conftest.py).
    seed_on_startup: bool = Field(default=True, validation_alias="SEED_ON_STARTUP")

    # Среда — backend держит для будущих gates (фронтенд CSP читает NODE_ENV напрямую)
    environment: Literal["dev", "prod"] = "dev"

    # === Aux MCP: bsl-context (справочник API платформы 1С) ===
    # Если оба пути заданы, orchestrator подключит bsl-context как дополнительный
    # источник tools (search/info/getMember/getMembers/getConstructors) поверх
    # основного 1С MCP. LLM видит их в едином списке.
    bsl_context_jar: str = Field(default="", validation_alias="BSL_CONTEXT_JAR_PATH")
    bsl_context_java: str = Field(default="java", validation_alias="BSL_CONTEXT_JAVA")
    bsl_context_platform_path: str = Field(
        default="", validation_alias="BSL_CONTEXT_PLATFORM_PATH"
    )

    # === Sprint 1 (Hermes integration) — Memory / Learning / Aux ===
    # Корень для MEMORY.md / USER.md. Per-channel поддиректории создаются автоматически.
    # Если не задано — используется <home>/.analyst-1c/memory.
    memory_root: str = Field(default="", validation_alias="MEMORY_ROOT")

    # Корень для trajectory JSONL логов (будущий fine-tuning датасет).
    trajectory_dir: str = Field(default="", validation_alias="TRAJECTORY_DIR")

    # Включить background trajectory logging. False = no-op.
    learning_enabled: bool = Field(default=True, validation_alias="LEARNING_ENABLED")

    # Включить MemoryManager. False = система памяти полностью отключена.
    memory_enabled: bool = Field(default=True, validation_alias="MEMORY_ENABLED")

    # Дешёвая aux модель для будущих compressor/curator/review (Sprint 2/3).
    # Пустое = использовать main модель (нет экономии но работает).
    aux_model: str = Field(default="", validation_alias="AUX_MODEL")

    # === Sprint 2 (Hermes Context & Resilience) ===
    # Размер контекстного окна основной модели в токенах. Используется
    # ContextCompressor для триггера автосжатия. MiMo v2.5-pro = 128k.
    max_context_tokens: int = Field(default=128_000, validation_alias="MAX_CONTEXT_TOKENS")

    # Порог автозапуска компрессии (доля от max_context_tokens).
    # 0.75 = при заполнении 75% начинаем сжимать.
    compression_threshold_ratio: float = Field(
        default=0.75, validation_alias="COMPRESSION_THRESHOLD_RATIO"
    )

    # Включить ContextCompressor. False = no-op (для отладки / тестов).
    compression_enabled: bool = Field(default=True, validation_alias="COMPRESSION_ENABLED")

    # Бюджет итераций tool-calling loop. Прежняя константа MAX_TOOL_ITERATIONS=100.
    iteration_budget: int = Field(default=100, validation_alias="ITERATION_BUDGET")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,  # позволяет использовать и поле-имя и alias
    }

    @property
    def cors_origins_list(self) -> list[str]:
        """Возвращает список origins. Пропускает пустые строки.

        SEC-04 fail-secure: в production без env → пустой список (CORS закрыт).
        В dev режиме (default environment="dev") при пустом env подставляем localhost
        фронта чтобы `pnpm dev` + `python -m uvicorn` работали из коробки без .env.
        Production деплой обязан задать BACKEND_ALLOWED_ORIGINS явно.
        """
        explicit = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if explicit:
            return explicit
        if self.environment == "dev":
            return ["http://localhost:3010", "http://127.0.0.1:3010"]
        return []

    @property
    def memory_root_path(self) -> "Path":
        """Resolve MEMORY.md/USER.md root. Defaults to <home>/.analyst-1c/memory."""
        from pathlib import Path

        if self.memory_root:
            return Path(self.memory_root).expanduser()
        return Path.home() / ".analyst-1c" / "memory"

    @property
    def trajectory_dir_path(self) -> "Path":
        """Resolve trajectory JSONL root. Defaults to <home>/.analyst-1c/trajectories."""
        from pathlib import Path

        if self.trajectory_dir:
            return Path(self.trajectory_dir).expanduser()
        return Path.home() / ".analyst-1c" / "trajectories"

    @property
    def sqlite_path(self) -> str:
        """Извлекает путь к файлу SQLite из DATABASE_URL.

        sqlite+aiosqlite:////data/app.db  → /data/app.db
        sqlite+aiosqlite:///:memory:      → :memory:
        """
        url = self.database_url
        triple_slash = "sqlite+aiosqlite:///"
        if url.startswith(triple_slash):
            return url[len(triple_slash):]
        prefix = "sqlite+aiosqlite://"
        if url.startswith(prefix):
            return url[len(prefix):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
