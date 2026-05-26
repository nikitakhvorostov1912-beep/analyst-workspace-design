"""Vector Store — sqlite-vec backed local embedding storage (M-K2.5).

Слой L3 Knowledge Layer: семантический поиск по metadata snapshots /
ИТС / БСП. Используется через `semantic_search(channel_id, query, k)`.

**Архитектура:**
- `vec_objects` (миграция v13) — backing table с metadata: channel_id,
  object_path, embedding_model, embedding_dim, created_at. id используется
  как rowid в vec0 virtual table.
- `vec_objects_embeddings` (vec0 virtual table) — создаётся динамически
  в `init_vector_store()` через `sqlite_vec.load(conn)` + DDL. Хранит
  только float32 embedding на каждый rowid.
- JOIN: `vec_objects_embeddings.rowid = vec_objects.id`.

**Почему vec0 динамически:**
- vec0 — это extension table type, его DDL зависит от загруженного
  расширения. Стандартная миграция не может его создать (`vec0`
  неизвестен SQLite до `sqlite_vec.load()`).
- Решение: миграция v13 даёт только backing-таблицу, vec0 создаётся
  при первом вызове `init_vector_store()` (idempotent).

**Embedding модель:**
- Дефолт `BAAI/bge-m3` (1024-D) через FastEmbed (M-K2.6).
- Альтернатива `openai/text-embedding-3-small` (1536-D).
- Размерность хранится per-row в `vec_objects.embedding_dim` — но vec0
  table создаётся под фиксированный dim. Смена модели = новая vec0
  table (или таблица с разными моделями требует разделения).

**Что НЕ делает M-K2.5:**
- Не интегрируется в semantic_search endpoint (это M-K3 hybrid retrieval).
- Не делает chunking текстов на части (single embedding per object).
- Не оптимизирует под миллионы векторов (vec0 brute-force до ~100k OK,
  для бóльшего нужны HNSW индексы — план B в `M-K2-PLAN.md` R-MK2-03).

**Зависимость:** `sqlite-vec>=0.1.9` (в pyproject.toml). Extension
загружается через `enable_load_extension(True)` + `sqlite_vec.load(conn)`.
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import Sequence

import aiosqlite

logger = logging.getLogger(__name__)


# Дефолтная размерность embedding'а — BGE-M3.
# Меняется через init_vector_store(dim=...). vec0 таблица создаётся под
# одну фиксированную размерность.
DEFAULT_EMBEDDING_DIM = 1024
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"


class VectorStoreError(Exception):
    """Базовая ошибка vector store — extension не загружен, dim mismatch, etc."""


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    """Один результат semantic search.

    Attrs:
        rowid: внутренний vec_objects.id (для debug / load_more pagination)
        channel_id: канал, который владеет объектом
        object_path: «Документ.ОПП»
        distance: cosine distance (0 = совпадение, ∞ = противоположны).
                  vec0 возвращает L2 squared distance по умолчанию — для
                  cosine добавим нормализацию векторов перед insert.
        embedding_model: модель использованная для эмбеддинга
    """

    rowid: int
    channel_id: str
    object_path: str
    distance: float
    embedding_model: str


def _embedding_to_bytes(embedding: Sequence[float]) -> bytes:
    """Сериализует float[] → bytes(little-endian float32) для vec0 INSERT.

    sqlite-vec ожидает packed binary `BLOB` of float32 values. NumPy
    тут не используется — minimal deps.
    """
    if not embedding:
        raise VectorStoreError("Embedding пустой")
    return struct.pack(f"<{len(embedding)}f", *embedding)


def _load_sqlite_vec_sync(raw_conn) -> None:
    """Синхронно загружает sqlite-vec расширение в raw sqlite3 connection.

    aiosqlite не имеет нативного `enable_load_extension`, нужно идти через
    `_connection` низкоуровневое. Вызывается из `init_vector_store`.
    """
    try:
        import sqlite_vec  # type: ignore[import-untyped]
    except ImportError as exc:
        raise VectorStoreError(
            "sqlite-vec пакет не установлен. "
            "Установите: pip install sqlite-vec>=0.1.9"
        ) from exc

    raw_conn.enable_load_extension(True)
    try:
        sqlite_vec.load(raw_conn)
    finally:
        raw_conn.enable_load_extension(False)


async def load_sqlite_vec(db: aiosqlite.Connection) -> None:
    """Загружает sqlite-vec в текущую aiosqlite connection.

    Идемпотентно — повторный вызов не делает ничего нового (sqlite-vec
    регистрирует функции / virtual table types один раз).

    Использует низкоуровневый `db._conn` чтобы вызвать
    `enable_load_extension`, который aiosqlite не expose напрямую.
    Это безопасно — стабильный atribute в aiosqlite 0.17+.
    """
    raw_conn = getattr(db, "_conn", None)
    if raw_conn is None:
        raise VectorStoreError(
            "Не могу достать raw sqlite3 connection из aiosqlite — "
            "несовместимая версия aiosqlite"
        )
    # aiosqlite._conn — это sqlite3.Connection в worker thread.
    # Вызываем через executor чтобы не блокировать event loop.
    await db._execute(_load_sqlite_vec_sync, raw_conn)


async def init_vector_store(
    db: aiosqlite.Connection,
    *,
    dim: int = DEFAULT_EMBEDDING_DIM,
) -> None:
    """Создаёт vec0 virtual table если её нет.

    Идемпотентно: `CREATE VIRTUAL TABLE IF NOT EXISTS` — повторный вызов
    no-op.

    Args:
        db: aiosqlite connection
        dim: размерность embedding'а (default 1024 для BGE-M3)

    Raises:
        VectorStoreError если sqlite-vec не загружается или DDL падает.
    """
    if dim <= 0:
        raise VectorStoreError(f"dim должен быть > 0, получено {dim}")

    await load_sqlite_vec(db)
    try:
        await db.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_objects_embeddings
            USING vec0(embedding FLOAT[{dim}])
            """
        )
        await db.commit()
    except aiosqlite.Error as exc:
        raise VectorStoreError(
            f"Не удалось создать vec_objects_embeddings (dim={dim}): {exc}"
        ) from exc


