from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:////data/app.db"
    cors_origins: str = "http://localhost:3010"
    log_level: str = "INFO"
    default_llm_endpoint: str = "https://api.openai.com/v1"
    default_llm_model: str = "gpt-4o-mini"
    app_version: str = "0.1.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def sqlite_path(self) -> str:
        """Извлекает путь к файлу SQLite из DATABASE_URL.

        sqlite+aiosqlite:////data/app.db  → /data/app.db
        sqlite+aiosqlite:///:memory:      → :memory:
        """
        url = self.database_url
        # Стандартный формат: sqlite+aiosqlite:/// + path
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
