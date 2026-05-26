"""ITS Search — semantic search по корпусу ИТС-стандартов (M-K2.7).

Knowledge Foundation Phase 7: query → embed → semantic_search(_its) →
JOIN с its_chunks → ITSSearchHit. Используется LLM-tool'ом `search_its`
(`its_tool.py`) и admin endpoint'ом `/knowledge/its/search`.

**Stateless:** ничего не хранит, не кэширует. Каждый вызов:
1. Embed query (1 OpenAI call)
2. SQL semantic_search в vec_objects
3. SQL fetch its_chunks по object_path
4. Map → ITSSearchHit

**Не делает:**
- Re-ranking (M-K3 опционально через BM25)
- Filter по category (M-K3 — сейчас всё через k cut-off)
- Multi-query / query rewriting (M-K3)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiosqlite

from app.knowledge.embeddings import EmbeddingClient, EmbeddingError
from app.knowledge.its_indexer import ITS_CHANNEL_ID
from app.knowledge.vector_store import VectorStoreError, semantic_search

logger = logging.getLogger(__name__)


DEFAULT_SEARCH_K = 5
"""Сколько чанков возвращать по умолчанию (баланс recall vs context size)."""


@dataclass(frozen=True, slots=True)
class ITSSearchHit:
    """Один результат поиска по ИТС.

    Содержит всё что нужно LLM для цитирования:
    - doc_id / source_path — ссылка на источник
    - title / section_title — для human-readable отображения
    - content — текст чанка
    - category — для приоритезации (std важнее patterns?)
    - distance — score близости (меньше = лучше)
    """

    doc_id: str
    chunk_index: int
    title: str
    section_title: str | None
    content: str
    category: str
    source_path: str
    distance: float

    @property
    def object_path(self) -> str:
        return f"its:{self.doc_id}#{self.chunk_index}"

    def to_dict(self) -> dict:
        """JSON-friendly для tool response / HTTP endpoint."""
        return {
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "title": self.title,
            "section_title": self.section_title,
            "content": self.content,
            "category": self.category,
            "source_path": self.source_path,
            "distance": self.distance,
        }

    def to_citation(self) -> str:
        """Краткая ссылка для LLM-prompt: «std396: Обработчик ОбработкаЗаполнения (раздел 1.)»."""
        if self.section_title:
            return f"{self.doc_id}: {self.title} (раздел {self.section_title})"
        return f"{self.doc_id}: {self.title}"


class ITSSearchError(Exception):
    """ITS search не смог отработать (embedding / DB)."""


async def search_its(
    db: aiosqlite.Connection,
    embedding_client: EmbeddingClient,
    query: str,
    *,
    k: int = DEFAULT_SEARCH_K,
) -> list[ITSSearchHit]:
    """Semantic search по ИТС-корпусу.

    Args:
        db: aiosqlite connection (init_vector_store должен быть вызван ранее,
            обычно через index_its_corpus)
        embedding_client: тот же клиент что использовался при индексации
            (модель должна совпадать с записанными embeddings)
        query: текст запроса на естественном языке
        k: сколько top-результатов вернуть (default 5)

    Returns:
        list[ITSSearchHit] отсортированный по distance ASC. Пустой list
        если индекс пуст или нет матчей.

    Raises:
        ITSSearchError при ошибке embedding'а или БД.
    """
    if not query or not query.strip():
        raise ITSSearchError("query пустой")
    if k <= 0:
        raise ITSSearchError(f"k должен быть > 0, получено {k}")

    # 1. Embed query
    try:
        embed_result = await embedding_client.embed([query])
    except EmbeddingError as exc:
        raise ITSSearchError(f"embedding query failed: {exc}") from exc
    if not embed_result.embeddings:
        raise ITSSearchError("embedding client вернул пустой result")
    query_vector = embed_result.embeddings[0]

    # 2. Vector search
    try:
        vec_hits = await semantic_search(
            db,
            channel_id=ITS_CHANNEL_ID,
            query_embedding=query_vector,
            k=k,
            embedding_model=embed_result.model,
        )
    except VectorStoreError as exc:
        raise ITSSearchError(f"vec search failed: {exc}") from exc

    if not vec_hits:
        return []

    # 3. Enrich через JOIN с its_chunks (один SELECT IN (...))
    object_paths = [hit.object_path for hit in vec_hits]
    placeholders = ",".join("?" * len(object_paths))
    cursor = await db.execute(
        f"""
        SELECT object_path, doc_id, chunk_index, title, section_title,
               content, category, source_path
        FROM its_chunks
        WHERE object_path IN ({placeholders})
        """,
        object_paths,
    )
    rows = await cursor.fetchall()
    by_path = {row[0]: row for row in rows}

    # 4. Сохраняем порядок vec_hits (ORDER BY distance ASC)
    results: list[ITSSearchHit] = []
    for vec_hit in vec_hits:
        row = by_path.get(vec_hit.object_path)
        if row is None:
            # vec_objects запись без its_chunks — orphan. Лог + skip.
            logger.warning(
                "Orphan vec_objects entry без its_chunks: %s",
                vec_hit.object_path,
            )
            continue
        _, doc_id, chunk_index, title, section_title, content, category, source_path = row
        results.append(ITSSearchHit(
            doc_id=doc_id,
            chunk_index=int(chunk_index),
            title=title,
            section_title=section_title,
            content=content,
            category=category,
            source_path=source_path,
            distance=vec_hit.distance,
        ))

    return results
