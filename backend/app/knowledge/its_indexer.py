"""ITS Indexer — оркестратор load → chunk → embed → store (M-K2.7).

Knowledge Foundation Phase 7: запускает полный или инкрементальный
re-index ИТС-стандартов в `its_chunks` + `vec_objects`.

**Канал:** `_its` (зарезервированный namespace, не реальный MCP).
Эмбеддинги изолированы от per-channel metadata индексов: vec0 один,
но channel_id фильтрует выдачу.

**Idempotency:** каждый чанк хэшируется (SHA-256 контента) при load.
Перед embed'ом сравниваем с `its_chunks.chunk_hash`:
- match → skip (нет embedding'а, нет $)
- no match / нет записи → embed + upsert

**Batch embedding:** OpenAI принимает до 2048 inputs за вызов, но мы
батчим по `DEFAULT_BATCH_SIZE=50` — баланс между throughput и timeout
risk на медленных каналах.

**Что НЕ делает M-K2.7 indexer:**
- Не парит chunk'и по моделям — одна модель = один index pass.
- Не делает streaming progress (SSE) — это в M-K3, сейчас sync await
  возвращает финальный `ITSIndexProgress`.
- Не удаляет orphan chunks (документ исчез из v8std) — если ИТС-чанк
  ушёл, его vec_objects останется. Acceptable для M-K2.7 (через rebuild
  channel `_its` можно вычистить).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.knowledge.embeddings import EmbeddingClient, EmbeddingError
from app.knowledge.its_chunker import DEFAULT_MAX_CHARS, ITSChunk, chunk_document
from app.knowledge.its_loader import ITSDocument, ITSLoaderError, load_its_documents
from app.knowledge.vector_store import (
    VectorStoreError,
    init_vector_store,
    upsert_embedding,
)

logger = logging.getLogger(__name__)


ITS_CHANNEL_ID = "_its"
"""Зарезервированный channel_id для ИТС-эмбеддингов (не пересекается с
 реальными MCP-каналами — UUID v4 строки, никогда не начинающиеся с `_`)."""


DEFAULT_BATCH_SIZE = 50
"""Сколько chunks отправляем в OpenAI за один embed-вызов."""


@dataclass(frozen=True, slots=True)
class ITSIndexProgress:
    """Финальная сводка одной index_its_corpus run'ы.

    Attrs:
        docs_total: сколько ITSDocument прошли через loader
        docs_processed: сколько успешно дочанчены и сохранены
        chunks_total: сколько чанков всего получилось
        chunks_embedded: сколько фактически отправили в embedding (новые/изменённые)
        chunks_skipped: сколько пропустили (hash совпал — уже актуально)
        duration_ms: тоталь время в миллисекундах
        started_at / finished_at: ISO timestamps
        status: 'done' | 'failed'
        error: текст ошибки если status='failed', иначе None
    """

    docs_total: int
    docs_processed: int
    chunks_total: int
    chunks_embedded: int
    chunks_skipped: int
    duration_ms: int
    started_at: str
    finished_at: str
    status: str
    error: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == "done"


class ITSIndexerError(Exception):
    """ITS indexer не смог отработать (loader / embedding / DB)."""


async def _get_existing_chunk_hashes(
    db: aiosqlite.Connection,
    doc_id: str,
) -> dict[int, str]:
    """Возвращает {chunk_index: chunk_hash} для уже индексированного документа."""
    cursor = await db.execute(
        "SELECT chunk_index, chunk_hash FROM its_chunks WHERE doc_id = ?",
        (doc_id,),
    )
    rows = await cursor.fetchall()
    return {row[0]: row[1] for row in rows}


async def _store_chunk_metadata(
    db: aiosqlite.Connection,
    doc: ITSDocument,
    chunk: ITSChunk,
) -> None:
    """INSERT OR REPLACE one its_chunks row. Commit делает caller (батч)."""
    await db.execute(
        """
        INSERT INTO its_chunks (
            object_path, doc_id, chunk_index, title, section_title,
            content, category, source_path, char_count, chunk_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(object_path) DO UPDATE SET
            title = excluded.title,
            section_title = excluded.section_title,
            content = excluded.content,
            category = excluded.category,
            source_path = excluded.source_path,
            char_count = excluded.char_count,
            chunk_hash = excluded.chunk_hash,
            created_at = CURRENT_TIMESTAMP
        """,
        (
            chunk.object_path,
            chunk.doc_id,
            chunk.chunk_index,
            doc.title,
            chunk.section_title,
            chunk.content,
            doc.category,
            doc.source_path,
            chunk.char_count,
            chunk.content_hash,
        ),
    )


async def _embed_and_store_batch(
    db: aiosqlite.Connection,
    embedding_client: EmbeddingClient,
    batch: list[tuple[ITSDocument, ITSChunk]],
) -> int:
    """Делает один embedding-вызов на batch и upsert'ит результат.

    Returns:
        количество чанков фактически записанных.

    Raises:
        EmbeddingError / VectorStoreError / aiosqlite.Error.
    """
    if not batch:
        return 0

    texts = [chunk.content for _, chunk in batch]
    result = await embedding_client.embed(texts)

    if len(result.embeddings) != len(batch):
        raise ITSIndexerError(
            f"Embedding mismatch: запросили {len(batch)}, получили {len(result.embeddings)}"
        )

    written = 0
    for (doc, chunk), embedding in zip(batch, result.embeddings, strict=True):
        await _store_chunk_metadata(db, doc, chunk)
        await upsert_embedding(
            db,
            channel_id=ITS_CHANNEL_ID,
            object_path=chunk.object_path,
            embedding=embedding,
            embedding_model=result.model,
        )
        written += 1

    return written


def _iter_doc_chunks(
    docs: Iterable[ITSDocument],
    *,
    max_chars: int,
) -> Iterable[tuple[ITSDocument, ITSChunk]]:
    """Cartesian iterator: (doc, chunk) для всех чанков всех docs."""
    for doc in docs:
        for chunk in chunk_document(doc, max_chars=max_chars):
            yield doc, chunk


async def index_its_corpus(
    db: aiosqlite.Connection,
    embedding_client: EmbeddingClient,
    docs_root: Path,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    force_reindex: bool = False,
) -> ITSIndexProgress:
    """Полный/инкрементальный re-index ИТС-корпуса в vec_objects + its_chunks.

    Алгоритм:
    1. Гарантировать vec0 (init_vector_store) с dim = embedding_client.dim.
    2. Для каждого ITSDocument:
       a. Загрузить existing chunk_hashes
       b. Для каждого ITSChunk — сравнить hash. Если match И не force →
          skip; иначе → положить в batch.
    3. Каждые `batch_size` накопленных чанков → embed + store.
    4. Хвост — final batch.

    Args:
        db: aiosqlite connection (caller владеет lifecycle)
        embedding_client: реализация EmbeddingClient (OpenAI / Mock)
        docs_root: путь к `tools/v8std/docs/`
        max_chars: лимит chunk size (передаётся в chunk_document)
        batch_size: количество чанков в одном embed-вызове
        force_reindex: True — игнорировать chunk_hash, переэмбедить всё

    Returns:
        ITSIndexProgress с метриками.

    Note: ошибки внутри одного документа НЕ останавливают весь run (best-effort).
    Они логируются и считаются как «не processed». Глобальная ошибка
    (loader root отсутствует, embedding endpoint dead) возвращается с status='failed'.
    """
    started_dt = datetime.now(timezone.utc)
    started_iso = started_dt.isoformat()

    docs_total = 0
    docs_processed = 0
    chunks_total = 0
    chunks_embedded = 0
    chunks_skipped = 0

    try:
        await init_vector_store(db, dim=embedding_client.dim)
    except VectorStoreError as exc:
        finished_dt = datetime.now(timezone.utc)
        logger.exception("ITS indexer: не могу инициализировать vec0")
        return ITSIndexProgress(
            docs_total=0, docs_processed=0,
            chunks_total=0, chunks_embedded=0, chunks_skipped=0,
            duration_ms=int((finished_dt - started_dt).total_seconds() * 1000),
            started_at=started_iso, finished_at=finished_dt.isoformat(),
            status="failed",
            error=f"vec_store init failed: {exc}",
        )

    try:
        documents = list(load_its_documents(docs_root))
    except ITSLoaderError as exc:
        finished_dt = datetime.now(timezone.utc)
        logger.exception("ITS indexer: loader failed")
        return ITSIndexProgress(
            docs_total=0, docs_processed=0,
            chunks_total=0, chunks_embedded=0, chunks_skipped=0,
            duration_ms=int((finished_dt - started_dt).total_seconds() * 1000),
            started_at=started_iso, finished_at=finished_dt.isoformat(),
            status="failed",
            error=f"loader failed: {exc}",
        )

    docs_total = len(documents)

    pending_batch: list[tuple[ITSDocument, ITSChunk]] = []

    async def flush_batch() -> int:
        nonlocal pending_batch
        if not pending_batch:
            return 0
        try:
            written = await _embed_and_store_batch(db, embedding_client, pending_batch)
        except (EmbeddingError, VectorStoreError, ITSIndexerError):
            logger.exception(
                "ITS indexer: batch embed/store failed (%d chunks)",
                len(pending_batch),
            )
            # Не падаем — следующий батч может пройти. Помечаем эти как
            # не embedded (counters не инкрементируем).
            pending_batch = []
            return 0
        pending_batch = []
        await db.commit()
        return written

    try:
        for doc in documents:
            try:
                existing_hashes = (
                    {} if force_reindex
                    else await _get_existing_chunk_hashes(db, doc.doc_id)
                )
                doc_chunks_processed = 0
                for chunk in chunk_document(doc, max_chars=max_chars):
                    chunks_total += 1
                    existing_hash = existing_hashes.get(chunk.chunk_index)
                    if existing_hash == chunk.content_hash and not force_reindex:
                        chunks_skipped += 1
                        doc_chunks_processed += 1
                        continue

                    pending_batch.append((doc, chunk))
                    doc_chunks_processed += 1

                    if len(pending_batch) >= batch_size:
                        written = await flush_batch()
                        chunks_embedded += written

                if doc_chunks_processed > 0:
                    docs_processed += 1

            except Exception:
                logger.exception("ITS indexer: пропускаю doc_id=%s", doc.doc_id)
                continue

        # Хвостовой batch
        written = await flush_batch()
        chunks_embedded += written

    except Exception as exc:
        finished_dt = datetime.now(timezone.utc)
        logger.exception("ITS indexer: unexpected failure")
        return ITSIndexProgress(
            docs_total=docs_total,
            docs_processed=docs_processed,
            chunks_total=chunks_total,
            chunks_embedded=chunks_embedded,
            chunks_skipped=chunks_skipped,
            duration_ms=int((finished_dt - started_dt).total_seconds() * 1000),
            started_at=started_iso, finished_at=finished_dt.isoformat(),
            status="failed",
            error=f"unexpected: {exc}",
        )

    finished_dt = datetime.now(timezone.utc)
    duration_ms = int((finished_dt - started_dt).total_seconds() * 1000)

    logger.info(
        "ITS indexer DONE: docs %d/%d, chunks %d (embedded %d, skipped %d) за %d мс",
        docs_processed, docs_total, chunks_total, chunks_embedded, chunks_skipped,
        duration_ms,
    )

    return ITSIndexProgress(
        docs_total=docs_total,
        docs_processed=docs_processed,
        chunks_total=chunks_total,
        chunks_embedded=chunks_embedded,
        chunks_skipped=chunks_skipped,
        duration_ms=duration_ms,
        started_at=started_iso, finished_at=finished_dt.isoformat(),
        status="done",
    )


async def count_its_chunks(db: aiosqlite.Connection) -> int:
    """Возвращает количество индексированных ИТС-чанков."""
    cursor = await db.execute("SELECT COUNT(*) FROM its_chunks")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def count_its_documents(db: aiosqlite.Connection) -> int:
    """Возвращает количество уникальных doc_id в индексе."""
    cursor = await db.execute("SELECT COUNT(DISTINCT doc_id) FROM its_chunks")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0
