"""Тесты для backend/app/knowledge/its_search.py (M-K2.7).

Покрытие:
- search_its happy path: top-K, ordering by distance
- к 0 / пустой query → raise
- orphan vec_objects → skip + log
- ITSSearchHit.to_dict / to_citation
- empty index → empty result
- distance preserved (vec_hits.distance → ITSSearchHit.distance)
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.embeddings import EmbeddingError, MockEmbeddingClient
from app.knowledge.its_indexer import ITS_CHANNEL_ID, index_its_corpus
from app.knowledge.its_search import (
    DEFAULT_SEARCH_K,
    ITSSearchError,
    ITSSearchHit,
    search_its,
)
from app.knowledge.vector_store import upsert_embedding
from app.storage.migrations import apply_migrations

TEST_DIM = 4


@pytest_asyncio.fixture
async def db_indexed(tmp_path: Path):
    """In-memory DB с заэмбедженным тестовым корпусом из 3 std-документов."""
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
    (root / "patterns" / "engineering" / "dry").mkdir(parents=True)
    (root / "patterns" / "engineering" / "dry" / "index.md").write_text(
        "# DRY Principle\n\nbody C",
        encoding="utf-8",
    )

    await index_its_corpus(conn, client, root)

    yield conn, client
    await conn.close()


# ---------- search_its happy ----------


@pytest.mark.asyncio
async def test_search_returns_hits(db_indexed):
    db, client = db_indexed
    # MockEmbeddingClient — это hash. Семантической близости НЕТ.
    # Query произвольный, важно что возвращается весь корпус ≤ k.
    hits = await search_its(db, client, "any query text", k=3)
    assert len(hits) == 3
    assert all(isinstance(h, ITSSearchHit) for h in hits)
    # Все hits — из тестового корпуса
    doc_ids = {h.doc_id for h in hits}
    assert doc_ids == {"std396", "std400", "pattern-engineering-dry"}


@pytest.mark.asyncio
async def test_search_exact_match_is_closest(db_indexed):
    """Если query равен контенту чанка — он должен быть в результатах
    (через детерминированный hash MockEmbeddingClient)."""
    db, client = db_indexed
    # Берём фактический контент std396 из БД и query'им им же
    cursor = await db.execute(
        "SELECT content FROM its_chunks WHERE doc_id = 'std396'"
    )
    row = await cursor.fetchone()
    assert row is not None
    exact_content = row[0]

    hits = await search_its(db, client, exact_content, k=3)
    assert len(hits) >= 1
    # Ближайший — std396 (distance = 0 на точном совпадении hash)
    assert hits[0].doc_id == "std396"
    assert hits[0].distance < hits[-1].distance if len(hits) > 1 else True


@pytest.mark.asyncio
async def test_search_orders_by_distance(db_indexed):
    db, client = db_indexed
    hits = await search_its(db, client, "any query", k=3)
    # distances должны монотонно расти
    distances = [h.distance for h in hits]
    assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_search_default_k(db_indexed):
    db, client = db_indexed
    # k не указан → DEFAULT_SEARCH_K (но в корпусе только 3)
    hits = await search_its(db, client, "anything")
    assert len(hits) == 3  # corpus has 3, default_k=5 → берём всё что есть
    assert DEFAULT_SEARCH_K >= 3


@pytest.mark.asyncio
async def test_search_respects_k(db_indexed):
    db, client = db_indexed
    hits = await search_its(db, client, "anything", k=1)
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_search_preserves_section_title_when_present(db_indexed, tmp_path: Path):
    # Стандартный fixture не даёт чанков с section_title — все короткие.
    # Дополнительно загружаем длинный документ с подсекциями.
    db, client = db_indexed
    # Документ с numbered subsections
    multi = (
        "###### #std500\n\n# Длинный стандарт\n\n"
        "###### 1.\n\nЧасть один\n\n"
        "###### 2.\n\nЧасть два"
    )
    root = tmp_path / "docs2"
    (root / "std").mkdir(parents=True)
    (root / "std" / "500.md").write_text(multi, encoding="utf-8")
    # Перестроим корпус (только новый файл)
    await index_its_corpus(db, client, root)

    hits = await search_its(db, client, "Часть", k=10)
    # Найдём std500 в результатах
    paths = {h.doc_id for h in hits}
    assert "std500" in paths


# ---------- Validation ----------


@pytest.mark.asyncio
async def test_search_empty_query_raises(db_indexed):
    db, client = db_indexed
    with pytest.raises(ITSSearchError, match="пустой"):
        await search_its(db, client, "")
    with pytest.raises(ITSSearchError):
        await search_its(db, client, "   ")


@pytest.mark.asyncio
async def test_search_invalid_k_raises(db_indexed):
    db, client = db_indexed
    with pytest.raises(ITSSearchError, match=r"k должен быть > 0"):
        await search_its(db, client, "query", k=0)
    with pytest.raises(ITSSearchError):
        await search_its(db, client, "query", k=-1)


# ---------- Empty index ----------


@pytest.mark.asyncio
async def test_search_empty_index_returns_empty():
    """Когда vec0 пустой — search должен вернуть [], не падать."""
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        client = MockEmbeddingClient(dim=TEST_DIM)
        # init_vector_store должен быть вызван до search'а (обычно индексер
        # это делает). Эмулируем — index пустой корпус.
        from app.knowledge.vector_store import init_vector_store
        await init_vector_store(conn, dim=TEST_DIM)

        hits = await search_its(conn, client, "anything", k=5)
        assert hits == []
    finally:
        await conn.close()


# ---------- Orphan handling ----------


@pytest.mark.asyncio
async def test_search_skips_orphan_vec_objects():
    """vec_objects содержит запись, для которой нет its_chunks — должен skip."""
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        client = MockEmbeddingClient(dim=TEST_DIM)
        from app.knowledge.vector_store import init_vector_store
        await init_vector_store(conn, dim=TEST_DIM)

        # Эмбеддим напрямую в vec_objects без записи в its_chunks
        await upsert_embedding(
            conn,
            channel_id=ITS_CHANNEL_ID,
            object_path="its:orphan#0",
            embedding=[1.0, 0.0, 0.0, 0.0],
            embedding_model=client.model,
        )

        hits = await search_its(conn, client, "query", k=5)
        # Orphan был один — после skip результатов 0
        assert hits == []
    finally:
        await conn.close()


# ---------- ITSSearchHit serialization ----------


def test_hit_to_dict_has_all_fields():
    hit = ITSSearchHit(
        doc_id="std396",
        chunk_index=2,
        title="Title",
        section_title="Section 1",
        content="content body",
        category="std",
        source_path="std/396.md",
        distance=0.12,
    )
    d = hit.to_dict()
    assert d == {
        "doc_id": "std396",
        "chunk_index": 2,
        "title": "Title",
        "section_title": "Section 1",
        "content": "content body",
        "category": "std",
        "source_path": "std/396.md",
        "distance": 0.12,
    }


def test_hit_to_citation_with_section():
    hit = ITSSearchHit(
        doc_id="std396", chunk_index=0, title="Обработчик ОбработкаЗаполнения",
        section_title="1.", content="", category="std",
        source_path="std/396.md", distance=0.0,
    )
    cite = hit.to_citation()
    assert "std396" in cite
    assert "Обработчик" in cite
    assert "1." in cite


def test_hit_to_citation_without_section():
    hit = ITSSearchHit(
        doc_id="std400", chunk_index=0, title="Транзакции",
        section_title=None, content="", category="std",
        source_path="std/400.md", distance=0.0,
    )
    cite = hit.to_citation()
    assert "std400" in cite
    assert "Транзакции" in cite
    assert "раздел" not in cite


def test_hit_object_path_format():
    hit = ITSSearchHit(
        doc_id="std400", chunk_index=3, title="t",
        section_title=None, content="", category="std",
        source_path="x", distance=0.0,
    )
    assert hit.object_path == "its:std400#3"


# ---------- M-K4 hybrid: BM25 + RRF + key-free fallback ----------


class _FailingEmbeddingClient:
    """Эмулирует отсутствие embedding-ключа: embed() всегда падает."""

    model = "failing"
    dim = TEST_DIM

    async def embed(self, texts):  # noqa: ARG002
        raise EmbeddingError("no embedding key")

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_search_falls_back_to_bm25_without_embedding(db_indexed):
    """Без рабочего embedding (нет ключа) поиск деградирует на BM25 и всё равно
    находит по ключевому слову — корпус уже проиндексирован (FTS populated)."""
    db, _ = db_indexed
    failing = _FailingEmbeddingClient()
    hits = await search_its(db, failing, "Транзакции", k=5)
    assert hits, "BM25 fallback должен вернуть результаты без embedding"
    assert any(h.doc_id == "std400" for h in hits)
    # BM25-only находки помечены sentinel-distance (вектора нет)
    assert all(h.distance == 1.0 for h in hits)


@pytest.mark.asyncio
async def test_search_bm25_surfaces_exact_term(db_indexed):
    """BM25-слой находит документ по точному термину (hybrid: vector ⊕ BM25)."""
    db, client = db_indexed
    hits = await search_its(db, client, "Транзакции", k=3)
    assert any(h.doc_id == "std400" for h in hits)


@pytest.mark.asyncio
async def test_search_bm25_only_index_without_vectors():
    """its_chunks заполнен (FTS через триггер), но vec_objects пуст —
    поиск работает на одном BM25, без векторов."""
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        from app.knowledge.vector_store import init_vector_store
        await init_vector_store(conn, dim=TEST_DIM)  # vec пуст
        await conn.execute(
            "INSERT INTO its_chunks(object_path,doc_id,chunk_index,title,section_title,"
            "content,category,source_path,char_count,chunk_hash) "
            "VALUES('its:std999#0','std999',0,'Блокировки',NULL,"
            "'Управляемые блокировки данных при проведении','std','std/999.md',10,'h1')"
        )
        await conn.commit()
        client = MockEmbeddingClient(dim=TEST_DIM)
        hits = await search_its(conn, client, "блокировки", k=5)
        assert len(hits) == 1
        assert hits[0].doc_id == "std999"
        assert hits[0].distance == 1.0  # BM25-only sentinel
    finally:
        await conn.close()
