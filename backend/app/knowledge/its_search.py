"""ITS Search — hybrid поиск по корпусу ИТС-стандартов (M-K2.7 + M-K4 hybrid).

query → (vector ANN `_its` ⊕ BM25 `its_chunks_fts`) → RRF → JOIN its_chunks →
ITSSearchHit. Используется LLM-tool'ом `search_its` (`its_tool.py`) и admin
endpoint'ом `/knowledge/its/search`.

**M-K4 hybrid:** до этого был только векторный поиск. Теперь vector + BM25
сливаются через Reciprocal Rank Fusion (`hybrid.py`). Векторный слой —
best-effort: если embedding недоступен (нет ключа / провайдер упал),
поиск деградирует на BM25-only (keyword) и продолжает работать.

**Stateless:** ничего не хранит, не кэширует.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiosqlite

from app.knowledge.embeddings import EmbeddingClient
from app.knowledge.hybrid import (
    bm25_object_paths,
    candidate_k,
    rrf_merge,
    vector_object_paths,
)
from app.knowledge.its_indexer import ITS_CHANNEL_ID

logger = logging.getLogger(__name__)


DEFAULT_SEARCH_K = 5
"""Сколько чанков возвращать по умолчанию (баланс recall vs context size)."""

ITS_FTS_TABLE = "its_chunks_fts"

# Псевдо-distance для чанков, найденных ТОЛЬКО через BM25 (нет вектора).
# distance оставлен в ITSSearchHit для обратной совместимости; реальное
# ранжирование делает RRF. Sentinel > любой нормальной cosine distance [0..2].
_BM25_ONLY_DISTANCE = 1.0


@dataclass(frozen=True, slots=True)
class ITSSearchHit:
    """Один результат поиска по ИТС.

    Содержит всё что нужно LLM для цитирования:
    - doc_id / source_path — ссылка на источник
    - title / section_title — для human-readable отображения
    - content — текст чанка
    - category — для приоритезации (std важнее patterns?)
    - distance — vec-distance (меньше = лучше); _BM25_ONLY_DISTANCE для
      keyword-only находок. Порядок в списке отражает RRF, не distance.
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
    """ITS search не смог отработать (валидация / БД)."""


async def search_its(
    db: aiosqlite.Connection,
    embedding_client: EmbeddingClient,
    query: str,
    *,
    k: int = DEFAULT_SEARCH_K,
) -> list[ITSSearchHit]:
    """Hybrid search по ИТС-корпусу (vector ⊕ BM25 → RRF).

    Args:
        db: aiosqlite connection (init_vector_store вызван ранее индексером)
        embedding_client: клиент, совпадающий с использованным при индексации
        query: текст запроса на естественном языке
        k: сколько top-результатов вернуть (default 5)

    Returns:
        list[ITSSearchHit] в порядке RRF-релевантности. Пустой list если
        ни vector, ни BM25 не дали матчей.

    Raises:
        ITSSearchError при невалидном вводе (пустой query / k <= 0).
    """
    if not query or not query.strip():
        raise ITSSearchError("query пустой")
    if k <= 0:
        raise ITSSearchError(f"k должен быть > 0, получено {k}")

    cand_k = candidate_k(k)

    # 1. Vector (best-effort) + 2. BM25 (без ключа)
    vec_paths, vec_distances = await vector_object_paths(
        db, embedding_client, query, channel_id=ITS_CHANNEL_ID, k=cand_k
    )
    bm25_paths = await bm25_object_paths(db, ITS_FTS_TABLE, query, k=cand_k)

    if not vec_paths and not bm25_paths:
        return []

    # 3. RRF merge → top-k object_path
    merged = rrf_merge([vec_paths, bm25_paths], k=k)
    if not merged:
        return []

    # 4. Enrich через JOIN its_chunks, сохраняя RRF-порядок
    placeholders = ",".join("?" * len(merged))
    cursor = await db.execute(
        f"""
        SELECT object_path, doc_id, chunk_index, title, section_title,
               content, category, source_path
        FROM its_chunks
        WHERE object_path IN ({placeholders})
        """,
        merged,
    )
    rows = await cursor.fetchall()
    by_path = {row[0]: row for row in rows}

    results: list[ITSSearchHit] = []
    for path in merged:
        row = by_path.get(path)
        if row is None:
            # vec/fts запись без its_chunks — orphan. Лог + skip.
            logger.warning("Orphan запись без its_chunks: %s", path)
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
            distance=vec_distances.get(path, _BM25_ONLY_DISTANCE),
        ))

    return results
