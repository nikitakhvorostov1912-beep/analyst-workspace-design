"""Тесты для ITS RAG admin endpoints (M-K2.7).

Покрытие:
- GET /knowledge/its/status: пустой индекс, после reload, флаги ready/enabled
- POST /knowledge/its/reload:
  - 400 когда settings.is_its_ready=False
  - 500 когда docs_root не существует
  - 200 happy path (через mock embedding client + temp docs)
  - force=true перезаписывает skip-by-hash
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _force_fresh_settings() -> None:
    """Сбрасывает get_settings() lru_cache.

    Нужно после monkeypatch.setenv: client fixture стартует app до
    тела теста и может закэшировать дефолтные Settings.
    """
    from app.config import get_settings
    get_settings.cache_clear()


def _prepare_corpus(tmp_path: Path) -> Path:
    """Создаёт временный docs/ tree с 2 std-файлами."""
    root = tmp_path / "docs"
    (root / "std").mkdir(parents=True)
    (root / "std" / "396.md").write_text(
        "###### #std396\n\n# Title 396\n\nbody",
        encoding="utf-8",
    )
    (root / "std" / "400.md").write_text(
        "###### #std400\n\n# Title 400\n\nbody",
        encoding="utf-8",
    )
    return root


# ---------- /knowledge/its/status ----------


@pytest.mark.asyncio
async def test_its_status_empty_index(client, monkeypatch):
    """Свежий индекс — chunks=0, documents=0."""
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("ITS_EMBEDDING_DIM", "4")
    monkeypatch.setenv("ITS_ENABLED", "true")
    _force_fresh_settings()
    response = await client.get("/knowledge/its/status")
    assert response.status_code == 200
    data = response.json()
    assert data["chunks"] == 0
    assert data["documents"] == 0
    assert data["enabled"] is True
    assert data["ready"] is True  # mock provider всегда ready
    assert data["provider"] == "mock"
    assert data["dim"] == 4


@pytest.mark.asyncio
async def test_its_status_after_reload(client, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("ITS_EMBEDDING_DIM", "4")
    monkeypatch.setenv("ITS_ENABLED", "true")
    root = _prepare_corpus(tmp_path)
    monkeypatch.setenv("ITS_DOCS_ROOT", str(root))
    _force_fresh_settings()

    # Сброс singleton чтобы dispatch_its_tool взял настройки заново
    from app.knowledge.its_tool import reset_embedding_client
    await reset_embedding_client()

    r = await client.post("/knowledge/its/reload")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "done"
    assert body["docs_total"] == 2
    assert body["chunks_embedded"] == 2

    status = await client.get("/knowledge/its/status")
    sb = status.json()
    assert sb["chunks"] == 2
    assert sb["documents"] == 2


@pytest.mark.asyncio
async def test_its_status_disabled_flag(client, monkeypatch):
    """is_its_ready=False когда ITS_ENABLED=false."""
    monkeypatch.setenv("ITS_ENABLED", "false")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    _force_fresh_settings()

    r = await client.get("/knowledge/its/status")
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is False
    assert data["ready"] is False


# ---------- /knowledge/its/reload ----------


@pytest.mark.asyncio
async def test_its_reload_returns_400_when_not_ready(client, monkeypatch):
    """openai без ключа → 400."""
    monkeypatch.setenv("ITS_ENABLED", "true")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("ITS_EMBEDDING_API_KEY", "")
    _force_fresh_settings()

    r = await client.post("/knowledge/its/reload")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "its_not_ready"


@pytest.mark.asyncio
async def test_its_reload_returns_500_when_docs_missing(
    client, monkeypatch, tmp_path: Path,
):
    """Несуществующий ITS_DOCS_ROOT → 500."""
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("ITS_ENABLED", "true")
    monkeypatch.setenv("ITS_DOCS_ROOT", str(tmp_path / "does-not-exist"))
    _force_fresh_settings()

    from app.knowledge.its_tool import reset_embedding_client
    await reset_embedding_client()

    r = await client.post("/knowledge/its/reload")
    assert r.status_code == 500
    assert r.json()["detail"]["error"] == "its_docs_root_missing"


@pytest.mark.asyncio
async def test_its_reload_force_reindex(client, monkeypatch, tmp_path: Path):
    """force=true → chunks_embedded > 0 даже на повторном вызове."""
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("ITS_EMBEDDING_DIM", "4")
    monkeypatch.setenv("ITS_ENABLED", "true")
    root = _prepare_corpus(tmp_path)
    monkeypatch.setenv("ITS_DOCS_ROOT", str(root))
    _force_fresh_settings()

    from app.knowledge.its_tool import reset_embedding_client
    await reset_embedding_client()

    # Первый reload
    r1 = await client.post("/knowledge/its/reload")
    assert r1.status_code == 200
    assert r1.json()["chunks_embedded"] == 2

    # Второй — должен skip
    r2 = await client.post("/knowledge/its/reload")
    assert r2.json()["chunks_embedded"] == 0
    assert r2.json()["chunks_skipped"] == 2

    # С force=true — снова embedded
    r3 = await client.post("/knowledge/its/reload?force=true")
    assert r3.json()["chunks_embedded"] == 2
    assert r3.json()["chunks_skipped"] == 0
