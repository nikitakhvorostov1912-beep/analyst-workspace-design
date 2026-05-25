"""Persistence-слой: запись сообщений, sessions, tool_calls, cards в SQLite."""

import json
import logging
import uuid
from datetime import datetime, timedelta

import aiosqlite

# SEC-3 (M-K0, 2026-05-25): tool_content в БД хранится raw для UI карточек,
# но при загрузке в LLM context — должен sanitize'нуться. Иначе injection
# в полях 1С (комментарий документа = «ignore previous instructions»)
# при первой обработке проходит через scan_sanitize_for_prompt в loop.py,
# но при следующем turn load_history_for_llm подгружает RAW из БД =
# injection активируется как «вторая попытка».
from app.memory.injection_scan import sanitize_for_prompt as scan_sanitize_for_prompt

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
    reasoning_content: str | None = None,
) -> str:
    """Записывает assistant-сообщение со списком tool_calls и cards.

    Args:
        reasoning_content: цепь рассуждений thinking-модели (Xiaomi MiMo, DeepSeek R1).
            Сохраняется чтобы при загрузке истории вернуть API — иначе MiMo
            отдаёт 400 «reasoning_content in thinking mode must be passed back».

    Returns:
        message_id нового сообщения.
    """
    message_id = str(uuid.uuid4())
    tool_calls_json = json.dumps(tool_calls, ensure_ascii=False)
    cards_json = json.dumps(cards, ensure_ascii=False)
    await db.execute(
        "INSERT INTO messages "
        "(id, session_id, role, content, tool_calls, cards, duration_ms, reasoning_content, created_at) "
        "VALUES (?, ?, 'assistant', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (message_id, session_id, content, tool_calls_json, cards_json, duration_ms, reasoning_content),
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


# --- Sessions CRUD (Plan 2.3) ---


def _parse_updated_at(value: str) -> datetime:
    """Парсит ISO-строку или SQLite TIMESTAMP в datetime."""
    # SQLite хранит как 'YYYY-MM-DD HH:MM:SS' или ISO
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    # Fallback — текущее время
    logger.warning("Не удалось распарсить дату: %s", value)
    return datetime.now()


async def list_sessions_grouped(
    db: aiosqlite.Connection,
    channel_id: str | None = None,
) -> dict:
    """Возвращает сессии сгруппированные по дате (today/yesterday/this_week/earlier).

    Группировка выполняется в Python с datetime.now() (локальное время сервера).
    """
    rows = await db.execute_fetchall(
        """
        SELECT s.id, s.title, s.channel_id, s.updated_at,
               (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count
        FROM sessions s
        WHERE (? IS NULL OR s.channel_id = ?)
        ORDER BY s.updated_at DESC
        """,
        (channel_id, channel_id),
    )

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=7)

    result: dict = {"today": [], "yesterday": [], "this_week": [], "earlier": []}

    for row in rows:
        session_id, title, ch_id, updated_at_raw, message_count = row
        updated_at = _parse_updated_at(str(updated_at_raw))

        item = {
            "id": session_id,
            "title": title,
            "channel_id": ch_id,
            "updated_at": updated_at,
            "message_count": int(message_count),
        }

        if updated_at >= today_start:
            result["today"].append(item)
        elif updated_at >= yesterday_start:
            result["yesterday"].append(item)
        elif updated_at >= week_start:
            result["this_week"].append(item)
        else:
            result["earlier"].append(item)

    return result


async def get_session(
    db: aiosqlite.Connection,
    session_id: str,
) -> dict | None:
    """Возвращает данные сессии или None если не найдена."""
    rows = await db.execute_fetchall(
        "SELECT id, title, channel_id, created_at, updated_at FROM sessions WHERE id = ?",
        (session_id,),
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "id": row[0],
        "title": row[1],
        "channel_id": row[2],
        "created_at": _parse_updated_at(str(row[3])),
        "updated_at": _parse_updated_at(str(row[4])),
    }


async def get_session_messages(
    db: aiosqlite.Connection,
    session_id: str,
) -> list[dict]:
    """Возвращает все сообщения сессии в хронологическом порядке (ASC).

    tool_calls и cards десериализуются из JSON.
    Cap 500 сообщений на сессию.
    """
    rows = await db.execute_fetchall(
        """
        SELECT id, role, content, tool_calls, cards, duration_ms, created_at
        FROM messages
        WHERE session_id = ?
        ORDER BY created_at ASC
        LIMIT 500
        """,
        (session_id,),
    )

    result = []
    for row in rows:
        msg_id, role, content, tool_calls_raw, cards_raw, duration_ms, created_at_raw = row

        tool_calls = None
        if tool_calls_raw:
            try:
                tool_calls = json.loads(tool_calls_raw)
            except (json.JSONDecodeError, TypeError):
                tool_calls = None

        cards = None
        if cards_raw:
            try:
                cards = json.loads(cards_raw)
            except (json.JSONDecodeError, TypeError):
                cards = None

        result.append({
            "id": msg_id,
            "role": role,
            "content": content,
            "tool_calls": tool_calls,
            "cards": cards,
            "duration_ms": duration_ms,
            "created_at": _parse_updated_at(str(created_at_raw)),
        })

    return result


