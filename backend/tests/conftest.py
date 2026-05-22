import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Используем in-memory SQLite для тестов — устанавливаем ДО импорта app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["APP_VERSION"] = "0.1.0"
# SEC-04: CORS configurable через BACKEND_ALLOWED_ORIGINS (план 3.2)
# В тестах разрешаем localhost для ASGI transport (не реальный CORS)
os.environ["BACKEND_ALLOWED_ORIGINS"] = "http://localhost:3010"
# Seed-дефолты (LLM + MCP) применяются в проде при первом запуске. В тестах
# они мешают сценариям «пустая БД → null» — отключаем через env флаг.
os.environ["SEED_ON_STARTUP"] = "false"
# W1.4 (2026-05-22): изоляция от dev-машинного backend/.env. На machine
# разработчика может лежать .env с реальным DEFAULT_LLM_API_KEY (Multi-LLM
# зашитые ключи). pydantic-settings подхватывает их в Settings() автоматом,
# что ломает тесты с проверками «нет ключа → 400». Очищаем явно.
for _provider_key in (
    "DEFAULT_LLM_API_KEY",
    "DEFAULT_LLM_API_KEY_NVIDIA",
    "DEFAULT_LLM_API_KEY_OPENAI",
    "DEFAULT_LLM_API_KEY_OPENROUTER",
    "DEFAULT_LLM_API_KEY_CLOUD_RU",  # P2.1 (2026-05-23): Cloud.ru env-fallback
):
    os.environ.pop(_provider_key, None)
# Также блокируем чтение backend/.env в тестах через config.py override.
# См. Settings.model_config — env_file берётся из PYDANTIC_ENV_FILE.
os.environ["PYDANTIC_ENV_FILE"] = ""


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Сбрасываем lru_cache get_settings() между тестами."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client():
    """AsyncClient с ASGI транспортом и запущенным lifespan."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        async with app.router.lifespan_context(app):
            yield ac


@pytest.fixture(autouse=True)
def _reset_pending():
    """Сбрасываем safety._pending между тестами."""
    yield
    try:
        from app.orchestrator.safety import _pending
        _pending.clear()
    except (ImportError, AttributeError):
        pass


@pytest_asyncio.fixture
async def db():
    """Отдельное aiosqlite соединение для тестов БД."""
    import aiosqlite

    from app.storage.migrations import apply_migrations

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)
    yield conn
    await conn.close()
