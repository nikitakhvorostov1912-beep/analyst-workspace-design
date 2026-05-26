"""Tests for backend/app/knowledge/vector_store.py (M-K2.5).

Покрытие:
- Migration v13: vec_objects table + индексы + UNIQUE constraint
- load_sqlite_vec: idempotent, vec_version() работает
- init_vector_store: создаёт vec0 table, idempotent, валидирует dim
- upsert_embedding: insert / update / dim mismatch
- semantic_search: top-K, channel isolation, k validation
- delete_channel_embeddings: cascade удаление
- count_embeddings: filtering
"""

from __future__ import annotations

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.vector_store import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL,
    VectorStoreError,
    count_embeddings,
    delete_channel_embeddings,
    init_vector_store,
    load_sqlite_vec,
    semantic_search,
    upsert_embedding,
)
from app.storage.migrations import apply_migrations


# Маленькая размерность для тестов чтобы не тратить память на нули.
TEST_DIM = 4


@pytest_asyncio.fixture
async def db_vec():
    """In-memory SQLite с миграциями + загруженным sqlite-vec + созданной
    vec0 таблицей dim=4."""
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await init_vector_store(conn, dim=TEST_DIM)
        yield conn
    finally:
        await conn.close()


# ---------- Migration v13 ----------


@pytest.mark.asyncio
async def test_migration_v13_creates_vec_objects_table():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vec_objects'"
        )
        row = await cursor.fetchone()
        assert row is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v13_unique_constraint():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await conn.execute(
            "INSERT INTO vec_objects (channel_id, object_path, embedding_model, embedding_dim) "
            "VALUES ('ch-1', 'Документ.A', 'bge-m3', 1024)"
        )
        await conn.commit()

        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO vec_objects (channel_id, object_path, embedding_model, embedding_dim) "
                "VALUES ('ch-1', 'Документ.A', 'bge-m3', 1024)"
            )
            await conn.commit()
    finally:
        await conn.close()


# ---------- load_sqlite_vec / init_vector_store ----------


@pytest.mark.asyncio
async def test_load_sqlite_vec_makes_vec_version_available():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await load_sqlite_vec(conn)
        cursor = await conn.execute("SELECT vec_version()")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0].startswith("v0.")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_init_vector_store_idempotent(db_vec):
    # db_vec уже инициализирована — повторный вызов не должен падать
    await init_vector_store(db_vec, dim=TEST_DIM)
    # Проверим что vec0 table присутствует
    cursor = await db_vec.execute(
        "SELECT name FROM sqlite_master WHERE name='vec_objects_embeddings'"
    )
    row = await cursor.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_init_vector_store_rejects_invalid_dim():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        with pytest.raises(VectorStoreError, match=r"dim должен быть > 0"):
            await init_vector_store(conn, dim=0)
        with pytest.raises(VectorStoreError):
            await init_vector_store(conn, dim=-1)
    finally:
        await conn.close()


# ---------- upsert_embedding ----------


@pytest.mark.asyncio
async def test_upsert_embedding_inserts_new(db_vec):
    rowid = await upsert_embedding(
        db_vec,
        channel_id="ch-1",
        object_path="Документ.ОПП",
        embedding=[0.1, 0.2, 0.3, 0.4],
    )
    assert rowid > 0

    cursor = await db_vec.execute(
        "SELECT channel_id, object_path, embedding_model, embedding_dim "
        "FROM vec_objects WHERE id = ?",
        (rowid,),
    )
    row = await cursor.fetchone()
    assert row == ("ch-1", "Документ.ОПП", DEFAULT_EMBEDDING_MODEL, TEST_DIM)


@pytest.mark.asyncio
async def test_upsert_embedding_updates_existing(db_vec):
    rowid1 = await upsert_embedding(
        db_vec,
        channel_id="ch-1",
        object_path="Документ.ОПП",
        embedding=[0.1, 0.2, 0.3, 0.4],
    )
    rowid2 = await upsert_embedding(
        db_vec,
        channel_id="ch-1",
        object_path="Документ.ОПП",
        embedding=[0.9, 0.9, 0.9, 0.9],
    )
    assert rowid2 != rowid1  # после DELETE+INSERT новый id

    # В таблице должна остаться одна запись для этого пути
    assert await count_embeddings(db_vec, "ch-1") == 1


@pytest.mark.asyncio
async def test_upsert_embedding_empty_raises(db_vec):
    with pytest.raises(VectorStoreError, match="embedding пустой"):
        await upsert_embedding(
            db_vec,
            channel_id="ch-1",
            object_path="Документ.X",
            embedding=[],
        )


@pytest.mark.asyncio
async def test_upsert_embedding_dim_mismatch_raises(db_vec):
    # vec0 создана с dim=4 — embedding длины 3 должен падать
    with pytest.raises(VectorStoreError, match="dim mismatch"):
        await upsert_embedding(
            db_vec,
            channel_id="ch-1",
            object_path="Документ.X",
            embedding=[0.1, 0.2, 0.3],
        )


