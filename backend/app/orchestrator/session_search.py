"""Session search — 3 mode FTS5 поиск по истории.

Sprint 4 (Hermes D4): расширяет существующий /search route.

Modes:
- discovery: q → top-N сессий с snippet (default — то что было).
- deep: session_id + q → ±5 message window вокруг матчей в этой сессии.
- cross: q → все matches across all sessions, агрегированные по сессии.

Базовая FTS5 безопасность (escape) переиспользуется из routes/search.py.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Literal

import aiosqlite

logger = logging.getLogger(__name__)

SearchMode = Literal["discovery", "deep", "cross"]

# Окно ±N сообщений для deep mode.
DEEP_WINDOW = 5


@dataclass(frozen=True)
class SearchHit:
    session_id: str
    session_title: str
    channel_id: str
    message_id: int
    role: str
    snippet: str
    created_at: str


def fts5_safe_query(q: str) -> str:
    """Те же правила что в routes/search._fts5_safe_query.

    Дублирую здесь чтобы избежать impedance routes ↔ orchestrator.
    """
    cleaned = re.sub(r'[\"\\]', '', q)
    cleaned = cleaned.replace("'", "''")
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    if not tokens:
        return '""'
    return " AND ".join(f'"{t}"*' for t in tokens)


async def discovery_search(
    db: aiosqlite.Connection,
    q: str,
    *,
    channel_id: str | None = None,
    limit: int = 20,
) -> list[SearchHit]:
    """Top-N hits грубо по релевантности."""
    safe = fts5_safe_query(q)
    if channel_id:
        sql = """
            SELECT m.id, m.session_id, s.title, s.channel_id, m.role, m.created_at,
                   snippet(messages_fts, 0, '<mark>', '</mark>', '...', 32)
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            JOIN sessions s ON s.id = m.session_id
            WHERE messages_fts MATCH ? AND s.channel_id = ?
            ORDER BY rank
            LIMIT ?
        """
        params: tuple = (safe, channel_id, limit)
    else:
        sql = """
            SELECT m.id, m.session_id, s.title, s.channel_id, m.role, m.created_at,
                   snippet(messages_fts, 0, '<mark>', '</mark>', '...', 32)
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            JOIN sessions s ON s.id = m.session_id
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        params = (safe, limit)

    out: list[SearchHit] = []
    try:
        async with db.execute(sql, params) as cur:
            async for r in cur:
                out.append(
                    SearchHit(
                        message_id=int(r[0]),
                        session_id=str(r[1]),
                        session_title=str(r[2] or ""),
                        channel_id=str(r[3] or ""),
                        role=str(r[4] or ""),
                        created_at=str(r[5] or ""),
                        snippet=str(r[6] or ""),
                    )
                )
    except sqlite3.OperationalError as exc:
        if "no such module: fts5" in str(exc).lower():
            logger.error("FTS5 недоступен")
            return []
        raise
    return out


async def deep_search(
    db: aiosqlite.Connection,
    session_id: str,
    q: str,
    *,
    window: int = DEEP_WINDOW,
) -> list[SearchHit]:
    """Ищет внутри одной сессии + возвращает окно ±N сообщений вокруг матчей.

    Алгоритм:
    1. Найти message_id матчей (FTS5).
    2. Для каждого — взять окно [id-window … id+window] non-FTS.
    3. Слить, дедупицировать, отсортировать по created_at asc.
    """
    safe = fts5_safe_query(q)
    matches: list[int] = []
    try:
        async with db.execute(
            """
            SELECT m.id FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            WHERE messages_fts MATCH ? AND m.session_id = ?
            ORDER BY m.id
            """,
            (safe, session_id),
        ) as cur:
            async for r in cur:
                matches.append(int(r[0]))
    except sqlite3.OperationalError as exc:
        if "no such module: fts5" in str(exc).lower():
            return []
        raise

    if not matches:
        return []

    # Соберём id-окна.
    id_set: set[int] = set()
    for mid in matches:
        for d in range(-window, window + 1):
            id_set.add(mid + d)

    if not id_set:
        return []

    # Достанем messages по id_set, в пределах session_id.
    placeholders = ",".join("?" * len(id_set))
    sql = f"""
        SELECT m.id, m.session_id, s.title, s.channel_id, m.role, m.created_at,
               SUBSTR(m.content, 1, 400) AS snippet
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE m.session_id = ? AND m.id IN ({placeholders})
        ORDER BY m.created_at ASC, m.id ASC
    """
    params = (session_id, *sorted(id_set))
    out: list[SearchHit] = []
    async with db.execute(sql, params) as cur:
        async for r in cur:
            out.append(
                SearchHit(
                    message_id=int(r[0]),
                    session_id=str(r[1]),
                    session_title=str(r[2] or ""),
                    channel_id=str(r[3] or ""),
                    role=str(r[4] or ""),
                    created_at=str(r[5] or ""),
                    snippet=str(r[6] or ""),
                )
            )
    return out


async def cross_search(
    db: aiosqlite.Connection,
    q: str,
    *,
    channel_id: str | None = None,
    limit_per_session: int = 3,
    max_sessions: int = 30,
) -> dict[str, list[SearchHit]]:
    """Все matches across all sessions, агрегированные по session_id.

    Returns:
        dict session_id → list[SearchHit] (отсортированный по created_at).
    """
    hits = await discovery_search(
        db, q, channel_id=channel_id, limit=max_sessions * limit_per_session * 3
    )

    grouped: dict[str, list[SearchHit]] = {}
    for hit in hits:
        grouped.setdefault(hit.session_id, []).append(hit)

    # Кап на сессию.
    for sid in list(grouped.keys()):
        grouped[sid] = sorted(grouped[sid], key=lambda h: h.created_at)[:limit_per_session]

    # Кап на общее число сессий — сохраняем top-N по сумме hit'ов.
    if len(grouped) > max_sessions:
        sorted_ids = sorted(grouped.items(), key=lambda kv: len(kv[1]), reverse=True)
        grouped = dict(sorted_ids[:max_sessions])

    return grouped
