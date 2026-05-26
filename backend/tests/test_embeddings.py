"""Tests for backend/app/knowledge/embeddings.py (M-K2.6).

Покрытие:
- MockEmbeddingClient: детерминированность, dim validation, L2 norm
- OpenAIEmbeddingClient: API call, payload shape, error handling
- EmbeddingError handling
- aclose() lifecycle
"""

from __future__ import annotations

import json
import math
from typing import Any

import httpx
import pytest

from app.knowledge.embeddings import (
    EmbeddingError,
    EmbeddingResult,
    MockEmbeddingClient,
    OpenAIEmbeddingClient,
)


# ---------- MockEmbeddingClient ----------


@pytest.mark.asyncio
async def test_mock_embeds_single_text():
    client = MockEmbeddingClient(dim=8)
    result = await client.embed(["hello"])
    assert isinstance(result, EmbeddingResult)
    assert len(result) == 1
    assert len(result.embeddings[0]) == 8
    assert result.dim == 8
    assert result.model == "mock-deterministic"


@pytest.mark.asyncio
async def test_mock_embeds_batch():
    client = MockEmbeddingClient(dim=4)
    result = await client.embed(["foo", "bar", "baz"])
    assert len(result) == 3
    assert all(len(emb) == 4 for emb in result.embeddings)


@pytest.mark.asyncio
async def test_mock_is_deterministic():
    """Одинаковый текст → одинаковый вектор (всегда)."""
    client = MockEmbeddingClient(dim=8)
    r1 = await client.embed(["consistent"])
    r2 = await client.embed(["consistent"])
    assert r1.embeddings == r2.embeddings


@pytest.mark.asyncio
async def test_mock_different_texts_produce_different_vectors():
    client = MockEmbeddingClient(dim=16)
    r = await client.embed(["alpha", "beta"])
    assert r.embeddings[0] != r.embeddings[1]


@pytest.mark.asyncio
async def test_mock_vectors_are_l2_normalized():
    """L2 norm каждого вектора ≈ 1.0 (для cosine-friendly distance)."""
    client = MockEmbeddingClient(dim=32)
    r = await client.embed(["normalize me"])
    norm = math.sqrt(sum(v * v for v in r.embeddings[0]))
    assert abs(norm - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_mock_empty_input_raises():
    client = MockEmbeddingClient(dim=4)
    with pytest.raises(EmbeddingError, match="texts пустой"):
        await client.embed([])


def test_mock_dim_must_be_positive():
    with pytest.raises(EmbeddingError, match=r"dim должен быть > 0"):
        MockEmbeddingClient(dim=0)
    with pytest.raises(EmbeddingError):
        MockEmbeddingClient(dim=-5)


@pytest.mark.asyncio
async def test_mock_aclose_is_noop():
    client = MockEmbeddingClient(dim=4)
    await client.aclose()  # no-op, не должен падать


# ---------- OpenAIEmbeddingClient ----------


def test_openai_requires_api_key():
    with pytest.raises(EmbeddingError, match="api_key обязателен"):
        OpenAIEmbeddingClient(api_key="")


def test_openai_dim_validation():
    with pytest.raises(EmbeddingError):
        OpenAIEmbeddingClient(api_key="sk-test", dim=0)


@pytest.mark.asyncio
async def test_openai_embed_happy_path(monkeypatch):
    """Mock httpx — возвращаем валидный OpenAI-style response."""

    captured_payload: dict[str, Any] = {}

    async def fake_post(self, url, **kwargs):  # noqa: ARG001
        captured_payload["url"] = url
        captured_payload["json"] = kwargs.get("json")
        captured_payload["headers"] = kwargs.get("headers")
        return httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": [0.1, 0.2, 0.3, 0.4]},
                    {"embedding": [0.5, 0.6, 0.7, 0.8]},
                ],
                "model": "text-embedding-3-small",
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = OpenAIEmbeddingClient(
        endpoint="https://api.openai.com/v1",
        api_key="sk-test",
        model="text-embedding-3-small",
        dim=4,
    )
    try:
        result = await client.embed(["foo", "bar"])
    finally:
        await client.aclose()

    assert len(result) == 2
    assert result.embeddings[0] == [0.1, 0.2, 0.3, 0.4]
    assert result.dim == 4
    assert result.model == "text-embedding-3-small"

    # Проверка URL + payload + auth
    assert captured_payload["url"].endswith("/embeddings")
    assert captured_payload["headers"]["Authorization"] == "Bearer sk-test"
    assert captured_payload["json"]["model"] == "text-embedding-3-small"
    assert captured_payload["json"]["input"] == ["foo", "bar"]
    # Кастомный dim != 1536 → должен идти параметр dimensions
    assert captured_payload["json"].get("dimensions") == 4


