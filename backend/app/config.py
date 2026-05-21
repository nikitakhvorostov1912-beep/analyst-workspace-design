from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


# ---------------------------------------------------------------------------
# Auto-detect для bsl-context (JAR + Java + платформа 1С)
# ---------------------------------------------------------------------------
# Хелперы вне класса Settings — чтобы их можно было дешёво вызывать из @property
# (Settings кеширован lru_cache, но resolve может зависеть от свежего sys.path
# и FS-состояния, например JAR недавно положен Electron'ом).


def _bundle_search_dirs() -> list[Path]:
    """Каталоги где ищем bundled artefacts (JAR-ы, скрипты).

    Покрывает два сценария:
    - PyInstaller frozen: backend.exe в `<exe-dir>` → ищем `<exe-dir>/bsl/`
      и `_MEIPASS/bsl/` (если кто-то положил внутрь архива).
    - Dev-режим: `backend/app/config.py` → ищем `<repo>/desktop/resources/bsl/`.
    """
    import sys

    dirs: list[Path] = []
    if getattr(sys, "frozen", False):
        # PyInstaller onefile: sys.executable = backend.exe в Programs/.../resources/
        exe_dir = Path(sys.executable).resolve().parent
        dirs.append(exe_dir)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(Path(meipass))
    else:
        # Dev: app/config.py → backend/ → repo-root → desktop/resources/
        here = Path(__file__).resolve()
        repo_root = here.parent.parent.parent  # app/ → backend/ → repo
        dirs.append(repo_root / "desktop" / "resources")
    return dirs


def _find_bundled_bsl_jar() -> str:
    """Ищет `bsl/mcp-bsl-context-*.jar` в bundle-каталогах. Самый свежий по версии."""
    candidates: list[Path] = []
    for base in _bundle_search_dirs():
        bsl_dir = base / "bsl"
        if bsl_dir.is_dir():
            candidates.extend(sorted(bsl_dir.glob("mcp-bsl-context-*.jar")))
    if not candidates:
        return ""
    # Берём последний — sorted даёт лексикографический порядок, что для
    # "mcp-bsl-context-0.3.2.jar" совпадает с возрастанием версий.
    return str(candidates[-1])


def _find_system_java() -> str:
    """Возвращает путь к java.exe.

    Порядок поиска:
      1) bundled JRE в `<exe-dir>/jre/bin/java.exe` (Electron кладёт minimal JRE
         собранный через jlink — ~54 MB). Это гарантия что у коллег без
         установленной Java справочник BSL всё равно работает.
      2) системный java из PATH через `shutil.which("java")`.
      3) пустая строка — справочник BSL не подключится, в /status будет
         подсказка установить Java.
    """
    import shutil
    import sys

    # 1) Bundled JRE
    for base in _bundle_search_dirs():
        candidate = base / "jre" / "bin" / ("java.exe" if sys.platform == "win32" else "java")
        if candidate.is_file():
            return str(candidate)

    # 2) Системный java
    found = shutil.which("java")
    return found or ""


