"""BSP Search — semantic search по корпусу БСП экспортных API (M-K2.8).

Knowledge Foundation Phase 8: query → embed → semantic_search(_bsp) →
JOIN bsp_chunks → BSPSearchHit. Используется LLM tool'ом `search_bsp`
и admin endpoint'ом `/knowledge/bsp/search`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiosqlite

from app.knowledge.bsp_indexer import BSP_CHANNEL_ID
from app.knowledge.embeddings import EmbeddingClient, EmbeddingError
from app.knowledge.vector_store import VectorStoreError, semantic_search

logger = logging.getLogger(__name__)


DEFAULT_SEARCH_K = 5


@dataclass(frozen=True, slots=True)
class BSPSearchHit:
    """Один результат поиска по БСП.

    Attrs:
        module_name: «ДлительныеОперации»
        method_name: «ВыполнитьФункцию»
        method_kind: «Функция» | «Процедура»
        signature: полная сигнатура одной строкой
        doc_comment: doc-комментарий (без `//`)
        content: doc + signature + body excerpt
        version: «3.1» | «3.2»
        source_path: путь относительно ssl_*/
        distance: cosine distance (меньше = лучше)
    """

    module_name: str
    method_name: str
    method_kind: str
    signature: str
    doc_comment: str
    content: str
    version: str
    source_path: str
    distance: float

    @property
    def object_path(self) -> str:
        return f"bsp:{self.version}:{self.module_name}.{self.method_name}"

    @property
    def full_name(self) -> str:
        """`<Модуль>.<Метод>` — стандартный формат вызова в BSL."""
        return f"{self.module_name}.{self.method_name}"

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "method_name": self.method_name,
            "method_kind": self.method_kind,
            "signature": self.signature,
            "doc_comment": self.doc_comment,
            "content": self.content,
            "version": self.version,
            "source_path": self.source_path,
            "distance": self.distance,
        }

    def to_citation(self) -> str:
        """Краткая ссылка для LLM-prompt: «БСП 3.2 → ДлительныеОперации.ВыполнитьФункцию (Функция)»."""
        return (
            f"БСП {self.version} → {self.full_name} ({self.method_kind})"
        )


class BSPSearchError(Exception):
    """BSP search не смог отработать."""


async def search_bsp(
    db: aiosqlite.Connection,
    embedding_client: EmbeddingClient,
    query: str,
    *,
    k: int = DEFAULT_SEARCH_K,
    version_filter: str | None = None,
) -> list[BSPSearchHit]:
    """Semantic search по БСП-корпусу.

    Args:
        db: aiosqlite connection
        embedding_client: тот же клиент что и при индексации
        query: текст запроса на естественном языке
        k: топ-K результатов
        version_filter: '3.1' | '3.2' | None (без фильтра)

    Returns:
        list[BSPSearchHit] отсортированный по distance ASC.

    Raises:
        BSPSearchError при ошибке embedding'а или БД.
    """
    if not query or not query.strip():
        raise BSPSearchError("query пустой")
    if k <= 0:
        raise BSPSearchError(f"k должен быть > 0, получено {k}")

    try:
        embed_result = await embedding_client.embed([query])
    except EmbeddingError as exc:
        raise BSPSearchError(f"embedding query failed: {exc}") from exc
    if not embed_result.embeddings:
        raise BSPSearchError("embedding client вернул пустой result")
    query_vector = embed_result.embeddings[0]

    # Берём с запасом если будет фильтр по version (semantic_search не знает
    # про version — он работает на channel_id)
    effective_k = k * 3 if version_filter else k

    try:
        vec_hits = await semantic_search(
            db,
            channel_id=BSP_CHANNEL_ID,
            query_embedding=query_vector,
            k=effective_k,
            embedding_model=embed_result.model,
        )
    except VectorStoreError as exc:
        raise BSPSearchError(f"vec search failed: {exc}") from exc

    if not vec_hits:
        return []

    object_paths = [hit.object_path for hit in vec_hits]
    placeholders = ",".join("?" * len(object_paths))
    sql = f"""
        SELECT object_path, module_name, method_name, method_kind,
               signature, doc_comment, content, version, source_path
        FROM bsp_chunks
        WHERE object_path IN ({placeholders})
    """
    params: list = list(object_paths)
    if version_filter:
        sql += " AND version = ?"
        params.append(version_filter)

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    by_path = {row[0]: row for row in rows}

    results: list[BSPSearchHit] = []
    for vec_hit in vec_hits:
        row = by_path.get(vec_hit.object_path)
        if row is None:
            # Orphan / отфильтрован по version — skip
            continue
        _, module_name, method_name, method_kind, signature, doc, content, version, source_path = row
        results.append(BSPSearchHit(
            module_name=module_name,
            method_name=method_name,
            method_kind=method_kind,
            signature=signature,
            doc_comment=doc,
            content=content,
            version=version,
            source_path=source_path,
            distance=vec_hit.distance,
        ))
        if len(results) >= k:
            break

    return results
