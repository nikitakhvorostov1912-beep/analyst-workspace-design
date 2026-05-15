"""GET /search — полнотекстовый поиск по messages через FTS5."""

import logging
import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models import SearchResponse, SearchResultItem

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])


def _get_db(request: Request):
    return request.app.state.db


def _fts5_safe_query(q: str) -> str:
    """Экранирует FTS5 специальные символы и добавляет prefix-matching.

    - Удаляет двойные кавычки и обратные слеши (опасные в FTS5 синтаксисе)
    - Экранирует одиночные кавычки: ' → ''
    - Если несколько слов — объединяет через AND
    - Добавляет * для prefix-matching к каждому токену
    """
    # Удаляем символы, ломающие FTS5 query parser
    cleaned = re.sub(r'[\"\\]', '', q)
    # Экранируем одиночные кавычки
    cleaned = cleaned.replace("'", "''")
    # Разбиваем на токены и добавляем prefix *
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    if not tokens:
        return '""'
    return " AND ".join(f'"{t}"*' for t in tokens)


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=2, max_length=200),
    channel: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db=Depends(_get_db),
) -> SearchResponse:
    """Полнотекстовый поиск по messages через FTS5 virtual table.

    Параметры:
        q: строка поиска (мин. 2 символа, макс. 200)
        channel: фильтр по channel_id сессии (опционально)
        limit: макс. количество результатов (1–50, дефолт 20)

    Возвращает список совпадений с HTML snippet (теги <mark>).
    503 если FTS5 недоступен в сборке sqlite.
    """
    safe_q = _fts5_safe_query(q)

    if channel is not None:
        sql = """
            SELECT
                f.session_id,
                s.title AS session_title,
                f.message_id,
                snippet(messages_fts, 0, '<mark>', '</mark>', '...', 32) AS snippet,
                m.created_at,
                s.channel_id
            FROM messages_fts f
            JOIN messages m ON m.id = f.message_id
            JOIN sessions s ON s.id = f.session_id
            WHERE messages_fts MATCH ?
              AND s.channel_id = ?
            ORDER BY rank
            LIMIT ?
        """
        params = (safe_q, channel, limit)
    else:
        sql = """
            SELECT
                f.session_id,
                s.title AS session_title,
                f.message_id,
                snippet(messages_fts, 0, '<mark>', '</mark>', '...', 32) AS snippet,
                m.created_at,
                s.channel_id
            FROM messages_fts f
            JOIN messages m ON m.id = f.message_id
            JOIN sessions s ON s.id = f.session_id
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        params = (safe_q, limit)

    try:
        rows = await db.execute_fetchall(sql, params)
    except Exception as exc:
        # Ловим sqlite3.OperationalError если FTS5 недоступен в сборке
        if "no such module: fts5" in str(exc).lower() or isinstance(exc, sqlite3.OperationalError):
            logger.error("FTS5 недоступен в sqlite build: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="FTS5 недоступен в данной сборке SQLite. Требуется SQLite с FTS5.",
            ) from exc
        raise

    results = [
        SearchResultItem(
            session_id=row[0],
            session_title=row[1],
            message_id=row[2],
            snippet=row[3] or "",
            created_at=str(row[4]),
            channel_id=row[5],
        )
        for row in rows
    ]

    return SearchResponse(results=results, total=len(results), query=q)