def _find_latest_1c_platform() -> str:
    """Ищет самую свежую установленную платформу 1С в стандартных каталогах.

    Перебираем `C:\\Program Files\\1cv8\\*` (и x86) + `~/AppData/Local/Programs/
    1cv8/*` (некоторые ставят в user-scope). Сортируем по имени-версии (для
    "8.3.27.1719" работает лексикографически) и берём последнюю.
    """
    import os
    import sys

    if sys.platform != "win32":
        return ""

    roots: list[Path] = []
    for env_var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        p = os.environ.get(env_var)
        if p:
            roots.append(Path(p) / "1cv8")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "Programs" / "1cv8")

    versions: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            # 1С каталоги — вида "8.3.27.1719"
            if child.is_dir() and child.name.startswith("8."):
                if (child / "bin" / "1cv8.exe").is_file():
                    versions.append(child)

    if not versions:
        return ""
    versions.sort(key=lambda p: p.name)
    return str(versions[-1])


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
    # API-ключи. Хранятся только в env (не в git, не в БД). Если для текущего
    # endpoint найден соответствующий ключ — backend подставляет его как fallback,
    # когда frontend не передал X-LLM-API-Key. UI узнаёт о наличии через флаг
    # has_env_api_key в GET /llm-config (значения НЕ раскрываются клиенту).
    #
    # Универсальный (MiMo / любой OpenAI-совместимый endpoint без специализированного ключа):
    default_llm_api_key: str = Field(default="", validation_alias="DEFAULT_LLM_API_KEY")
    # Per-provider ключи — подбираются по endpoint URL.
    # Добавлены 2026-05-21 для коллег пользователя (NVIDIA NIM ключ зашит в дистрибутиве).
    default_llm_api_key_nvidia: str = Field(
        default="", validation_alias="DEFAULT_LLM_API_KEY_NVIDIA"
    )
    default_llm_api_key_openai: str = Field(
        default="", validation_alias="DEFAULT_LLM_API_KEY_OPENAI"
    )
    default_llm_api_key_openrouter: str = Field(
        default="", validation_alias="DEFAULT_LLM_API_KEY_OPENROUTER"
    )

    app_version: str = "0.1.0"

    # Дефолтное MCP-подключение — встроенный сервер MCP_Toolkit EPF на :6010
    # (см. memory/feedback_1c_transit_mcp_embedded_6010.md). Создаётся при первом
    # запуске чтобы аналитик мог сразу зайти в чат без ручной настройки.
    # Имя дефолтного подключения — нейтральное «Моя база 1С», чтобы коллегам
    # сразу было понятно «это моя локальная база, нужно проверить порт».
    # Раньше было «Транзит» / «КА Демо» — оба сбивали с толку («что это? нужно?»).
    default_mcp_name: str = Field(default="Моя база 1С", validation_alias="DEFAULT_MCP_NAME")
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
    # Если все три пути доступны (JAR, Java, платформа 1С), orchestrator подключит
    # bsl-context как дополнительный источник tools (search/info/getMember/
    # getMembers/getConstructors) поверх основного 1С MCP. LLM видит их в едином
    # списке.
    #
    # Resolve-стратегия (см. resolved_bsl_* ниже):
    #   1) env var (BSL_CONTEXT_*) — если пользователь задал
    #   2) bundled путь из Electron (resources/bsl/, передаётся через env)
    #   3) auto-detect (системный java, типовой путь к платформе)
    bsl_context_jar: str = Field(default="", validation_alias="BSL_CONTEXT_JAR_PATH")
    bsl_context_java: str = Field(default="", validation_alias="BSL_CONTEXT_JAVA")
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

    def resolve_default_api_key(self, endpoint: str) -> str:
        """Подбирает env-ключ для конкретного провайдера по endpoint URL.

        Возвращает пустую строку если для endpoint нет зашитого ключа —
        тогда backend должен потребовать X-LLM-API-Key от клиента.

        Логика проверки совпадает с UI (lib/llm-providers.ts):
        - integrate.api.nvidia.com → NVIDIA ключ
        - api.openai.com → OpenAI ключ
        - openrouter.ai → OpenRouter ключ
        - api.xiaomimimo.com / прочее → универсальный (исторически MiMo)
        """
        if not endpoint:
            return self.default_llm_api_key
        url = endpoint.lower()
        if "nvidia.com" in url and self.default_llm_api_key_nvidia:
            return self.default_llm_api_key_nvidia
        if "api.openai.com" in url and self.default_llm_api_key_openai:
            return self.default_llm_api_key_openai
        if "openrouter.ai" in url and self.default_llm_api_key_openrouter:
            return self.default_llm_api_key_openrouter
        return self.default_llm_api_key

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
    def memory_root_path(self) -> Path:
        """Resolve MEMORY.md/USER.md root. Defaults to <home>/.analyst-1c/memory."""
        if self.memory_root:
            return Path(self.memory_root).expanduser()
        return Path.home() / ".analyst-1c" / "memory"

    @property
    def trajectory_dir_path(self) -> Path:
        """Resolve trajectory JSONL root. Defaults to <home>/.analyst-1c/trajectories."""
        if self.trajectory_dir:
            return Path(self.trajectory_dir).expanduser()
        return Path.home() / ".analyst-1c" / "trajectories"

    # ---------------------------------------------------------------------
    # BSL-context auto-detect: чтобы у коллег работало «из коробки»
    # ---------------------------------------------------------------------
    # Сценарий: на машине коллеги .env с BSL_CONTEXT_* НЕ заполнен. Раньше
    # справочник просто не подключался. Теперь:
    #   1) JAR — bundled в `<exe-dir>/bsl/mcp-bsl-context-*.jar` (Electron
    #      кладёт его в resources). В dev — `<repo>/desktop/resources/bsl/`.
    #   2) Java — системный `java.exe` из PATH (`shutil.which`).
    #   3) Платформа 1С — самая свежая из `C:\Program Files\1cv8\*`.
    # Все три источника опциональные. Если хоть один не найден — справочник
    # не подключается и в /status показывается понятная подсказка.

    @property
    def resolved_bsl_jar(self) -> str:
        """JAR справочника BSL. Env override → bundled → пусто."""
        if self.bsl_context_jar:
            return self.bsl_context_jar
        return _find_bundled_bsl_jar()

    @property
    def resolved_bsl_java(self) -> str:
        """Путь к java.exe. Env override → системный PATH → пусто."""
        if self.bsl_context_java:
            return self.bsl_context_java
        return _find_system_java()

    @property
    def resolved_bsl_platform_path(self) -> str:
        """Каталог платформы 1С. Env override → auto-detect → пусто."""
        if self.bsl_context_platform_path:
            return self.bsl_context_platform_path
        return _find_latest_1c_platform()

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
