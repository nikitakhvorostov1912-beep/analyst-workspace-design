"""Тесты для bsp_tool.py + admin endpoints /knowledge/bsp/* (M-K2.8).

Покрытие:
- BSP_TOOL_SCHEMA shape: required, types, enum для version
- is_bsp_tool / is_bsp_enabled
- _parse_args: query / k / version валидация + cap k
- _format_results_for_llm
- dispatch_bsp_tool happy / error paths
- routes: /bsp/status (empty, after reload, disabled)
- routes: /bsp/reload (400 not_ready, 500 missing roots, 200 happy, force=true)
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from app.config import Settings
from app.knowledge.bsp_indexer import index_bsp_corpus
from app.knowledge.bsp_search import BSPSearchHit
from app.knowledge.bsp_tool import (
    BSP_TOOL_SCHEMA,
    SEARCH_BSP_TOOL_NAME,
    _format_results_for_llm,
    _parse_args,
    dispatch_bsp_tool,
    is_bsp_enabled,
    is_bsp_tool,
)
from app.knowledge.embeddings import MockEmbeddingClient
from app.knowledge.its_tool import set_embedding_client_for_testing
from app.storage.migrations import apply_migrations


TEST_DIM = 4


def _force_fresh_settings() -> None:
    from app.config import get_settings
    get_settings.cache_clear()


def _make_ssl_root(tmp_path: Path, name: str = "ssl_3_2") -> Path:
    root = tmp_path / name
    target = root / "src" / "cf" / "CommonModules" / "ДлительныеОперации" / "Ext" / "Module.bsl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "#Область ПрограммныйИнтерфейс\n"
        "// Запускает функцию в фоне.\n"
        "Функция ВыполнитьФункцию(Парамы) Экспорт\n"
        "    Возврат Истина;\n"
        "КонецФункции\n"
        "#КонецОбласти\n",
        encoding="utf-8",
    )
    return root


@pytest_asyncio.fixture(autouse=True)
async def _reset_singleton():
    set_embedding_client_for_testing(None)
    yield
    set_embedding_client_for_testing(None)


@pytest_asyncio.fixture
async def db_with_bsp(tmp_path: Path):
    """In-memory DB с заэмбедженным корпусом БСП."""
    conn = await aiosqlite.connect(":memory:")
    await apply_migrations(conn)
    client = MockEmbeddingClient(dim=TEST_DIM)
    ssl_root = _make_ssl_root(tmp_path)
    await index_bsp_corpus(conn, client, [ssl_root])
    set_embedding_client_for_testing(client)
    yield conn
    await conn.close()


# ---------- Schema ----------


def test_schema_shape():
    assert BSP_TOOL_SCHEMA["type"] == "function"
    fn = BSP_TOOL_SCHEMA["function"]
    assert fn["name"] == SEARCH_BSP_TOOL_NAME == "search_bsp"
    params = fn["parameters"]
    assert params["required"] == ["query"]
    assert params["properties"]["version"]["enum"] == ["3.1", "3.2"]


def test_is_bsp_tool():
    assert is_bsp_tool("search_bsp")
    assert not is_bsp_tool("search_its")
    assert not is_bsp_tool("execute_query")


def test_is_bsp_enabled_settings(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("BSP_ENABLED", "true")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    s = Settings()
    assert is_bsp_enabled(s) is True


def test_is_bsp_disabled_when_its_not_ready(monkeypatch):
    """BSP не ready если ITS API key отсутствует (общий embedding client)."""
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("BSP_ENABLED", "true")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("ITS_EMBEDDING_API_KEY", "")
    monkeypatch.setenv("DEFAULT_LLM_API_KEY_OPENAI", "")
    s = Settings()
    assert is_bsp_enabled(s) is False


# ---------- _parse_args ----------


def test_parse_args_happy():
    q, k, v = _parse_args({"query": "x", "k": 3})
    assert q == "x"
    assert k == 3
    assert v is None


def test_parse_args_version_31():
    q, k, v = _parse_args({"query": "x", "version": "3.1"})
    assert v == "3.1"


def test_parse_args_version_invalid():
    with pytest.raises(ValueError, match="version"):
        _parse_args({"query": "x", "version": "4.0"})


def test_parse_args_caps_k():
    _, k, _ = _parse_args({"query": "x", "k": 999})
    assert k <= 20


def test_parse_args_missing_query():
    with pytest.raises(ValueError, match="query"):
        _parse_args({})


def test_parse_args_negative_k():
    with pytest.raises(ValueError, match="k"):
        _parse_args({"query": "x", "k": -5})


# ---------- _format_results_for_llm ----------


def test_format_empty():
    out = _format_results_for_llm([])
    assert out == {"results": [], "total": 0}


def test_format_includes_citation_not_distance():
    hit = BSPSearchHit(
        module_name="ДлительныеОперации", method_name="ВыполнитьФункцию",
        method_kind="Функция", signature="sig", doc_comment="doc",
        content="full", version="3.2", source_path="x", distance=0.1,
    )
    out = _format_results_for_llm([hit])
    r = out["results"][0]
    assert "distance" not in r
    assert "БСП" in r["citation"]
    assert "ДлительныеОперации.ВыполнитьФункцию" in r["citation"]
    assert r["version"] == "3.2"


# ---------- dispatch_bsp_tool ----------


@pytest.mark.asyncio
async def test_dispatch_happy(db_with_bsp, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("BSP_ENABLED", "true")
    monkeypatch.setenv("ITS_EMBEDDING_DIM", str(TEST_DIM))
    s = Settings()

    ok, result, err = await dispatch_bsp_tool(
        db_with_bsp, s, "search_bsp", {"query": "длительные"},
    )
    assert ok is True
    assert err is None
    assert isinstance(result, dict)
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_dispatch_invalid_args(db_with_bsp, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    s = Settings()
    ok, _, err = await dispatch_bsp_tool(db_with_bsp, s, "search_bsp", {})
    assert ok is False
    assert "query" in err


@pytest.mark.asyncio
async def test_dispatch_wrong_name(db_with_bsp, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    s = Settings()
    ok, _, err = await dispatch_bsp_tool(db_with_bsp, s, "not_bsp", {})
    assert ok is False
    assert "Неизвестный" in err


# ---------- /knowledge/bsp/status ----------


@pytest.mark.asyncio
async def test_status_empty(client, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("BSP_ENABLED", "true")
    _force_fresh_settings()

    r = await client.get("/knowledge/bsp/status")
    assert r.status_code == 200
    body = r.json()
    assert body["methods"] == 0
    assert body["modules"] == 0
    assert body["enabled"] is True
    assert body["ready"] is True  # mock provider
    assert isinstance(body["ssl_roots"], list)


@pytest.mark.asyncio
async def test_status_disabled(client, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("BSP_ENABLED", "false")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    _force_fresh_settings()

    r = await client.get("/knowledge/bsp/status")
    assert r.json()["enabled"] is False
    assert r.json()["ready"] is False


# ---------- /knowledge/bsp/reload ----------


@pytest.mark.asyncio
async def test_reload_400_when_not_ready(client, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("BSP_ENABLED", "true")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("ITS_EMBEDDING_API_KEY", "")
    _force_fresh_settings()

    r = await client.post("/knowledge/bsp/reload")
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "bsp_not_ready"


@pytest.mark.asyncio
async def test_reload_500_when_roots_missing(client, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("BSP_ENABLED", "true")
    monkeypatch.setenv(
        "BSP_SSL_ROOTS",
        f"{tmp_path / 'no_ssl_31'},{tmp_path / 'no_ssl_32'}",
    )
    _force_fresh_settings()

    from app.knowledge.its_tool import reset_embedding_client
    await reset_embedding_client()

    r = await client.post("/knowledge/bsp/reload")
    assert r.status_code == 500
    assert r.json()["detail"]["error"] == "bsp_ssl_roots_missing"


@pytest.mark.asyncio
async def test_reload_happy(client, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("ITS_EMBEDDING_DIM", str(TEST_DIM))
    monkeypatch.setenv("BSP_ENABLED", "true")
    ssl_root = _make_ssl_root(tmp_path)
    monkeypatch.setenv("BSP_SSL_ROOTS", str(ssl_root))
    _force_fresh_settings()

    from app.knowledge.its_tool import reset_embedding_client
    await reset_embedding_client()

    r = await client.post("/knowledge/bsp/reload")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "done"
    assert body["methods_embedded"] == 1

    # Status показывает counts
    s = await client.get("/knowledge/bsp/status")
    sb = s.json()
    assert sb["methods"] == 1
    assert sb["modules"] == 1


@pytest.mark.asyncio
async def test_reload_force(client, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("ITS_EMBEDDING_DIM", str(TEST_DIM))
    monkeypatch.setenv("BSP_ENABLED", "true")
    ssl_root = _make_ssl_root(tmp_path)
    monkeypatch.setenv("BSP_SSL_ROOTS", str(ssl_root))
    _force_fresh_settings()

    from app.knowledge.its_tool import reset_embedding_client
    await reset_embedding_client()

    # 1-й reload
    r1 = await client.post("/knowledge/bsp/reload")
    assert r1.json()["methods_embedded"] == 1

    # 2-й — skip
    r2 = await client.post("/knowledge/bsp/reload")
    assert r2.json()["methods_embedded"] == 0
    assert r2.json()["methods_skipped"] == 1

    # force=true — embedded again
    r3 = await client.post("/knowledge/bsp/reload?force=true")
    assert r3.json()["methods_embedded"] == 1
