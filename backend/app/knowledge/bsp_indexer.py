"""BSP Indexer — оркестратор load → embed → store для БСП (M-K2.8).

Knowledge Foundation Phase 8: запускает индексацию экспортных методов
БСП CommonModules (3.1 + 3.2) в vec_objects + bsp_chunks.

**Канал:** `_bsp` (зарезервированный namespace для БСП-эмбеддингов,
не пересекается с реальными MCP-каналами).

**Idempotency:** SHA-256 от content (doc + signature + body) — match → skip.

**Batch embedding:** DEFAULT_BATCH_SIZE=50 — баланс throughput vs timeout.

**Сравнение с ИТС indexer:**
- ИТС шёл по markdown файлам с переменным chunking. БСП: один метод =
  один chunk (естественная гранулярность API).
- ИТС category из директории. БСП version из ssl_3_1/3_2 root.
- Общий vec_objects backbone — фильтрация по channel_id.

**Что НЕ делает:**
- Не делает streaming progress (M-K3 опционально через SSE).
- Не удаляет orphan-чанки если метод был удалён из БСП (нужен явный
  /knowledge/bsp/reset endpoint, M-K3+).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.knowledge.bsp_loader import (
    BSPLoaderError,
    BSPMethod,
    load_bsp_modules,
)
from app.knowledge.embeddings import EmbeddingClient, EmbeddingError
from app.knowledge.vector_store import (
    VectorStoreError,
    init_vector_store,
    upsert_embedding,
)

logger = logging.getLogger(__name__)


BSP_CHANNEL_ID = "_bsp"
"""Зарезервированный channel_id для БСП-эмбеддингов."""


DEFAULT_BATCH_SIZE = 50


@dataclass(frozen=True, slots=True)
class BSPIndexProgress:
    """Метрики одной index_bsp_corpus run'ы.

    Attrs:
        roots_total: сколько ssl_root каталогов обработано (1 или 2)
        methods_total: сколько BSPMethod встретили
        methods_embedded: сколько фактически отправили в embedding
        methods_skipped: сколько уже актуальны (hash match)
        duration_ms: общее время run
        started_at / finished_at: ISO timestamps
        status: 'done' | 'failed'
        error: текст ошибки если failed
    """

    roots_total: int
    methods_total: int
    methods_embedded: int
    methods_skipped: int
    duration_ms: int
    started_at: str
    finished_at: str
    status: str
    error: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == "done"


class BSPIndexerError(Exception):
    """BSP indexer не смог отработать."""


async def _get_existing_method_hashes(
    db: aiosqlite.Connection,
    version: str,
) -> dict[tuple[str, str], str]:
    """Возвращает {(module, method): chunk_hash} для уже индексированных методов версии."""
    cursor = await db.execute(
        "SELECT module_name, method_name, chunk_hash FROM bsp_chunks WHERE version = ?",
        (version,),
    )
    rows = await cursor.fetchall()
    return {(row[0], row[1]): row[2] for row in rows}


async def _store_method_metadata(
    db: aiosqlite.Connection,
    method: BSPMethod,
) -> None:
    """INSERT OR REPLACE one bsp_chunks row. Commit делает caller."""
    await db.execute(
        """
        INSERT INTO bsp_chunks (
            object_path, module_name, method_name, method_kind,
            signature, doc_comment, content, version, source_path,
            char_count, chunk_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(object_path) DO UPDATE SET
            module_name = excluded.module_name,
            method_name = excluded.method_name,
            method_kind = excluded.method_kind,
            signature = excluded.signature,
            doc_comment = excluded.doc_comment,
            content = excluded.content,
            version = excluded.version,
            source_path = excluded.source_path,
            char_count = excluded.char_count,
            chunk_hash = excluded.chunk_hash,
            created_at = CURRENT_TIMESTAMP
        """,
        (
            method.object_path,
            method.module_name,
            method.method_name,
            method.method_kind,
            method.signature,
            method.doc_comment,
            method.content,
            method.version,
            method.source_path,
            len(method.content),
            method.content_hash,
        ),
    )


async def _embed_and_store_batch(
    db: aiosqlite.Connection,
    embedding_client: EmbeddingClient,
    batch: list[BSPMethod],
) -> int:
    """Embed batch + upsert. Returns количество сохранённых."""
    if not batch:
        return 0
    texts = [m.content for m in batch]
    result = await embedding_client.embed(texts)
    if len(result.embeddings) != len(batch):
        raise BSPIndexerError(
            f"BSP embedding mismatch: запросили {len(batch)}, получили {len(result.embeddings)}"
        )
    written = 0
    for method, embedding in zip(batch, result.embeddings, strict=True):
        await _store_method_metadata(db, method)
        await upsert_embedding(
            db,
            channel_id=BSP_CHANNEL_ID,
            object_path=method.object_path,
            embedding=embedding,
            embedding_model=result.model,
        )
        written += 1
    return written


async def index_bsp_corpus(
    db: aiosqlite.Connection,
    embedding_client: EmbeddingClient,
    ssl_roots: list[Path],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    force_reindex: bool = False,
) -> BSPIndexProgress:
    """Индексирует один или несколько ssl_root каталогов (3.1 + 3.2).

    Args:
        db: aiosqlite connection
        embedding_client: тот же клиент что и для search (модель должна
            совпадать)
        ssl_roots: список корневых каталогов БСП (например
            [Path("tools/ssl_3_1"), Path("tools/ssl_3_2")])
        batch_size: количество methods в одном embed-вызове
        force_reindex: True — игнорировать chunk_hash, переэмбедить всё

    Returns:
        BSPIndexProgress с метриками.

    Note: ошибка в одном ssl_root НЕ останавливает обработку других —
    best-effort. Только глобальные ошибки (vec_store init, нет embedding
    client) дают status='failed'.
    """
    started_dt = datetime.now(timezone.utc)
    started_iso = started_dt.isoformat()

    try:
        await init_vector_store(db, dim=embedding_client.dim)
    except VectorStoreError as exc:
        finished_dt = datetime.now(timezone.utc)
        logger.exception("BSP indexer: vec_store init failed")
        return BSPIndexProgress(
            roots_total=0, methods_total=0,
            methods_embedded=0, methods_skipped=0,
            duration_ms=int((finished_dt - started_dt).total_seconds() * 1000),
            started_at=started_iso, finished_at=finished_dt.isoformat(),
            status="failed", error=f"vec_store init failed: {exc}",
        )

    methods_total = 0
    methods_embedded = 0
    methods_skipped = 0
    pending_batch: list[BSPMethod] = []
    # Кеш hashes per version, чтобы не делать SELECT для каждого method
    hashes_by_version: dict[str, dict[tuple[str, str], str]] = {}

    async def flush_batch() -> int:
        nonlocal pending_batch
        if not pending_batch:
            return 0
        try:
            written = await _embed_and_store_batch(
                db, embedding_client, pending_batch,
            )
        except (EmbeddingError, VectorStoreError, BSPIndexerError):
            logger.exception(
                "BSP indexer: batch failed (%d methods) — skip батч, продолжаю",
                len(pending_batch),
            )
            pending_batch = []
            return 0
        pending_batch = []
        await db.commit()
        return written

    roots_total = 0
    for ssl_root in ssl_roots:
        try:
            methods = list(load_bsp_modules(ssl_root))
        except BSPLoaderError:
            logger.exception(
                "BSP indexer: loader failed для %s — skip root", ssl_root,
            )
            continue
        roots_total += 1

        for method in methods:
            methods_total += 1

            if not force_reindex:
                if method.version not in hashes_by_version:
                    hashes_by_version[method.version] = await _get_existing_method_hashes(
                        db, method.version,
                    )
                existing = hashes_by_version[method.version].get(
                    (method.module_name, method.method_name),
                )
                if existing == method.content_hash:
                    methods_skipped += 1
                    continue

            pending_batch.append(method)
            if len(pending_batch) >= batch_size:
                written = await flush_batch()
                methods_embedded += written

    # Хвост
    written = await flush_batch()
    methods_embedded += written

    finished_dt = datetime.now(timezone.utc)
    duration_ms = int((finished_dt - started_dt).total_seconds() * 1000)

    logger.info(
        "BSP indexer DONE: roots %d, methods %d (embedded %d, skipped %d) за %d мс",
        roots_total, methods_total, methods_embedded, methods_skipped, duration_ms,
    )

    return BSPIndexProgress(
        roots_total=roots_total,
        methods_total=methods_total,
        methods_embedded=methods_embedded,
        methods_skipped=methods_skipped,
        duration_ms=duration_ms,
        started_at=started_iso, finished_at=finished_dt.isoformat(),
        status="done",
    )


async def count_bsp_methods(db: aiosqlite.Connection) -> int:
    """Возвращает количество индексированных БСП-методов."""
    cursor = await db.execute("SELECT COUNT(*) FROM bsp_chunks")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def count_bsp_modules(db: aiosqlite.Connection) -> int:
    """Возвращает количество уникальных module_name в индексе."""
    cursor = await db.execute("SELECT COUNT(DISTINCT module_name) FROM bsp_chunks")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def count_bsp_by_version(db: aiosqlite.Connection) -> dict[str, int]:
    """Возвращает {version: count} разбивку по версиям БСП."""
    cursor = await db.execute(
        "SELECT version, COUNT(*) FROM bsp_chunks GROUP BY version"
    )
    rows = await cursor.fetchall()
    return {row[0]: int(row[1]) for row in rows}
