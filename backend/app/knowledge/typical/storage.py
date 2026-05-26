"""Typical Configurations storage — CRUD для реестра снапшотов и runs.

Соответствует миграции v17 (M-K2.5.0, ADR-003):
- `typical_configurations` — реестр типовых снапшотов
- `typical_indexing_runs` — журнал прогонов индексации

## Lifecycle конфигурации

```
pending  ─ создана запись, источник зафиксирован
   │
extracted ─ DESIGNER /DumpConfigToFiles прошёл, XML дерево готово
   │
parsed ── BSL + queries + metadata разобраны
   │
graph_built ─ 6 графов посчитаны
   │
enriched ── LLM-карточки сгенерированы
   │
ready ─── полностью готов к запросам пользователя
```

Альтернативный финал — `failed`. Переход в `failed` фиксирует ошибку
в `typical_indexing_runs.error` и стопит pipeline.

## Lifecycle прогона (run)

```
pending → in_progress → completed
                      → failed
```
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import aiosqlite

from app.knowledge.typical.registry import (
    DISPLAY_NAMES,
    TypicalConfigKind,
    reserved_channel_id,
)

logger = logging.getLogger(__name__)


class ConfigurationStatus(str, Enum):
    """Статус снапшота типовой конфигурации."""

    PENDING = "pending"
    EXTRACTED = "extracted"
    PARSED = "parsed"
    GRAPH_BUILT = "graph_built"
    ENRICHED = "enriched"
    READY = "ready"
    FAILED = "failed"


class IndexingPhase(str, Enum):
    """Фаза индексационного прогона.

    Каждая фаза материализует один шаг пайплайна и имеет свой
    progress_pct + items_processed/total.
    """

    EXTRACT = "extract"          # .dt → DESIGNER /DumpConfigToFiles
    PARSE_BSL = "parse_bsl"      # BSL модули → AST → DB rows
    PARSE_QUERIES = "parse_queries"
    PARSE_METADATA = "parse_metadata"  # Configuration.xml + дерево XML
    GRAPH = "graph"              # Семантические графы через graph_storage
    CARDS = "cards"              # LLM-карточки
    EMBED = "embed"              # Эмбеддинги карточек в vec_objects


class IndexingRunStatus(str, Enum):
    """Статус одного прогона."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TypicalConfiguration:
    """Реестровая запись о типовой конфигурации.

    Иммутабельная — апдейты через update_configuration_status / delete.
    """

    id: int
    config_kind: str
    config_version: str
    channel_id: str
    display_name: str
    source_path: str | None
    status: str
    indexed_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "config_kind": self.config_kind,
            "config_version": self.config_version,
            "channel_id": self.channel_id,
            "display_name": self.display_name,
            "source_path": self.source_path,
            "status": self.status,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass(frozen=True, slots=True)
class TypicalIndexingRun:
    """Один прогон индексации одной фазы для одной конфигурации."""

    id: int
    config_id: int
    phase: str
    status: str
    progress_pct: int
    items_processed: int
    items_total: int
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "config_id": self.config_id,
            "phase": self.phase,
            "status": self.status,
            "progress_pct": self.progress_pct,
            "items_processed": self.items_processed,
            "items_total": self.items_total,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "metadata": self.metadata,
        }


def _parse_timestamp(value: Any) -> datetime | None:
    """Парсит timestamp из колонки SQLite. None — если NULL."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # SQLite возвращает в формате 'YYYY-MM-DD HH:MM:SS' (CURRENT_TIMESTAMP)
        # либо в ISO формате (если приложение писало datetime.isoformat()).
        try:
            return datetime.fromisoformat(value.replace(" ", "T"))
        except ValueError:
            logger.warning(f"Не удалось распарсить timestamp: {value!r}")
            return None
    return None


def _row_to_configuration(row: aiosqlite.Row) -> TypicalConfiguration:
    """Конвертирует одну строку SQLite в dataclass."""
    return TypicalConfiguration(
        id=row["id"],
        config_kind=row["config_kind"],
        config_version=row["config_version"],
        channel_id=row["channel_id"],
        display_name=row["display_name"],
        source_path=row["source_path"],
        status=row["status"],
        indexed_at=_parse_timestamp(row["indexed_at"]),
        metadata=json.loads(row["metadata"] or "{}"),
        created_at=_parse_timestamp(row["created_at"]),
    )


def _row_to_run(row: aiosqlite.Row) -> TypicalIndexingRun:
    return TypicalIndexingRun(
        id=row["id"],
        config_id=row["config_id"],
        phase=row["phase"],
        status=row["status"],
        progress_pct=row["progress_pct"],
        items_processed=row["items_processed"],
        items_total=row["items_total"],
        error=row["error"],
        started_at=_parse_timestamp(row["started_at"]),
        finished_at=_parse_timestamp(row["finished_at"]),
        metadata=json.loads(row["metadata"] or "{}"),
    )


# ── Configuration CRUD ───────────────────────────────────────────────


async def create_configuration(
    db: aiosqlite.Connection,
    kind: TypicalConfigKind,
    version: str,
    source_path: str | None = None,
    display_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TypicalConfiguration:
    """Создаёт snapshot-запись о типовой конфигурации.

    channel_id вычисляется из (kind, version) автоматически через
    reserved_channel_id() — пользователю не нужно его передавать.

    Если для этой пары (kind, version) запись уже существует — поднимает
    sqlite3.IntegrityError (UNIQUE constraint).
    """
    channel_id = reserved_channel_id(kind, version)
    final_display_name = display_name or f"{DISPLAY_NAMES[kind]} ({version})"
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

    cursor = await db.execute(
        """
        INSERT INTO typical_configurations
            (config_kind, config_version, channel_id, display_name,
             source_path, status, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kind.value,
            version,
            channel_id,
            final_display_name,
            source_path,
            ConfigurationStatus.PENDING.value,
            metadata_json,
        ),
    )
    config_id = cursor.lastrowid
    await db.commit()

    logger.info(
        f"Typical configuration created: kind={kind.value} "
        f"version={version} channel={channel_id} id={config_id}"
    )

    fetched = await get_configuration_by_id(db, config_id)
    if fetched is None:
        raise RuntimeError(f"Failed to fetch just-created configuration id={config_id}")
    return fetched


