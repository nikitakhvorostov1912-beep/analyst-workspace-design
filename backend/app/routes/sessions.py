"""Sessions CRUD: POST/GET/PATCH/DELETE /sessions.

Plan 2.3 — полный CRUD с группировкой по дате, auto-title в background task.
"""

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from app.models import (
    SessionCreate,
    SessionDetail,
    SessionMessages,
    SessionPatch,
    SessionsGrouped,
)
from app.orchestrator.persistence import (
    delete_session,
    ensure_session,
    get_session,
    get_session_messages,
    list_sessions_grouped,
    update_session_title,
)
from app.storage.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


def _row_to_detail(row: dict) -> SessionDetail:
    return SessionDetail(
        id=row["id"],
        title=row["title"],
        channel_id=row["channel_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post("/sessions", response_model=SessionDetail)
async def create_session(
    body: SessionCreate,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> SessionDetail:
    """Создаёт новую сессию для channel_id."""
    session_id = await ensure_session(
        db,
        session_id=None,
        channel_id=body.channel_id,
        title_seed=body.title or "",
    )

    # Если title передан явно — сразу сохраняем
    if body.title:
        await update_session_title(db, session_id, body.title)

    row = await get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Ошибка создания сессии")

    return _row_to_detail(row)


@router.get("/sessions", response_model=SessionsGrouped)
async def list_sessions(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    channel_id: str | None = None,
) -> SessionsGrouped:
    """Возвращает сессии сгруппированные по дате.

    Response: {today: [...], yesterday: [...], this_week: [...], earlier: [...]}
    Сортировка внутри групп: по updated_at DESC (выполнено в SQL).
    """
    grouped = await list_sessions_grouped(db, channel_id)
    return SessionsGrouped(**grouped)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session_detail(
    session_id: str,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> SessionDetail:
    """Возвращает детали сессии или 404."""
    row = await get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return _row_to_detail(row)


@router.get("/sessions/{session_id}/messages", response_model=SessionMessages)
async def get_messages(
    session_id: str,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> SessionMessages:
    """Возвращает все сообщения сессии в хронологическом порядке.

    Включает tool_calls и cards (десериализованы из JSON).
    Cap 500 сообщений.
    """
    # Проверяем что сессия существует
    row = await get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")

    messages = await get_session_messages(db, session_id)
    return SessionMessages(messages=messages)


@router.delete("/sessions/{session_id}", status_code=204)
async def remove_session(
    session_id: str,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> None:
    """Удаляет сессию и все её сообщения (ON DELETE CASCADE)."""
    deleted = await delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="session not found")


@router.patch("/sessions/{session_id}", response_model=SessionDetail)
async def patch_session(
    session_id: str,
    body: SessionPatch,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> SessionDetail:
    """Переименовывает сессию."""
    updated = await update_session_title(db, session_id, body.title)
    if not updated:
        raise HTTPException(status_code=404, detail="session not found")

    row = await get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")

    return _row_to_detail(row)
