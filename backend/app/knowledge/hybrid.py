"""Hybrid retrieval helpers — RRF merge + FTS5 query building (M-K4 ИТС-KB).

Общий слой для `its_search` и `bsp_search`: безопасное превращение NL-запроса
в FTS5 MATCH, BM25-поиск по object_path и Reciprocal Rank Fusion слияние
векторного и keyword-ранжирований.

WHY hybrid: чистый векторный поиск (1) требует embedding-ключ и (2) промахивается
на точных терминах — имена методов БСП, номера стандартов. BM25 закрывает оба:
работает без ключа и точен на лексических совпадениях. RRF объединяет оба
ранжирования без нормализации скоров (разные шкалы distance vs bm25-rank).
"""

from __future__ import annotations

import logging
import re

import aiosqlite

from app.knowledge.embeddings import EmbeddingClient, EmbeddingError
from app.knowledge.vector_store import VectorStoreError, semantic_search

logger = logging.getLogger(__name__)

RRF_K = 60
"""Параметр RRF (Cormack et al. 2009): сглаживает вклад низких рангов."""

_CANDIDATE_MULTIPLIER = 4
_MIN_CANDIDATES = 20

# \w в Python (str) по умолчанию Unicode-aware: матчит кириллицу/латиницу/цифры.
_TOKEN_RE = re.compile(r"\w+")


def candidate_k(k: int) -> int:
    """Сколько кандидатов брать из каждого источника до RRF (с запасом)."""
    return max(k * _CANDIDATE_MULTIPLIER, _MIN_CANDIDATES)


def to_fts_match(query: str) -> str | None:
    """NL-запрос → безопасная FTS5 MATCH-строка (или None если нет токенов).

    Токены < 2 символов отбрасываются; каждый оборачивается в кавычки
    (phrase-literal — защита от FTS5 syntax error на `.`, операторах вроде
    `ОбщегоНазначения.Метод`); объединение через OR максимизирует recall
    (финальное ранжирование делает RRF).
    """
    if not query:
        return None
    seen: set[str] = set()
    uniq: list[str] = []
    for token in _TOKEN_RE.findall(query.lower()):
        if len(token) >= 2 and token not in seen:
            seen.add(token)
            uniq.append(token)
    if not uniq:
        return None
    return " OR ".join(f'"{t}"' for t in uniq)


async def bm25_object_paths(
    db: aiosqlite.Connection,
    fts_table: str,
    query: str,
    *,
    k: int,
) -> list[str]:
    """BM25-поиск по FTS5-таблице → object_path в порядке релевантности.

    `fts_table` — доверенное имя ('its_chunks_fts' / 'bsp_chunks_fts'),
    НЕ из user input (интерполируется в SQL). Ошибки FTS5 (битый MATCH,
    отсутствие таблицы) → [] — keyword-слой не должен валить hybrid.
    """
    match = to_fts_match(query)
    if not match:
        return []
    try:
        cursor = await db.execute(
            f"SELECT object_path FROM {fts_table} "  # noqa: S608 — fts_table доверенное
            f"WHERE {fts_table} MATCH ? ORDER BY rank LIMIT ?",
            (match, k),
        )
        rows = await cursor.fetchall()
    except aiosqlite.Error as exc:
        logger.warning("BM25 поиск по %s не отработал: %s", fts_table, exc)
        return []
    return [row[0] for row in rows]


def rrf_merge(ranked_lists: list[list[str]], *, k: int, rrf_k: int = RRF_K) -> list[str]:
    """Reciprocal Rank Fusion: слияние ранжированных списков object_path.

    score(path) = Σ 1/(rrf_k + rank) по всем спискам где path встретился.
    Возврат — top-k path по убыванию score. При единственном непустом списке
    порядок сохраняется (RRF монотонен по rank), поэтому деградация на
    vector-only или BM25-only корректна.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, path in enumerate(ranked, start=1):
            scores[path] = scores.get(path, 0.0) + 1.0 / (rrf_k + rank)
    return sorted(scores, key=lambda p: scores[p], reverse=True)[:k]


async def vector_object_paths(
    db: aiosqlite.Connection,
    embedding_client: EmbeddingClient,
    query: str,
    *,
    channel_id: str,
    k: int,
) -> tuple[list[str], dict[str, float]]:
    """Best-effort векторный слой hybrid-поиска для канала `channel_id`.

    Возврат: (object_paths в порядке близости, {object_path: distance}).
    Embedding недоступен (нет ключа) или vec-store упал → ([], {}) — поиск
    деградирует на BM25-only, а не падает.
    """
    try:
        embed_result = await embedding_client.embed([query])
    except EmbeddingError as exc:
        logger.warning("vector слой недоступен (embedding: %s) — BM25-only", exc)
        return [], {}
    if not embed_result.embeddings:
        return [], {}
    try:
        vec_hits = await semantic_search(
            db,
            channel_id=channel_id,
            query_embedding=embed_result.embeddings[0],
            k=k,
            embedding_model=embed_result.model,
        )
    except VectorStoreError as exc:
        logger.warning("vector слой недоступен (vec store: %s) — BM25-only", exc)
        return [], {}
    paths = [hit.object_path for hit in vec_hits]
    distances = {hit.object_path: hit.distance for hit in vec_hits}
    return paths, distances
