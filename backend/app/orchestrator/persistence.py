"""Persistence-слой: запись сообщений, sessions, tool_calls, cards в SQLite."""

import json
import logging
import uuid
from datetime import UTC, datetime

import aiosqlite

logger = logging.getLogger(__name__)


async def ensure_session(
    db: aiosqlite.Connection,
    session_id: str | None,
    channel_id: str,
    title_seed: str,
) -> str:
    """Возвращает существующий или создаёт новый session_id.

    Args:
        session_id: если None — создаём новый UUID4
        channel_id: обязательный идентификатор канала (базы 1С)
        title_seed: первые символы запроса для будущего auto-title
    """
    if session_id is None:
        new_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO sessions (id, title, channel_id, created_at, updated_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (new_id, None, channel_id),
        )
        await db.commit()
        return new_id

    row = await db.execute_fetchall(
        "SELECT id FROM sessions WHERE id = ?", (session_id,)
    )
    if row:
        return session_id

    # Session_id передан, но не существует — создаём с указанным id
    await db.execute(
        "INSERT INTO sessions (id, title, channel_id, created_at, updated_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        (session_id, None, channel_id),
    )
    await db.commit()
    return session_id


async def save_user_message(
    db: aiosqlite.Connection,
    session_id: str,
    content: str,
) -> str:
    """Записывает user-сообщение, возвращает message_id."""
    message_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO messages (id, session_id, role, content, created_at) "
        "VALUES (?, ?, 'user', ?, CURRENT_TIMESTAMP)",
        (message_id, session_id, content),
    )
    await db.commit()
    return message_id


async def save_assistant_message(
    db: aiosqlite.Connection,
    session_id: str,
    content: str,
    tool_calls: list[dict],
    cards: list[dict],
    duration_ms: int,
) -> str:
    """Записывает assistant-сообщение со списком tool_calls и cards.

    Returns:
        message_id нового сообщения.
    """
    message_id = str(uuid.uuid4())
    tool_calls_json = json.dumps(tool_calls, ensure_ascii=False)
    cards_json = json.dumps(cards, ensure_ascii=False)
    await db.execute(
        "INSERT INTO messages "
        "(id, session_id, role, content, tool_calls, cards, duration_ms, created_at) "
        "VALUES (?, ?, 'assistant', ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (message_id, session_id, content, tool_calls_json, cards_json, duration_ms),
    )
    await db.commit()
    return message_id


async def touch_session(db: aiosqlite.Connection, session_id: str) -> None:
    """Обновляет updated_at у сессии."""
    await db.execute(
        "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (session_id,),
    )
    await db.commit()


async def lookup_mcp_endpoint(
    db: aiosqlite.Connection,
    channel_id: str,
) -> str | None:
    """Ищет endpoint MCP-соединения по channel_id.

    Returns:
        URL endpoint или None если не найдено.
    """
    rows = await db.execute_fetchall(
        "SELECT endpoint FROM mcp_connections WHERE id = ?",
        (channel_id,),
    )
    if rows:
        return rows[0][0]
    return None
