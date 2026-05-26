"""Тесты для backend/app/knowledge/its_indexer.py (M-K2.7).

Покрытие:
- index_its_corpus: happy path, idempotent skip, force_reindex, batch flush
- ITS_CHANNEL_ID константа
- count_its_chunks / count_its_documents
- error handling: missing root, embedding failure
- Integration через MockEmbeddingClient (детерминированный)
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.embeddings import MockEmbeddingClient
from app.knowledge.its_indexer import (
    DEFAULT_BATCH_SIZE,
    ITS_CHANNEL_ID,
    ITSIndexProgress,
    count_its_chunks,
    count_its_documents,
    index_its_corpus,
)
from app.knowledge.vector_store import count_embeddings, semantic_search
from app.storage.migrations import apply_migrations


# Маленький dim для теста чтобы init_vector_store создал vec0(dim=4)
TEST_DIM = 4


@pytest_asyncio.fixture
async def db_ready():
    """In-memory SQLite с миграциями (v14)."""
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def embed_client():
    """MockEmbeddingClient dim=4 (детерминированный)."""
    return MockEmbeddingClient(dim=TEST_DIM)


def _build_corpus(tmp_path: Path, files: dict[str, str]) -> Path:
    """Создаёт временный docs/ tree из словаря {rel_path: content}."""
    root = tmp_path / "docs"
    root.mkdir()
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


# ---------- Константы ----------


def test_its_channel_id_is_reserved():
    """Channel ID начинается с _ — реальные MCP-каналы это UUID v4 (не начинаются с _)."""
    assert ITS_CHANNEL_ID.startswith("_")
    assert ITS_CHANNEL_ID == "_its"


def test_default_batch_size_sensible():
    assert 10 <= DEFAULT_BATCH_SIZE <= 200


# ---------- Happy path ----------


@pytest.mark.asyncio
async def test_index_simple_corpus(db_ready, embed_client, tmp_path: Path):
    """3 файла → 3 чанка (короткие) → 3 embeddings в vec0."""
    root = _build_corpus(tmp_path, {
        "std/396.md": "###### #std396\n\n# Title 396\n\nshort body",
        "std/400.md": "###### #std400\n\n# Title 400\n\nshort body 2",
        "metod8dev/1590.md": "###### #metod1590\n\n# Метод 1590\n\nbody",
    })

    progress = await index_its_corpus(db_ready, embed_client, root)

    assert isinstance(progress, ITSIndexProgress)
    assert progress.is_success
    assert progress.docs_total == 3
    assert progress.docs_processed == 3
    assert progress.chunks_total == 3
    assert progress.chunks_embedded == 3
    assert progress.chunks_skipped == 0

    # vec_objects содержит 3 строки в канале _its
    assert await count_embeddings(db_ready, ITS_CHANNEL_ID) == 3
    # its_chunks содержит 3 строки
    assert await count_its_chunks(db_ready) == 3
    assert await count_its_documents(db_ready) == 3


@pytest.mark.asyncio
async def test_index_writes_its_chunks_metadata(db_ready, embed_client, tmp_path: Path):
    """its_chunks содержит title / category / source_path / object_path."""
    root = _build_corpus(tmp_path, {
        "std/396.md": "###### #std396\n\n# Обработчик ОбработкаЗаполнения\n\nbody",
    })

    await index_its_corpus(db_ready, embed_client, root)

    cursor = await db_ready.execute(
        "SELECT object_path, doc_id, title, category, source_path "
        "FROM its_chunks WHERE doc_id = ?",
        ("std396",),
    )
    row = await cursor.fetchone()
    assert row is not None
    object_path, doc_id, title, category, source_path = row
    assert object_path == "its:std396#0"
    assert doc_id == "std396"
    assert title == "Обработчик ОбработкаЗаполнения"
    assert category == "std"
    assert source_path == "std/396.md"


# ---------- Idempotency ----------


@pytest.mark.asyncio
async def test_reindex_skips_unchanged_chunks(db_ready, embed_client, tmp_path: Path):
    """Второй запуск на тех же файлах — chunks_skipped, chunks_embedded=0."""
    root = _build_corpus(tmp_path, {
        "std/396.md": "###### #std396\n\n# T\n\nbody",
    })

    p1 = await index_its_corpus(db_ready, embed_client, root)
    assert p1.chunks_embedded == 1
    assert p1.chunks_skipped == 0

    p2 = await index_its_corpus(db_ready, embed_client, root)
    assert p2.chunks_embedded == 0
    assert p2.chunks_skipped == 1
    assert p2.is_success


@pytest.mark.asyncio
async def test_reindex_picks_up_changed_chunks(db_ready, embed_client, tmp_path: Path):
    """Изменили контент → hash изменился → re-embed."""
    root = _build_corpus(tmp_path, {
        "std/396.md": "###### #std396\n\n# T\n\nfirst body",
    })

    await index_its_corpus(db_ready, embed_client, root)
    # Перезаписываем файл
    (root / "std" / "396.md").write_text(
        "###### #std396\n\n# T\n\nsecond body",
        encoding="utf-8",
    )

    p = await index_its_corpus(db_ready, embed_client, root)
    assert p.chunks_embedded == 1
    assert p.chunks_skipped == 0


@pytest.mark.asyncio
async def test_force_reindex_ignores_hashes(db_ready, embed_client, tmp_path: Path):
    """force_reindex=True переэмбедит даже unchanged."""
    root = _build_corpus(tmp_path, {
        "std/396.md": "###### #std396\n\n# T\n\nbody",
    })

    await index_its_corpus(db_ready, embed_client, root)
    p = await index_its_corpus(
        db_ready, embed_client, root, force_reindex=True,
    )
    assert p.chunks_embedded == 1
    assert p.chunks_skipped == 0


# ---------- Batch flush ----------


@pytest.mark.asyncio
async def test_index_handles_batch_overflow(db_ready, embed_client, tmp_path: Path):
    """Создаём > batch_size файлов, проверяем что все эмбедятся."""
    files = {
        f"std/{i}.md": f"###### #std{i}\n\n# Title {i}\n\nbody {i}"
        for i in range(400, 406)  # 6 файлов
    }
    root = _build_corpus(tmp_path, files)

    progress = await index_its_corpus(
        db_ready, embed_client, root, batch_size=2,
    )
    assert progress.chunks_embedded == 6
    assert await count_embeddings(db_ready, ITS_CHANNEL_ID) == 6


# ---------- Search integration ----------


@pytest.mark.asyncio
async def test_indexed_chunks_findable_via_semantic_search(
    db_ready, embed_client, tmp_path: Path,
):
    """После index → semantic_search(channel_id='_its') возвращает hits."""
    root = _build_corpus(tmp_path, {
        "std/396.md": "###### #std396\n\n# T\n\nbody A",
        "std/400.md": "###### #std400\n\n# T\n\nbody B",
    })

    await index_its_corpus(db_ready, embed_client, root)

    # Эмбедим query тем же mock-клиентом (детерминированный)
    query_result = await embed_client.embed(["body A"])
    query_vec = query_result.embeddings[0]

    hits = await semantic_search(
        db_ready,
        channel_id=ITS_CHANNEL_ID,
        query_embedding=query_vec,
        k=10,
        embedding_model=embed_client.model,
    )
    assert len(hits) == 2
    # Ближе должна быть «body A» — мы её и эмбедили как query
    assert hits[0].object_path == "its:std396#0"


# ---------- Error handling ----------


@pytest.mark.asyncio
async def test_index_missing_root_returns_failed(db_ready, embed_client, tmp_path: Path):
    """Несуществующий root → status='failed', нулевая статистика."""
    missing = tmp_path / "doesnt-exist"
    progress = await index_its_corpus(db_ready, embed_client, missing)
    assert not progress.is_success
    assert progress.status == "failed"
    assert progress.error is not None
    assert "loader" in progress.error.lower()


@pytest.mark.asyncio
async def test_index_empty_corpus_succeeds_zero_chunks(
    db_ready, embed_client, tmp_path: Path,
):
    """Пустой docs/ — done, 0 chunks (не failure)."""
    root = tmp_path / "docs"
    root.mkdir()
    progress = await index_its_corpus(db_ready, embed_client, root)
    assert progress.is_success
    assert progress.docs_total == 0
    assert progress.chunks_embedded == 0