async def delete_session(
    db: aiosqlite.Connection,
    session_id: str,
) -> bool:
    """Удаляет сессию (CASCADE удалит messages автоматически).

    Returns:
        True если сессия существовала и удалена, False если не найдена.
    """
    rows = await db.execute_fetchall(
        "SELECT id FROM sessions WHERE id = ?", (session_id,)
    )
    if not rows:
        return False

    await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    await db.commit()
    return True


async def update_session_title(
    db: aiosqlite.Connection,
    session_id: str,
    title: str,
) -> bool:
    """Обновляет title сессии.

    Returns:
        True если сессия найдена и обновлена.
    """
    rows = await db.execute_fetchall(
        "SELECT id FROM sessions WHERE id = ?", (session_id,)
    )
    if not rows:
        return False

    await db.execute(
        "UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (title, session_id),
    )
    await db.commit()
    return True


async def count_session_messages(
    db: aiosqlite.Connection,
    session_id: str,
) -> int:
    """Считает количество сообщений в сессии."""
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) FROM messages WHERE session_id = ?",
        (session_id,),
    )
    return int(rows[0][0]) if rows else 0


async def load_history_for_llm(
    db: aiosqlite.Connection,
    session_id: str,
    *,
    max_messages: int = 30,
    tool_content_cap: int = 8000,
) -> list[dict]:
    """Возвращает историю сессии в OpenAI chat-completions формате.

    Без системного промпта (его добавит вызывающая сторона).
    Сохранённые в БД сообщения конвертируются обратно в формат:
    - {role:'user', content:...}
    - {role:'assistant', content:..., tool_calls:[{id,type,function:{name,arguments}}]}
    - {role:'tool', tool_call_id:..., content:...} — генерируются из
      assistant.tool_calls[].result/error (один tool message на каждый tool_call).

    Аргументы:
        session_id: ID сессии.
        max_messages: оставить только последние N записей из таблицы messages
            (по 1 user или 1 assistant). История tool-результатов раскрывается
            из tool_calls assistant-сообщения и не считается в max_messages.
        tool_content_cap: cap длины каждого tool-результата (байт).
            Старые результаты обрезаются — экономим контекст LLM.

    Returns:
        Список сообщений в порядке возрастания времени.
    """
    # ORDER BY rowid вторичным ключом — гарантирует insertion-order при
    # одинаковых created_at (SQLite TIMESTAMP с гранулярностью 1 секунда).
    # UUID4 в id рандомные — на них полагаться нельзя.
    rows = await db.execute_fetchall(
        """
        SELECT id, role, content, tool_calls, reasoning_content, created_at
        FROM messages
        WHERE session_id = ?
        ORDER BY created_at ASC, rowid ASC
        LIMIT 500
        """,
        (session_id,),
    )

    # Cap по количеству БД-записей. Берём последние max_messages — это сохраняет
    # хронологию и срезает самые старые обмены.
    raw_msgs = list(rows)
    if len(raw_msgs) > max_messages:
        raw_msgs = raw_msgs[-max_messages:]

    out: list[dict] = []
    for row in raw_msgs:
        _msg_id, role, content, tool_calls_raw, reasoning_content, _created_at = row

        if role == "user":
            out.append({"role": "user", "content": content or ""})
            continue

        if role != "assistant":
            # Прочие роли в БД не пишем; на всякий случай пропускаем.
            continue

        # Парсим tool_calls (наш кастомный формат: list[{id,name,args,result,error,duration_ms}])
        tc_list: list[dict] = []
        if tool_calls_raw:
            try:
                parsed = json.loads(tool_calls_raw)
                if isinstance(parsed, list):
                    tc_list = parsed
            except (json.JSONDecodeError, TypeError):
                tc_list = []

        if not tc_list:
            # Простой assistant-ответ без инструментов
            simple_msg: dict = {
                "role": "assistant",
                "content": content or "",
                # MiMo требует reasoning_content в каждом assistant сообщении
                # для thinking-моделей. Пустая строка — для исторических данных.
                "reasoning_content": reasoning_content or "",
            }
            out.append(simple_msg)
            continue

        # Assistant с tool_calls — OpenAI требует:
        # 1) assistant message с tool_calls (function name + arguments JSON-string)
        # 2) tool messages по каждому tool_call с tool_call_id + content
        openai_tool_calls = []
        for tc in tc_list:
            tc_id = tc.get("id", "") or ""
            if not tc_id:
                # Без id вернуть в LLM нельзя — пропускаем
                continue
            openai_tool_calls.append({
                "id": tc_id,
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False),
                },
            })

        if not openai_tool_calls:
            # Все tc_id потеряны — отдадим как обычный assistant без tools
            fallback_msg: dict = {
                "role": "assistant",
                "content": content or "",
                "reasoning_content": reasoning_content or "",
            }
            out.append(fallback_msg)
            continue

        assistant_msg: dict = {
            "role": "assistant",
            "content": content or None,
            "tool_calls": openai_tool_calls,
        }
        # Thinking-модели (Xiaomi MiMo, DeepSeek R1) — reasoning_content
        # обязательно возвращаем; иначе 400 «must be passed back to the API».
        # Для исторических сообщений без сохранённого reasoning ставим пустую
        # строку — MiMo принимает её как «не было размышлений в этом ходе».
        assistant_msg["reasoning_content"] = reasoning_content or ""
        out.append(assistant_msg)

        # Tool messages — по каждому tool_call. Старые результаты сильно
        # обрезаем (tool_content_cap), чтобы не раздувать контекст.
        # SEC-3: ВСЕГДА прогоняем через injection scan ПЕРЕД подачей в LLM —
        # БД хранит raw для UI карточек, но контекст модели должен быть
        # стерилизован независимо от того, что было при первой обработке.
        for tc in tc_list:
            tc_id = tc.get("id", "") or ""
            if not tc_id:
                continue
            result = tc.get("result")
            if result is not None:
                tool_content = json.dumps(result, ensure_ascii=False)
            else:
                tool_content = tc.get("error") or ""
            # SEC-3: sanitize ДО truncate — homoglyph match не должен
            # «съесть» только хвост, обрезанный по cap.
            tool_content = scan_sanitize_for_prompt(tool_content)
            if len(tool_content) > tool_content_cap:
                tool_content = tool_content[:tool_content_cap] + "...truncated"
            out.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": tool_content,
            })

    return out


