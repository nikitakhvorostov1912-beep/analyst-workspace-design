"""CRUD для typical_object_cards (M-K2.5.5).

Хранит LLM-генерируемые карточки объектов типовых конфигураций.
Поддерживает idempotent upsert через UNIQUE(channel_id, object_qualified_name)
+ source_hash для skip-если-неизменился.

## Главные операции

- `upsert_card(card, source_hash, ...)` — вставляет или обновляет.
  При совпадении source_hash возвращает existing без изменений.
- `get_card_by_qname` / `list_cards_by_channel` — чтение.
- `delete_cards_by_channel` — каскадная очистка перед re-generation.
- `update_card_status` — смена lifecycle (pending → generated → embedded).
"""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite

from app.knowledge.typical.card_models import (
    CardStatus,
    TypicalObjectCard,
    TypicalObjectCardRecord,
)

logger = logging.getLogger(__name__)


# ── Public API ───────────────────────────────────────────────────────


async def upsert_card(
    db: aiosqlite.Connection,
    *,
    card: TypicalObjectCard,
    source_hash: str,
    prompt_version: str = "v1",
    llm_model: str | None = None,
    token_usage_in: int | None = None,
    token_usage_out: int | None = None,
    status: CardStatus = CardStatus.GENERATED,
    error: str | None = None,
    is_mock: bool = False,
) -> int:
    """Вставляет или обновляет карточку. Возвращает id записи.

    Идемпотентен через UNIQUE(channel_id, object_qualified_name).
    Повторный upsert с тем же source_hash обновит updated_at, но
    payload останется тем же.

    is_mock (M-K2.5.9.2): True для карточек от MockLLMCaller — UI / retrieval
    могут фильтровать или показать warning. Backfill для существующих
    63 197 карточек выполнен в Migration v19.
    """
    if not card.channel_id or not card.object_qualified_name:
        raise ValueError("channel_id и object_qualified_name обязательны")

    payload_json = card.to_payload_json()
    await db.execute(
        """
        INSERT INTO typical_object_cards (
            channel_id, object_qualified_name, object_kind,
            card_payload, source_hash, prompt_version,
            llm_model, token_usage_in, token_usage_out,
            status, error, is_mock, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(channel_id, object_qualified_name) DO UPDATE SET
            object_kind = excluded.object_kind,
            card_payload = excluded.card_payload,
            source_hash = excluded.source_hash,
            prompt_version = excluded.prompt_version,
            llm_model = excluded.llm_model,
            token_usage_in = excluded.token_usage_in,
            token_usage_out = excluded.token_usage_out,
            status = excluded.status,
            error = excluded.error,
            is_mock = excluded.is_mock,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            card.channel_id,
            card.object_qualified_name,
            card.object_kind,
            payload_json,
            source_hash,
            prompt_version,
            llm_model,
            token_usage_in,
            token_usage_out,
            status.value,
            error,
            1 if is_mock else 0,
        ),
    )
    await db.commit()

    cursor = await db.execute(
        """
        SELECT id FROM typical_object_cards
        WHERE channel_id = ? AND object_qualified_name = ?
        """,
        (card.channel_id, card.object_qualified_name),
    )
    row = await cursor.fetchone()
    if row is None:
        raise RuntimeError("upsert_card не вернул id — внутренняя ошибка")
    return int(row[0])


async def get_card_by_qname(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    object_qualified_name: str,
) -> TypicalObjectCardRecord | None:
    """Возвращает карточку или None."""
    cursor = await db.execute(
        """
        SELECT id, channel_id, object_qualified_name, object_kind,
               card_payload, source_hash, prompt_version,
               llm_model, token_usage_in, token_usage_out,
               embedding_model, embedding_dim, status, error,
               created_at, updated_at, is_mock
        FROM typical_object_cards
        WHERE channel_id = ? AND object_qualified_name = ?
        """,
        (channel_id, object_qualified_name),
    )
    row = await cursor.fetchone()
    return _row_to_record(row) if row else None


async def list_cards_by_channel(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    object_kind: str | None = None,
    status: CardStatus | None = None,
    limit: int = 100,
    exclude_mock: bool = False,
) -> list[TypicalObjectCardRecord]:
    """Список карточек канала с опциональными фильтрами.

    exclude_mock (M-K2.5.9.2): True — отфильтровать карточки с is_mock=1
    (mock-сгенерированные через MockLLMCaller). Используется retrieval'ом
    когда нужно ограничиться только верифицированными production-карточками.
    """
    where = ["channel_id = ?"]
    params: list[Any] = [channel_id]

    if object_kind:
        where.append("object_kind = ?")
        params.append(object_kind)
    if status:
        where.append("status = ?")
        params.append(status.value)
    if exclude_mock:
        where.append("is_mock = 0")

    sql = f"""
        SELECT id, channel_id, object_qualified_name, object_kind,
               card_payload, source_hash, prompt_version,
               llm_model, token_usage_in, token_usage_out,
               embedding_model, embedding_dim, status, error,
               created_at, updated_at, is_mock
        FROM typical_object_cards
        WHERE {' AND '.join(where)}
        ORDER BY object_qualified_name
        LIMIT ?
    """
    params.append(limit)

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [_row_to_record(r) for r in rows]


async def get_existing_source_hash(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    object_qualified_name: str,
) -> str | None:
    """Быстрый lookup hash'а existing карточки (для skip-неизменных).

    Возвращает None если карточки ещё нет.
    """
    cursor = await db.execute(
        """
        SELECT source_hash FROM typical_object_cards
        WHERE channel_id = ? AND object_qualified_name = ?
        """,
        (channel_id, object_qualified_name),
    )
    row = await cursor.fetchone()
    return row[0] if row else None


async def update_card_status(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    object_qualified_name: str,
    status: CardStatus,
    error: str | None = None,
    embedding_model: str | None = None,
    embedding_dim: int | None = None,
) -> bool:
    """Обновляет lifecycle / embedding info. Возвращает True если карточка найдена."""
    sets: list[str] = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params: list[Any] = [status.value]

    if error is not None:
        sets.append("error = ?")
        params.append(error)

    if embedding_model is not None:
        sets.append("embedding_model = ?")
        params.append(embedding_model)

    if embedding_dim is not None:
        sets.append("embedding_dim = ?")
        params.append(embedding_dim)

    params.extend([channel_id, object_qualified_name])

    cursor = await db.execute(
        f"""
        UPDATE typical_object_cards SET {', '.join(sets)}
        WHERE channel_id = ? AND object_qualified_name = ?
        """,
        params,
    )
    await db.commit()
    return cursor.rowcount > 0


async def delete_cards_by_channel(
    db: aiosqlite.Connection,
    channel_id: str,
) -> int:
    """Удаляет все карточки канала. Возвращает кол-во."""
    cursor = await db.execute(
        "SELECT COUNT(*) FROM typical_object_cards WHERE channel_id = ?",
        (channel_id,),
    )
    row = await cursor.fetchone()
    count = int(row[0]) if row else 0
    if count == 0:
        return 0

    await db.execute(
        "DELETE FROM typical_object_cards WHERE channel_id = ?",
        (channel_id,),
    )
    await db.commit()
    return count


async def count_cards_by_channel(
    db: aiosqlite.Connection,
    channel_id: str,
) -> dict[str, int]:
    """Возвращает {status: count} для канала."""
    cursor = await db.execute(
        """
        SELECT status, COUNT(*) FROM typical_object_cards
        WHERE channel_id = ?
        GROUP BY status
        """,
        (channel_id,),
    )
    rows = await cursor.fetchall()
    return {r[0]: int(r[1]) for r in rows}


async def count_mock_cards_by_channel(
    db: aiosqlite.Connection,
    channel_id: str,
) -> dict[str, int]:
    """Возвращает {'mock': N, 'verified': M} для канала.

    M-K2.5.9.2: используется UI и LLM tools для понимания «доля production-готовых
    карточек vs mock». Если mock=100%, бот должен честно сказать что данные
    не верифицированы.
    """
    cursor = await db.execute(
        """
        SELECT is_mock, COUNT(*) FROM typical_object_cards
        WHERE channel_id = ?
        GROUP BY is_mock
        """,
        (channel_id,),
    )
    rows = await cursor.fetchall()
    result = {"mock": 0, "verified": 0}
    for is_mock, count in rows:
        key = "mock" if int(is_mock) == 1 else "verified"
        result[key] = int(count)
    return result


# ── Helpers ──────────────────────────────────────────────────────────


def _row_to_record(row: tuple) -> TypicalObjectCardRecord:
    """Маппит SQL-row на TypicalObjectCardRecord."""
    card = TypicalObjectCard.from_payload_json(
        channel_id=row[1],
        object_qualified_name=row[2],
        object_kind=row[3],
        payload_json=row[4] or "{}",
    )
    # Защитный bool: row[16] (is_mock) может быть NULL/0/1 INTEGER из SQLite.
    is_mock_raw = row[16] if len(row) > 16 else 0
    return TypicalObjectCardRecord(
        id=int(row[0]),
        channel_id=row[1],
        object_qualified_name=row[2],
        object_kind=row[3],
        card=card,
        source_hash=row[5],
        prompt_version=row[6],
        llm_model=row[7],
        token_usage_in=row[8],
        token_usage_out=row[9],
        embedding_model=row[10],
        embedding_dim=row[11],
        status=row[12],
        error=row[13],
        created_at=row[14],
        updated_at=row[15],
        is_mock=bool(is_mock_raw),
    )
