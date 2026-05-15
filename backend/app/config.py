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
    default_llm_endpoint: str = "https://api.openai.com/v1"
    default_llm_model: str = "gpt-4o-mini"
    app_version: str = "0.1.0"

    # Среда — backend держит для будущих gates (фронтенд CSP читает NODE_ENV напрямую)
    environment: Literal["dev", "prod"] = "dev"

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