# --- Card state (Plan 03-04) ---


async def save_card_state(
    db: aiosqlite.Connection,
    *,
    card_id: str,
    session_id: str,
    message_id: str,
    tool_name: str,
    original_args: dict,
    channel_id: str,
    anon_tokens: list[str] | None = None,
    commit: bool = True,
) -> None:
    """Сохраняет состояние карточки для load-more и deanonymize endpoint.

    Args:
        card_id: UUID4 карточки (из payload)
        session_id: ID сессии
        message_id: ID сообщения
        tool_name: имя MCP-инструмента (например 'get_event_log')
        original_args: исходные аргументы вызова инструмента
        channel_id: ID MCP-подключения
        anon_tokens: список anon-токенов найденных в payload (опциональный, v4)
        commit: BE-6 (M-K0.2) — если False, не делать commit (caller сам коммитит
            батчем). По умолчанию True для backward compat.
    """
    anon_tokens_json = json.dumps(anon_tokens, ensure_ascii=False) if anon_tokens is not None else None
    await db.execute(
        """
        INSERT OR REPLACE INTO card_states
            (card_id, session_id, message_id, tool_name, original_args, channel_id, anon_tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            card_id,
            session_id,
            message_id,
            tool_name,
            json.dumps(original_args, ensure_ascii=False),
            channel_id,
            anon_tokens_json,
        ),
    )
    if commit:
        await db.commit()


async def get_card_state(
    db: aiosqlite.Connection,
    card_id: str,
) -> dict | None:
    """Возвращает состояние карточки по card_id или None если не найдено."""
    rows = await db.execute_fetchall(
        "SELECT card_id, session_id, message_id, tool_name, original_args, channel_id, created_at "
        "FROM card_states WHERE card_id = ?",
        (card_id,),
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "card_id": row[0],
        "session_id": row[1],
        "message_id": row[2],
        "tool_name": row[3],
        "original_args": row[4],
        "channel_id": row[5],
        "created_at": row[6],
    }


async def get_card_anon_tokens(
    db: aiosqlite.Connection,
    card_id: str,
) -> list[str]:
    """Возвращает anon-токены сохранённые для карточки, или пустой список."""
    rows = await db.execute_fetchall(
        "SELECT anon_tokens FROM card_states WHERE card_id = ?",
        (card_id,),
    )
    if not rows or rows[0][0] is None:
        return []
    try:
        return json.loads(rows[0][0])
    except (json.JSONDecodeError, TypeError):
        return []


# --- FTS5 / metadata_cache helpers (Plan 04-03) ---


async def count_fts_rows(db: aiosqlite.Connection) -> int:
    """Возвращает количество строк в messages_fts virtual table."""
    rows = await db.execute_fetchall("SELECT COUNT(*) FROM messages_fts")
    return int(rows[0][0]) if rows else 0


async def count_metadata_cache_rows(
    db: aiosqlite.Connection,
    channel_id: str,
) -> int:
    """Возвращает количество записей в metadata_cache для channel_id."""
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) FROM metadata_cache WHERE channel_id = ?",
        (channel_id,),
    )
    return int(rows[0][0]) if rows else 0
