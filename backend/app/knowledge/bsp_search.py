"""BSP Search — hybrid поиск по корпусу БСП экспортных API (M-K2.8 + M-K4 hybrid).

query → (vector ANN `_bsp` ⊕ BM25 `bsp_chunks_fts`) → RRF → JOIN bsp_chunks →
BSPSearchHit. Используется LLM tool'ом `search_bsp` и admin endpoint'ом
`/knowledge/bsp/search`.

**M-K4 hybrid:** vector + BM25 через RRF (`hybrid.py`). Векторный слой
best-effort: при недоступном embedding (нет ключа) поиск деградирует на
BM25-only. BM25 особенно ценен для БСП: точные имена методов/модулей
(`ДлительныеОперации.ВыполнитьФункцию`) матчатся лексически, а не «по смыслу».
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiosqlite

from app.knowledge.bsp_indexer import BSP_CHANNEL_ID
from app.knowledge.embeddings import EmbeddingClient
from app.knowledge.hybrid import (
    bm25_object_paths,
    candidate_k,
    rrf_merge,
    vector_object_paths,
)

logger = logging.getLogger(__name__)


DEFAULT_SEARCH_K = 5

BSP_FTS_TABLE = "bsp_chunks_fts"

# Псевдо-distance для находок только из BM25 (вектора нет). Реальный порядок
# задаёт RRF; distance оставлен для обратной совместимости BSPSearchHit.
_BM25_ONLY_DISTANCE = 1.0


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
        distance: vec-distance (меньше = лучше); _BM25_ONLY_DISTANCE для
            keyword-only находок. Порядок в списке отражает RRF, не distance.
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
    """BSP search не смог отработать (валидация / БД)."""


async def search_bsp(
    db: aiosqlite.Connection,
    embedding_client: EmbeddingClient,
    query: str,
    *,
    k: int = DEFAULT_SEARCH_K,
    version_filter: str | None = None,
) -> list[BSPSearchHit]:
    """Hybrid search по БСП-корпусу (vector ⊕ BM25 → RRF).

    Args:
        db: aiosqlite connection
        embedding_client: клиент, совпадающий с использованным при индексации
        query: текст запроса на естественном языке
        k: топ-K результатов
        version_filter: '3.1' | '3.2' | None (без фильтра)

    Returns:
        list[BSPSearchHit] в порядке RRF-релевантности.

    Raises:
        BSPSearchError при невалидном вводе (пустой query / k <= 0).
    """
    if not query or not query.strip():
        raise BSPSearchError("query пустой")
    if k <= 0:
        raise BSPSearchError(f"k должен быть > 0, получено {k}")

    cand_k = candidate_k(k)

    vec_paths, vec_distances = await vector_object_paths(
        db, embedding_client, query, channel_id=BSP_CHANNEL_ID, k=cand_k
    )
    bm25_paths = await bm25_object_paths(db, BSP_FTS_TABLE, query, k=cand_k)

    if not vec_paths and not bm25_paths:
        return []

    # RRF до cand_k кандидатов — запас для последующего version_filter
    merged = rrf_merge([vec_paths, bm25_paths], k=cand_k)
    if not merged:
        return []

    placeholders = ",".join("?" * len(merged))
    sql = f"""
        SELECT object_path, module_name, method_name, method_kind,
               signature, doc_comment, content, version, source_path
        FROM bsp_chunks
        WHERE object_path IN ({placeholders})
    """
    params: list = list(merged)
    if version_filter:
        sql += " AND version = ?"
        params.append(version_filter)

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    by_path = {row[0]: row for row in rows}

    results: list[BSPSearchHit] = []
    for path in merged:
        row = by_path.get(path)
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
            distance=vec_distances.get(path, _BM25_ONLY_DISTANCE),
        ))
        if len(results) >= k:
            break

    return results
