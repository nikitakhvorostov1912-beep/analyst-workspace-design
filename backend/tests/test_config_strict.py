"""Тесты config.py — CORS origins + BACKEND_ALLOWED_ORIGINS."""


import pytest


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    """Сбрасываем lru_cache get_settings() перед/после теста и чистим env."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_cors_origins_empty_by_default(monkeypatch):
    """SEC-04 fail-secure: в production без env → cors_origins_list == [].
    Dev environment получает localhost fallback для UX (см. config.py docstring)."""
    monkeypatch.delenv("BACKEND_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "prod")

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.cors_origins == ""
    assert settings.cors_origins_list == []


def test_settings_cors_origins_dev_default(monkeypatch):
    """Dev environment + пустой env → localhost:3010 fallback (UX из коробки)."""
    monkeypatch.delenv("BACKEND_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "dev")

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.cors_origins_list == [
        "http://localhost:3010",
        "http://127.0.0.1:3010",
    ]


def test_settings_cors_origins_from_env(monkeypatch):
    """BACKEND_ALLOWED_ORIGINS='https://a,https://b' → cors_origins_list == ['https://a', 'https://b']."""
    monkeypatch.setenv("BACKEND_ALLOWED_ORIGINS", "https://a,https://b")

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    assert "https://a" in settings.cors_origins_list
    assert "https://b" in settings.cors_origins_list
    assert len(settings.cors_origins_list) == 2
