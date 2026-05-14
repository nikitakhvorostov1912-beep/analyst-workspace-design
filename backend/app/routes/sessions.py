"""POST /sessions — минимальный endpoint создания сессии.

Полный CRUD (GET list/detail, DELETE) — в Plan 2.3.
"""

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.orchestrator.persistence import ensure_session, touch_session
from app.storage.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    channel_id: str = Field(min_length=1)


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None
    channel_id: str
    created_at: str


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> SessionResponse:
    """Создаёт новую сессию для channel_id."""
    session_id = await ensure_session(
        db,
        session_id=None,
        channel_id=request.channel_id,
        title_seed=request.title or "",
    )

    rows = await db.execute_fetchall(
        "SELECT id, title, channel_id, created_at FROM sessions WHERE id = ?",
        (session_id,),
    )
    row = rows[0]
    return SessionResponse(
        id=row[0],
        title=row[1],
        channel_id=row[2],
        created_at=str(row[3]),
    )