@pytest.mark.asyncio
async def test_openai_uses_default_dim_without_dimensions_param(monkeypatch):
    """При dim == OPENAI_DEFAULT_DIM (1536) НЕ должны слать `dimensions`."""

    captured_payload: dict[str, Any] = {}

    async def fake_post(self, url, **kwargs):  # noqa: ARG001
        captured_payload["json"] = kwargs.get("json")
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.0] * 1536}], "model": "text-embedding-3-small"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = OpenAIEmbeddingClient(api_key="sk-test")
    try:
        await client.embed(["x"])
    finally:
        await client.aclose()

    assert "dimensions" not in captured_payload["json"]


@pytest.mark.asyncio
async def test_openai_embed_empty_raises():
    client = OpenAIEmbeddingClient(api_key="sk-test")
    try:
        with pytest.raises(EmbeddingError, match="texts пустой"):
            await client.embed([])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_openai_handles_4xx_response(monkeypatch):
    async def fake_post(self, url, **kwargs):  # noqa: ARG001
        return httpx.Response(
            401,
            content=b'{"error":"invalid_api_key"}',
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = OpenAIEmbeddingClient(api_key="sk-bad")
    try:
        with pytest.raises(EmbeddingError, match="401"):
            await client.embed(["x"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_openai_handles_network_error(monkeypatch):
    async def fake_post(self, url, **kwargs):  # noqa: ARG001
        raise httpx.ConnectError("DNS failure")

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = OpenAIEmbeddingClient(api_key="sk-test")
    try:
        with pytest.raises(EmbeddingError, match="Сетевая ошибка"):
            await client.embed(["x"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_openai_handles_malformed_response(monkeypatch):
    async def fake_post(self, url, **kwargs):  # noqa: ARG001
        # Response без поля "data"
        return httpx.Response(
            200,
            json={"foo": "bar"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = OpenAIEmbeddingClient(api_key="sk-test")
    try:
        with pytest.raises(EmbeddingError, match="ожидалось data"):
            await client.embed(["x"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_openai_handles_invalid_json_response(monkeypatch):
    async def fake_post(self, url, **kwargs):  # noqa: ARG001
        return httpx.Response(
            200,
            content=b"not a json",
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = OpenAIEmbeddingClient(api_key="sk-test")
    try:
        with pytest.raises(EmbeddingError, match="JSON"):
            await client.embed(["x"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_openai_strips_endpoint_trailing_slash():
    client = OpenAIEmbeddingClient(
        endpoint="https://api.openai.com/v1/",
        api_key="sk-test",
    )
    try:
        # Внутри сохранился без trailing slash
        assert client._endpoint == "https://api.openai.com/v1"  # type: ignore[attr-defined]
    finally:
        await client.aclose()


# ---------- Integration: Mock client + vector_store ----------


@pytest.mark.asyncio
async def test_mock_embeddings_work_with_vector_store(tmp_path):
    """End-to-end: MockEmbeddingClient → upsert → semantic_search.

    Без реальных API-вызовов, проверяет совместимость типов и форматов.
    """
    import aiosqlite

    from app.knowledge.vector_store import (
        init_vector_store,
        semantic_search,
        upsert_embedding,
    )
    from app.storage.migrations import apply_migrations

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await apply_migrations(db)
        await init_vector_store(db, dim=8)

        embed_client = MockEmbeddingClient(dim=8)
        try:
            texts = ["Документ ОПП", "Контрагенты справочник", "Регистр остатков"]
            result = await embed_client.embed(texts)

            for path, emb in zip(["Документ.ОПП", "Справочник.К", "Регистр.О"], result.embeddings):
                await upsert_embedding(
                    db,
                    channel_id="ch-1",
                    object_path=path,
                    embedding=emb,
                    embedding_model="mock-deterministic",
                )

            # Поиск по тому же тексту должен найти исходный документ first
            query_result = await embed_client.embed(["Документ ОПП"])
            hits = await semantic_search(
                db,
                channel_id="ch-1",
                query_embedding=query_result.embeddings[0],
                k=3,
                embedding_model="mock-deterministic",
            )
            assert len(hits) == 3
            assert hits[0].object_path == "Документ.ОПП"
            assert hits[0].distance < hits[1].distance
        finally:
            await embed_client.aclose()