# ---------- semantic_search ----------


@pytest.mark.asyncio
async def test_semantic_search_returns_topk(db_vec):
    # Заполняем 3 объекта с известными векторами
    await upsert_embedding(
        db_vec, channel_id="ch-1", object_path="A",
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    await upsert_embedding(
        db_vec, channel_id="ch-1", object_path="B",
        embedding=[0.0, 1.0, 0.0, 0.0],
    )
    await upsert_embedding(
        db_vec, channel_id="ch-1", object_path="C",
        embedding=[0.0, 0.0, 1.0, 0.0],
    )

    hits = await semantic_search(
        db_vec,
        channel_id="ch-1",
        query_embedding=[1.0, 0.0, 0.0, 0.0],
        k=2,
    )
    assert len(hits) == 2
    assert hits[0].object_path == "A"
    assert hits[0].distance < hits[1].distance


@pytest.mark.asyncio
async def test_semantic_search_isolates_channels(db_vec):
    await upsert_embedding(
        db_vec, channel_id="ch-A", object_path="X",
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    await upsert_embedding(
        db_vec, channel_id="ch-B", object_path="Y",
        embedding=[1.0, 0.0, 0.0, 0.0],
    )

    hits_a = await semantic_search(
        db_vec, channel_id="ch-A",
        query_embedding=[1.0, 0.0, 0.0, 0.0], k=10,
    )
    assert len(hits_a) == 1
    assert hits_a[0].object_path == "X"

    hits_b = await semantic_search(
        db_vec, channel_id="ch-B",
        query_embedding=[1.0, 0.0, 0.0, 0.0], k=10,
    )
    assert len(hits_b) == 1
    assert hits_b[0].object_path == "Y"


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_for_unknown_channel(db_vec):
    await upsert_embedding(
        db_vec, channel_id="ch-real", object_path="X",
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    hits = await semantic_search(
        db_vec, channel_id="ch-ghost",
        query_embedding=[1.0, 0.0, 0.0, 0.0], k=10,
    )
    assert hits == []


@pytest.mark.asyncio
async def test_semantic_search_validates_k(db_vec):
    with pytest.raises(VectorStoreError, match=r"k должен быть > 0"):
        await semantic_search(
            db_vec, channel_id="ch-1",
            query_embedding=[1.0, 0.0, 0.0, 0.0], k=0,
        )


@pytest.mark.asyncio
async def test_semantic_search_empty_query_raises(db_vec):
    with pytest.raises(VectorStoreError, match="query_embedding пустой"):
        await semantic_search(
            db_vec, channel_id="ch-1",
            query_embedding=[], k=5,
        )


# ---------- delete_channel_embeddings ----------


@pytest.mark.asyncio
async def test_delete_channel_embeddings_removes_all_for_channel(db_vec):
    await upsert_embedding(
        db_vec, channel_id="ch-A", object_path="X",
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    await upsert_embedding(
        db_vec, channel_id="ch-A", object_path="Y",
        embedding=[0.0, 1.0, 0.0, 0.0],
    )
    await upsert_embedding(
        db_vec, channel_id="ch-B", object_path="Z",
        embedding=[0.0, 0.0, 1.0, 0.0],
    )

    deleted = await delete_channel_embeddings(db_vec, "ch-A")
    assert deleted == 2
    assert await count_embeddings(db_vec, "ch-A") == 0
    assert await count_embeddings(db_vec, "ch-B") == 1


@pytest.mark.asyncio
async def test_delete_channel_embeddings_unknown_returns_zero(db_vec):
    deleted = await delete_channel_embeddings(db_vec, "ch-ghost")
    assert deleted == 0


# ---------- count_embeddings ----------


@pytest.mark.asyncio
async def test_count_embeddings_total_and_per_channel(db_vec):
    await upsert_embedding(
        db_vec, channel_id="ch-A", object_path="X",
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    await upsert_embedding(
        db_vec, channel_id="ch-B", object_path="Y",
        embedding=[0.0, 1.0, 0.0, 0.0],
    )

    assert await count_embeddings(db_vec) == 2
    assert await count_embeddings(db_vec, "ch-A") == 1
    assert await count_embeddings(db_vec, "ch-B") == 1
    assert await count_embeddings(db_vec, "ch-Z") == 0


@pytest.mark.asyncio
async def test_default_embedding_dim_is_bge_m3(db_vec):
    """BGE-M3 имеет 1024 dimensions — это дефолт в PLAN.md."""
    assert DEFAULT_EMBEDDING_DIM == 1024
    assert DEFAULT_EMBEDDING_MODEL == "BAAI/bge-m3"
