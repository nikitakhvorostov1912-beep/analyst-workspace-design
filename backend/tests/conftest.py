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
