"""Admin endpoints — privacy escape hatches.

Phase 9.1: POST /admin/reset-local-db — очищает все данные пользовательских
сессий (messages, sessions, card_states, metadata_cache), сохраняя настройки
подключений (mcp_connections) и LLM (llm_settings).

Requires explicit `X-Confirm-Reset: true` header to prevent accidental calls.
"""

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.storage.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

# Список таблиц, которые очищаются при reset.
# Сохраняем: schema_version, mcp_connections, llm_settings.
RESET_TABLES: tuple[str, ...] = (
    "messages",
    "sessions",
    "card_states",
    "metadata_cache",
)


@router.post("/reset-local-db", status_code=status.HTTP_200_OK)
async def reset_local_db(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    x_confirm_reset: Annotated[
        str,
        Header(
            alias="X-Confirm-Reset",
            description="Должен быть 'true' для защиты от случайных вызовов",
        ),
    ],
) -> dict:
    """Очищает локальные данные сессий, сохраняя настройки подключений.

    Очищаются: messages, sessions, card_states, metadata_cache.
    Сохраняются: mcp_connections, llm_settings, schema_version.

    Returns:
        {"status": "ok", "cleared": [список реально очищенных таблиц]}
    """
    if x_confirm_reset != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid X-Confirm-Reset header (must be 'true')",
        )

    cleared: list[str] = []
    for table in RESET_TABLES:
        try:
            await db.execute(f"DELETE FROM {table}")  # noqa: S608 — table from whitelist
            cleared.append(table)
        except Exception as exc:
            # Таблица может отсутствовать в старой БД (миграции не выполнены)
            logger.warning("reset_table_failed: %s (%s)", table, exc)

    await db.commit()
    logger.info("local_db_reset: cleared=%s", cleared)
    return {"status": "ok", "cleared": cleared}