async def upsert_embedding(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    object_path: str,
    embedding: Sequence[float],
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> int:
    """Записывает / обновляет один embedding.

    Возвращает rowid из `vec_objects` (он же rowid в vec0). При повторном
    вызове с тем же (channel_id, object_path, embedding_model) — обновляет
    embedding (DELETE + INSERT — vec0 не поддерживает UPDATE через MATCH).

    Args:
        db: aiosqlite connection (требует init_vector_store вызванного ранее)
        channel_id: канал-владелец
        object_path: «Документ.ОПП»
        embedding: list[float] длиной = dim из init_vector_store
        embedding_model: имя модели (для multi-model каналов в будущем)

    Returns:
        rowid в vec_objects.

    Raises:
        VectorStoreError при пустом embedding'е или ошибке записи.
    """
    if not embedding:
        raise VectorStoreError("embedding пустой")

    dim = len(embedding)
    blob = _embedding_to_bytes(embedding)

    # 1. Удаляем старую запись (если есть) — UNIQUE constraint обеспечит
    #    что после INSERT мы получим единственную row для (channel, path, model).
    cursor = await db.execute(
        """
        SELECT id FROM vec_objects
        WHERE channel_id = ? AND object_path = ? AND embedding_model = ?
        """,
        (channel_id, object_path, embedding_model),
    )
    existing = await cursor.fetchone()
    if existing is not None:
        old_id = existing[0]
        await db.execute("DELETE FROM vec_objects_embeddings WHERE rowid = ?", (old_id,))
        await db.execute("DELETE FROM vec_objects WHERE id = ?", (old_id,))

    # 2. Insert metadata first to get rowid
    cursor = await db.execute(
        """
        INSERT INTO vec_objects (channel_id, object_path, embedding_model, embedding_dim)
        VALUES (?, ?, ?, ?)
        """,
        (channel_id, object_path, embedding_model, dim),
    )
    rowid = cursor.lastrowid
    if rowid is None:
        await db.rollback()
        raise VectorStoreError("Не удалось получить rowid после INSERT vec_objects")

    # 3. Insert embedding в vec0 с тем же rowid
    try:
        await db.execute(
            "INSERT INTO vec_objects_embeddings(rowid, embedding) VALUES (?, ?)",
            (rowid, blob),
        )
    except aiosqlite.Error as exc:
        await db.rollback()
        raise VectorStoreError(
            f"vec0 INSERT failed (вероятно dim mismatch: ожидался "
            f"созданный init_vector_store dim, получен {dim}): {exc}"
        ) from exc

    await db.commit()
    return rowid


async def semantic_search(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    query_embedding: Sequence[float],
    k: int = 10,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> list[VectorSearchHit]:
    """Top-K similarity search в рамках одного канала.

    Args:
        db: aiosqlite connection с загруженным sqlite-vec
        channel_id: фильтрует результаты только этим каналом
        query_embedding: запрос-вектор размерности vec0 dim
        k: сколько top-результатов вернуть (default 10)
        embedding_model: матчить только embeddings от этой модели

    Returns:
        list[VectorSearchHit] отсортированный по distance ASC.

    Raises:
        VectorStoreError при пустом query или ошибке поиска.
    """
    if not query_embedding:
        raise VectorStoreError("query_embedding пустой")
    if k <= 0:
        raise VectorStoreError(f"k должен быть > 0, получено {k}")

    blob = _embedding_to_bytes(query_embedding)

    # vec0 синтаксис: MATCH + k = N + ORDER BY distance.
    # vec0 возвращает special column `distance` в SELECT — JOIN с
    # vec_objects по rowid даёт метаданные.
    try:
        cursor = await db.execute(
            """
            SELECT ve.rowid, vo.channel_id, vo.object_path, ve.distance, vo.embedding_model
            FROM vec_objects_embeddings ve
            JOIN vec_objects vo ON vo.id = ve.rowid
            WHERE ve.embedding MATCH ?
              AND vo.channel_id = ?
              AND vo.embedding_model = ?
              AND ve.k = ?
            ORDER BY ve.distance
            """,
            (blob, channel_id, embedding_model, k),
        )
        rows = await cursor.fetchall()
    except aiosqlite.Error as exc:
        raise VectorStoreError(f"vec0 search failed: {exc}") from exc

    return [
        VectorSearchHit(
            rowid=row[0],
            channel_id=row[1],
            object_path=row[2],
            distance=float(row[3]),
            embedding_model=row[4],
        )
        for row in rows
    ]


async def delete_channel_embeddings(
    db: aiosqlite.Connection,
    channel_id: str,
) -> int:
    """Удаляет все embeddings канала (например при удалении подключения).

    Возвращает количество удалённых строк.
    """
    # Сначала находим все rowid'ы канала
    cursor = await db.execute(
        "SELECT id FROM vec_objects WHERE channel_id = ?",
        (channel_id,),
    )
    rows = await cursor.fetchall()
    ids = [row[0] for row in rows]
    if not ids:
        return 0

    # Удаляем embeddings и metadata
    placeholders = ",".join("?" * len(ids))
    await db.execute(
        f"DELETE FROM vec_objects_embeddings WHERE rowid IN ({placeholders})",
        ids,
    )
    await db.execute(
        f"DELETE FROM vec_objects WHERE id IN ({placeholders})",
        ids,
    )
    await db.commit()
    return len(ids)


async def count_embeddings(
    db: aiosqlite.Connection,
    channel_id: str | None = None,
) -> int:
    """Возвращает количество embeddings в store.

    Если channel_id указан — только для этого канала. Иначе — всего.
    """
    if channel_id is None:
        cursor = await db.execute("SELECT COUNT(*) FROM vec_objects")
    else:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM vec_objects WHERE channel_id = ?",
            (channel_id,),
        )
    row = await cursor.fetchone()
    return int(row[0]) if row else 0
