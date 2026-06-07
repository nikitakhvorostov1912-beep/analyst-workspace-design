"""Тесты для backend/app/knowledge/its_tool.py (M-K2.7).

Покрытие:
- ITS_TOOL_SCHEMA shape: name, required, types
- is_its_tool / is_its_enabled
- _parse_args: валидация + cap k
- _build_embedding_client: openai / mock / unknown
- get_embedding_client singleton + reset
- dispatch_its_tool happy / error paths
- _format_results_for_llm
- Settings.is_its_ready / resolved_its_api_key (через mock Settings)
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from app.config import Settings
from app.knowledge.embeddings import MockEmbeddingClient, OpenAIEmbeddingClient
from app.knowledge.its_indexer import index_its_corpus
from app.knowledge.its_search import ITSSearchHit
from app.knowledge.its_tool import (
    ITS_TOOL_SCHEMA,
    SEARCH_ITS_TOOL_NAME,
    _build_embedding_client,
    _format_results_for_llm,
    _parse_args,
    dispatch_its_tool,
    get_embedding_client,
    is_its_enabled,
    is_its_tool,
    its_index_ready,
    reset_embedding_client,
    set_embedding_client_for_testing,
)
from app.storage.migrations import apply_migrations


TEST_DIM = 4


@pytest_asyncio.fixture(autouse=True)
async def _reset_singleton():
    """Перед каждым тестом — чистый singleton."""
    set_embedding_client_for_testing(None)
    yield
    set_embedding_client_for_testing(None)


@pytest_asyncio.fixture
async def db_indexed(tmp_path: Path):
    """In-memory DB с минимальным заэмбедженным корпусом."""
    conn = await aiosqlite.connect(":memory:")
    await apply_migrations(conn)
    client = MockEmbeddingClient(dim=TEST_DIM)

    root = tmp_path / "docs"
    (root / "std").mkdir(parents=True)
    (root / "std" / "396.md").write_text(
        "###### #std396\n\n# Обработчик ОбработкаЗаполнения\n\nbody A",
        encoding="utf-8",
    )
    (root / "std" / "400.md").write_text(
        "###### #std400\n\n# Транзакции\n\nbody B",
        encoding="utf-8",
    )
    await index_its_corpus(conn, client, root)

    # Кормим singleton тем же mock-клиентом, чтобы dispatch использовал
    # ту же модель что и индексер.
    set_embedding_client_for_testing(client)

    yield conn
    await conn.close()


# ---------- Schema ----------


def test_its_tool_schema_shape():
    assert ITS_TOOL_SCHEMA["type"] == "function"
    fn = ITS_TOOL_SCHEMA["function"]
    assert fn["name"] == SEARCH_ITS_TOOL_NAME == "search_its"
    assert "description" in fn
    params = fn["parameters"]
    assert params["type"] == "object"
    assert "query" in params["properties"]
    assert params["required"] == ["query"]
    assert params["properties"]["query"]["type"] == "string"
    assert params["properties"]["k"]["type"] == "integer"


def test_is_its_tool():
    assert is_its_tool("search_its")
    assert not is_its_tool("execute_query")
    assert not is_its_tool("clarify_question")
    assert not is_its_tool("")


# ---------- Settings flags ----------


def test_settings_is_its_ready_mock_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_ENABLED", "true")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    s = Settings()
    assert s.is_its_ready is True


def test_settings_is_its_ready_openai_no_key(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_ENABLED", "true")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("ITS_EMBEDDING_API_KEY", "")
    monkeypatch.setenv("DEFAULT_LLM_API_KEY_OPENAI", "")
    s = Settings()
    assert s.is_its_ready is False


def test_settings_is_its_ready_disabled(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_ENABLED", "false")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    s = Settings()
    assert s.is_its_ready is False


def test_settings_resolved_its_api_key_fallback(monkeypatch):
    """Если ITS_EMBEDDING_API_KEY пуст, фоллбэк на DEFAULT_LLM_API_KEY_OPENAI."""
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_API_KEY", "")
    monkeypatch.setenv("DEFAULT_LLM_API_KEY_OPENAI", "sk-fallback")
    s = Settings()
    assert s.resolved_its_api_key == "sk-fallback"


def test_settings_resolved_its_api_key_priority(monkeypatch):
    """Явный ITS_EMBEDDING_API_KEY побеждает fallback."""
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_API_KEY", "sk-explicit")
    monkeypatch.setenv("DEFAULT_LLM_API_KEY_OPENAI", "sk-fallback")
    s = Settings()
    assert s.resolved_its_api_key == "sk-explicit"


def test_is_its_enabled_uses_settings_flag(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_ENABLED", "true")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    s_yes = Settings()
    assert is_its_enabled(s_yes) is True

    monkeypatch.setenv("ITS_ENABLED", "false")
    s_no = Settings()
    assert is_its_enabled(s_no) is False


# ---------- _parse_args ----------


def test_parse_args_happy():
    query, k = _parse_args({"query": "hello", "k": 3})
    assert query == "hello"
    assert k == 3


def test_parse_args_default_k():
    query, k = _parse_args({"query": "hello"})
    assert query == "hello"
    assert k >= 1


def test_parse_args_caps_k():
    """k > _MAX_K округляется до _MAX_K, не raises."""
    _, k = _parse_args({"query": "hello", "k": 9999})
    assert k <= 20  # _MAX_K


def test_parse_args_missing_query():
    with pytest.raises(ValueError, match="query"):
        _parse_args({})


def test_parse_args_empty_query():
    with pytest.raises(ValueError, match="query"):
        _parse_args({"query": "   "})


def test_parse_args_non_string_query():
    with pytest.raises(ValueError, match="query"):
        _parse_args({"query": 42})


def test_parse_args_negative_k():
    with pytest.raises(ValueError, match="k"):
        _parse_args({"query": "x", "k": -1})


def test_parse_args_non_int_k():
    with pytest.raises(ValueError, match="k"):
        _parse_args({"query": "x", "k": "abc"})


def test_parse_args_not_a_dict():
    with pytest.raises(ValueError, match="args"):
        _parse_args("not a dict")  # type: ignore[arg-type]


# ---------- _build_embedding_client ----------


def test_build_mock_client(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("ITS_EMBEDDING_DIM", "8")
    s = Settings()
    client = _build_embedding_client(s)
    assert isinstance(client, MockEmbeddingClient)
    assert client.dim == 8


def test_build_openai_client(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("ITS_EMBEDDING_API_KEY", "sk-test")
    s = Settings()
    client = _build_embedding_client(s)
    assert isinstance(client, OpenAIEmbeddingClient)


def test_build_openai_client_no_key_raises(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("ITS_EMBEDDING_API_KEY", "")
    monkeypatch.setenv("DEFAULT_LLM_API_KEY_OPENAI", "")
    s = Settings()
    from app.knowledge.embeddings import EmbeddingError
    with pytest.raises(EmbeddingError, match="API key"):
        _build_embedding_client(s)


# ---------- Singleton ----------


@pytest.mark.asyncio
async def test_get_embedding_client_singleton(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("ITS_EMBEDDING_DIM", "4")
    s = Settings()
    c1 = await get_embedding_client(s)
    c2 = await get_embedding_client(s)
    assert c1 is c2


@pytest.mark.asyncio
async def test_reset_embedding_client_releases_singleton(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    s = Settings()
    c1 = await get_embedding_client(s)
    await reset_embedding_client()
    c2 = await get_embedding_client(s)
    assert c1 is not c2


# ---------- _format_results_for_llm ----------


def test_format_empty_returns_zero():
    out = _format_results_for_llm([])
    assert out == {"results": [], "total": 0}


def test_format_excludes_distance_field():
    hit = ITSSearchHit(
        doc_id="std396", chunk_index=0,
        title="Title", section_title="1.",
        content="body", category="std",
        source_path="std/396.md", distance=0.12,
    )
    out = _format_results_for_llm([hit])
    assert out["total"] == 1
    r = out["results"][0]
    assert "distance" not in r
    assert r["citation"].startswith("std396")
    assert r["content"] == "body"
    assert r["category"] == "std"


# ---------- dispatch_its_tool ----------


@pytest.mark.asyncio
async def test_dispatch_happy(db_indexed, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("ITS_EMBEDDING_DIM", str(TEST_DIM))
    s = Settings()

    ok, result, err = await dispatch_its_tool(
        db_indexed, s, "search_its", {"query": "что-то", "k": 2},
    )
    assert ok is True
    assert err is None
    assert isinstance(result, dict)
    assert "results" in result
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_dispatch_wrong_tool_name(db_indexed, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    s = Settings()
    ok, _, err = await dispatch_its_tool(db_indexed, s, "not_search_its", {})
    assert ok is False
    assert "Неизвестный" in err


@pytest.mark.asyncio
async def test_dispatch_invalid_args(db_indexed, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "mock")
    s = Settings()
    ok, _, err = await dispatch_its_tool(db_indexed, s, "search_its", {})
    assert ok is False
    assert "query" in err


@pytest.mark.asyncio
async def test_dispatch_no_api_key_returns_error(db_indexed, monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("ITS_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("ITS_EMBEDDING_API_KEY", "")
    monkeypatch.setenv("DEFAULT_LLM_API_KEY_OPENAI", "")
    s = Settings()

    # Снимаем mock client из singleton чтобы dispatch попытался построить новый
    set_embedding_client_for_testing(None)

    ok, _, err = await dispatch_its_tool(
        db_indexed, s, "search_its", {"query": "test"},
    )
    assert ok is False
    assert "ITS RAG" in err or "API key" in err


# ---------- its_index_ready (гейт по реальному наполнению индекса) ----------


async def test_its_index_ready_missing_empty_populated():
    """search_its не должен предлагаться модели, если индекс пуст/отсутствует —
    иначе бот «делает вид», что искал в ИТС (жалоба пользователя)."""
    import aiosqlite

    async with aiosqlite.connect(":memory:") as db:
        # таблицы нет → не готов (conservative)
        assert await its_index_ready(db) is False

        await db.execute(
            "CREATE TABLE its_chunks (doc_id TEXT, chunk_index INTEGER)"
        )
        await db.commit()
        # таблица есть, но пустая → не готов
        assert await its_index_ready(db) is False

        await db.execute(
            "INSERT INTO its_chunks (doc_id, chunk_index) VALUES ('d', 0)"
        )
        await db.commit()
        # есть данные → готов
        assert await its_index_ready(db) is True