async def get_configuration_by_id(
    db: aiosqlite.Connection,
    config_id: int,
) -> TypicalConfiguration | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM typical_configurations WHERE id = ?",
        (config_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return _row_to_configuration(row) if row else None


async def get_configuration_by_channel(
    db: aiosqlite.Connection,
    channel_id: str,
) -> TypicalConfiguration | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM typical_configurations WHERE channel_id = ?",
        (channel_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return _row_to_configuration(row) if row else None


async def get_configuration_by_kind_version(
    db: aiosqlite.Connection,
    kind: TypicalConfigKind,
    version: str,
) -> TypicalConfiguration | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        """
        SELECT * FROM typical_configurations
        WHERE config_kind = ? AND config_version = ?
        """,
        (kind.value, version),
    ) as cursor:
        row = await cursor.fetchone()
    return _row_to_configuration(row) if row else None


async def list_configurations(
    db: aiosqlite.Connection,
    kind: TypicalConfigKind | None = None,
    status: ConfigurationStatus | None = None,
) -> list[TypicalConfiguration]:
    """Список снапшотов. Фильтры опциональны."""
    db.row_factory = aiosqlite.Row
    query = "SELECT * FROM typical_configurations WHERE 1=1"
    params: list[Any] = []
    if kind is not None:
        query += " AND config_kind = ?"
        params.append(kind.value)
    if status is not None:
        query += " AND status = ?"
        params.append(status.value)
    query += " ORDER BY config_kind, config_version"

    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    return [_row_to_configuration(r) for r in rows]


async def update_configuration_status(
    db: aiosqlite.Connection,
    channel_id: str,
    status: ConfigurationStatus,
    indexed_at: datetime | None = None,
    metadata_patch: dict[str, Any] | None = None,
) -> bool:
    """Меняет статус конфигурации.

    Если передан `indexed_at` — обновляется (обычно при переходе в `ready`).
    Если передан `metadata_patch` — мержится с существующим JSON metadata.

    Возвращает True если запись была найдена и обновлена.
    """
    db.row_factory = aiosqlite.Row

    if metadata_patch is not None:
        async with db.execute(
            "SELECT metadata FROM typical_configurations WHERE channel_id = ?",
            (channel_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return False
        existing = json.loads(row["metadata"] or "{}")
        existing.update(metadata_patch)
        metadata_json = json.dumps(existing, ensure_ascii=False)
    else:
        metadata_json = None

    sets = ["status = ?"]
    params: list[Any] = [status.value]
    if indexed_at is not None:
        sets.append("indexed_at = ?")
        params.append(indexed_at.isoformat())
    if metadata_json is not None:
        sets.append("metadata = ?")
        params.append(metadata_json)
    params.append(channel_id)

    cursor = await db.execute(
        f"UPDATE typical_configurations SET {', '.join(sets)} WHERE channel_id = ?",
        params,
    )
    await db.commit()
    return cursor.rowcount > 0


async def delete_configuration(
    db: aiosqlite.Connection,
    channel_id: str,
) -> bool:
    """Удаляет снапшот. FK CASCADE снесёт все его runs.

    Возвращает True если запись была найдена и удалена.
    """
    cursor = await db.execute(
        "DELETE FROM typical_configurations WHERE channel_id = ?",
        (channel_id,),
    )
    await db.commit()
    return cursor.rowcount > 0


# ── Indexing Run CRUD ────────────────────────────────────────────────


async def create_run(
    db: aiosqlite.Connection,
    config_id: int,
    phase: IndexingPhase,
    items_total: int = 0,
    metadata: dict[str, Any] | None = None,
) -> TypicalIndexingRun:
    """Создаёт запись о новом прогоне фазы.

    Статус = PENDING. Переход в IN_PROGRESS / COMPLETED / FAILED —
    через update_run_progress() с явным status.
    """
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
    cursor = await db.execute(
        """
        INSERT INTO typical_indexing_runs
            (config_id, phase, status, items_total, metadata)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            config_id,
            phase.value,
            IndexingRunStatus.PENDING.value,
            items_total,
            metadata_json,
        ),
    )
    run_id = cursor.lastrowid
    await db.commit()

    fetched = await get_run_by_id(db, run_id)
    if fetched is None:
        raise RuntimeError(f"Failed to fetch just-created run id={run_id}")
    return fetched


async def get_run_by_id(
    db: aiosqlite.Connection,
    run_id: int,
) -> TypicalIndexingRun | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM typical_indexing_runs WHERE id = ?",
        (run_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return _row_to_run(row) if row else None


async def update_run_progress(
    db: aiosqlite.Connection,
    run_id: int,
    *,
    items_processed: int | None = None,
    progress_pct: int | None = None,
    status: IndexingRunStatus | None = None,
    error: str | None = None,
    finished: bool = False,
    metadata_patch: dict[str, Any] | None = None,
) -> bool:
    """Обновляет прогресс прогона.

    - `items_processed` / `progress_pct` — частичный апдейт счётчиков.
    - `status` — явная смена статуса (PENDING → IN_PROGRESS → ... ).
      При переходе в IN_PROGRESS впервые автоматически выставляется
      started_at = CURRENT_TIMESTAMP, если он был NULL.
    - `finished` = True — выставляет finished_at = CURRENT_TIMESTAMP.
      Используется при переходе в COMPLETED / FAILED.
    - `error` — текст ошибки (для FAILED).
    - `metadata_patch` — мерж с существующим JSON metadata.
    """
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT started_at, metadata FROM typical_indexing_runs WHERE id = ?",
        (run_id,),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return False

    sets: list[str] = []
    params: list[Any] = []

    if items_processed is not None:
        sets.append("items_processed = ?")
        params.append(items_processed)

    if progress_pct is not None:
        sets.append("progress_pct = ?")
        params.append(max(0, min(100, progress_pct)))

    if status is not None:
        sets.append("status = ?")
        params.append(status.value)
        # Auto-fill started_at при первом переходе в IN_PROGRESS
        if status == IndexingRunStatus.IN_PROGRESS and row["started_at"] is None:
            sets.append("started_at = CURRENT_TIMESTAMP")

    if error is not None:
        sets.append("error = ?")
        params.append(error)

    if finished:
        sets.append("finished_at = CURRENT_TIMESTAMP")

    if metadata_patch is not None:
        existing = json.loads(row["metadata"] or "{}")
        existing.update(metadata_patch)
        sets.append("metadata = ?")
        params.append(json.dumps(existing, ensure_ascii=False))

    if not sets:
        return True  # noop

    params.append(run_id)
    cursor = await db.execute(
        f"UPDATE typical_indexing_runs SET {', '.join(sets)} WHERE id = ?",
        params,
    )
    await db.commit()
    return cursor.rowcount > 0


async def list_runs(
    db: aiosqlite.Connection,
    config_id: int,
    phase: IndexingPhase | None = None,
    status: IndexingRunStatus | None = None,
) -> list[TypicalIndexingRun]:
    """Журнал прогонов для конкретной конфигурации.

    Сортируется по started_at DESC (если есть), затем по id DESC.
    """
    db.row_factory = aiosqlite.Row
    query = "SELECT * FROM typical_indexing_runs WHERE config_id = ?"
    params: list[Any] = [config_id]
    if phase is not None:
        query += " AND phase = ?"
        params.append(phase.value)
    if status is not None:
        query += " AND status = ?"
        params.append(status.value)
    query += " ORDER BY COALESCE(started_at, created_at) DESC, id DESC"

    # SQLite требует наличия колонки created_at для COALESCE — но у нас
    # её нет в typical_indexing_runs (нет смысла, started_at достаточно).
    # Используем просто started_at DESC NULLS LAST через CASE.
    query = query.replace(
        "ORDER BY COALESCE(started_at, created_at) DESC, id DESC",
        "ORDER BY CASE WHEN started_at IS NULL THEN 1 ELSE 0 END, started_at DESC, id DESC",
    )

    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    return [_row_to_run(r) for r in rows]
