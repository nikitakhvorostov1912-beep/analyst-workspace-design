"""W1.4 (2026-05-22): rate-limit на POST /chat (slowapi).

Защита от DoS / UI-багов / автоматического спама. Дефолт 30/minute. После
превышения возвращается 429 + JSON {detail, code: rate_limit_exceeded}.

Тест использует FastAPI TestClient напрямую (не через httpx.AsyncClient,
т.к. slowapi middleware гораздо проще верифицировать на TestClient).
"""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_low_limit(monkeypatch):
    """Force низкий лимит (3/minute) для теста.

    Сбрасывает in-memory storage slowapi между тестами — иначе счётчики
    переносятся и второй тест видит 429 от первого.
    Также чистит lru_cache на get_settings ДО и ПОСЛЕ, чтобы env-vars из
    этого теста не залипали в другие.
    """
    monkeypatch.setenv("CHAT_RATE_LIMIT", "3/minute")

    import app.config
    import app.routes.chat as chat_mod

    # ДО: освобождаем cache, чтобы новые env-vars подхватились
    app.config.get_settings.cache_clear()
    if hasattr(chat_mod.chat_limiter, "reset"):
        chat_mod.chat_limiter.reset()

    from app.main import create_app
    yield create_app()

    # ПОСЛЕ: тоже чистим — иначе следующий тест увидит наш dummy ключ
    app.config.get_settings.cache_clear()
    if hasattr(chat_mod.chat_limiter, "reset"):
        chat_mod.chat_limiter.reset()


def test_chat_rate_limit_429_after_exceed(app_low_limit, monkeypatch):
    """4-й запрос за минуту → 429 с code='rate_limit_exceeded'."""
    monkeypatch.setenv("DEFAULT_LLM_API_KEY", "dummy")
    # In-memory DB чтобы lifespan не упал на отсутствии /data/app.db
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("SEED_ON_STARTUP", "false")

    payload = {"message": "тест", "channel_id": "non-existent"}

    with TestClient(app_low_limit) as client:
        # Первые 3 запроса — могут вернуть 400/500 (нет valid channel) но НЕ 429
        statuses = []
        for _ in range(3):
            r = client.post("/chat", json=payload)
            statuses.append(r.status_code)

        # 4-й запрос — должен быть 429
        r4 = client.post("/chat", json=payload)
        assert r4.status_code == 429, (
            f"Expected 429 on 4th request (limit=3/minute), got {r4.status_code}. "
            f"First 3 statuses: {statuses}"
        )

        data = r4.json()
        assert data.get("code") == "rate_limit_exceeded"
        assert "Retry-After" in r4.headers


def test_chat_under_limit_does_not_429(app_low_limit, monkeypatch):
    """2 запроса (limit=3) → ни один не 429."""
    monkeypatch.setenv("DEFAULT_LLM_API_KEY", "dummy")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("SEED_ON_STARTUP", "false")

    payload = {"message": "тест", "channel_id": "non-existent"}

    with TestClient(app_low_limit) as client:
        for _ in range(2):
            r = client.post("/chat", json=payload)
            assert r.status_code != 429, f"Unexpected 429: {r.status_code}"
