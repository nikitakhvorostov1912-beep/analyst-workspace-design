"""Object Dossier — паспорт объекта 1С метаданных.

M-K1.12 + M-K1.13 (L1-2 use case).

Dossier — это **структурированный snapshot** объекта 1С метаданных для
быстрого ответа на вопрос «расскажи про <объект>» в чате.

**Источники данных** (приоритет):
1. `metadata_cache` (миграция v5) — уже накопленный snapshot
2. Если нет в кеше → MCP `get_metadata` через orchestrator
3. Если MCP недоступен → fallback на stale data из cache (если есть)

**Состав dossier:**
- Базовое: name, kind (Документ/Справочник/Регистр*), presentation
- Структура: реквизиты + типы (best-effort, из cache)
- Подсистемы где объект участвует
- Связанные объекты (registrar, leading, references)
- Capabilities — что можно сделать с объектом (через orchestrator)

Это **L1 Metadata layer** — структура без бизнес-логики (бизнес-логика в
L4 Behavioral, M-K3+).

**Не реализует** в M-K1:
- Полное дерево всех реквизитов с типами (это требует deep introspection
  через MCP get_metadata — M-K1.12 minimum: name + kind + presentation)
- Подписки на события (M-K3 через CFE)
- Перехватчики (M-K3 через CFE Activity Stream)

Минимальная useful реализация для M-K1: возвращает то что уже есть в
`metadata_cache` + если запись отсутствует — возвращает `not_found_in_cache`
(caller может вызвать MCP `get_metadata` сам или показать «кеш ещё не
заполнен — выполните /ping»).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiosqlite

from app.knowledge.types import ObjectPath

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ObjectDossier:
    """Паспорт объекта 1С метаданных.

    Иммутабельный snapshot. Создаётся через `get_dossier()` service function.

    Attrs:
        object_path: ObjectPath с разобранным kind + name
        presentation: человеческое представление (e.g. «Заказ покупателя»)
        kind: тип объекта (Документ, Справочник, Регистр*, ...)
        channel_id: канал из которого взят dossier
        fetched_at: когда были данные обновлены в кеше
        attributes: список реквизитов (M-K1 минимально — пустой)
        tabular_sections: табличные части (M-K1 минимально — пустой)
        forms: формы (M-K1 минимально — пустой)
        subscriptions: подписки на события (M-K1 — пустой, заполняется в M-K3 через CFE)
        related_objects: связанные объекты (M-K1 — пустой)
        source: 'cache' | 'mcp' | 'cache_stale' (откуда взяли данные)
    """

    object_path: ObjectPath
    presentation: str | None
    kind: str
    channel_id: str
    fetched_at: datetime | None
    source: str  # 'cache' | 'mcp' | 'cache_stale' | 'not_found'
    attributes: list[dict[str, Any]] = field(default_factory=list)
    tabular_sections: list[dict[str, Any]] = field(default_factory=list)
    forms: list[dict[str, Any]] = field(default_factory=list)
    subscriptions: list[dict[str, Any]] = field(default_factory=list)
    related_objects: list[dict[str, Any]] = field(default_factory=list)


class DossierNotFoundError(Exception):
    """Запрошенный объект не найден ни в кеше, ни через MCP."""


async def get_dossier_from_cache(
    db: aiosqlite.Connection,
    channel_id: str,
    object_path: ObjectPath,
) -> ObjectDossier | None:
    """Читает dossier из metadata_cache (миграция v5).

    Returns:
        ObjectDossier(source='cache') если запись есть, None иначе.
    """
    async with db.execute(
        """
        SELECT object_type, name, presentation, fetched_at
        FROM metadata_cache
        WHERE channel_id = ? AND object_path = ?
        LIMIT 1
        """,
        (channel_id, object_path.full),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    object_type, name, presentation, fetched_at = row
    # fetched_at из SQLite — TEXT (CURRENT_TIMESTAMP) — парсим в datetime
    fetched_dt: datetime | None
    if isinstance(fetched_at, str):
        try:
            fetched_dt = datetime.fromisoformat(fetched_at.replace(" ", "T"))
        except ValueError:
            fetched_dt = None
    elif isinstance(fetched_at, datetime):
        fetched_dt = fetched_at
    else:
        fetched_dt = None

    return ObjectDossier(
        object_path=object_path,
        presentation=presentation,
        kind=object_type or object_path.kind,
        channel_id=channel_id,
        fetched_at=fetched_dt,
        source="cache",
    )


async def get_dossier(
    db: aiosqlite.Connection,
    channel_id: str,
    object_path_raw: str,
) -> ObjectDossier:
    """Возвращает dossier объекта.

    Сейчас (M-K1.13 minimum):
    - Парсит object_path_raw → ObjectPath
    - Читает из metadata_cache
    - Если нет — raise DossierNotFoundError

    В M-K1.14+ будет fallback на MCP get_metadata если кеш пустой.
    В M-K2+ — обогащение через L2/L3 (граф + patterns).

    Args:
        db: aiosqlite connection
        channel_id: канал MCP подключения
        object_path_raw: строка типа 'Документ.ОПП'

    Returns:
        ObjectDossier (source='cache' если найден)

    Raises:
        ValueError: если object_path_raw невалидный
        DossierNotFoundError: если не найден ни в cache ни через MCP
    """
    object_path = ObjectPath.parse(object_path_raw)
    dossier = await get_dossier_from_cache(db, channel_id, object_path)
    if dossier is None:
        raise DossierNotFoundError(
            f"Объект {object_path.full!r} не найден в metadata_cache "
            f"канала {channel_id!r}. Выполните /connections/{channel_id}/ping "
            "или /metadata-suggest для заполнения кеша."
        )
    return dossier


async def fill_cache_entry(
    db: aiosqlite.Connection,
    channel_id: str,
    object_path: str,
    object_type: str,
    name: str,
    presentation: str | None = None,
) -> None:
    """Записывает / обновляет одну запись в metadata_cache.

    M-K1.12: вспомогательный helper для metadata cache filler. Использует
    INSERT OR REPLACE для idempotent backfill.

    NB: реальный massive backfill через MCP get_metadata — задача
    metadata_cache_filler.py (TBD M-K1.12 full). Этот helper — точечная
    запись (e.g. когда LLM запросила объект которого не было в кеше).
    """
    await db.execute(
        """
        INSERT OR REPLACE INTO metadata_cache
            (channel_id, object_path, object_type, name, presentation, fetched_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (channel_id, object_path, object_type, name, presentation),
    )
    await db.commit()
