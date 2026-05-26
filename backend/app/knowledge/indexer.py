"""Metadata Indexer — bulk-refresh metadata_cache из MCP get_metadata.

M-K2.1: первая фаза Knowledge Foundation. Вытаскиваем bulk-refresh
из inline-кода `connections.metadata_suggest` (lines 494-543) в reusable
pure-функцию.

**Зачем reusable модуль:**
- M-K2.2 будет строить state machine (`index_runs` table) и endpoint
  `POST /knowledge/{ch}/index/start` поверх этой функции — без HTTP-обвязки.
- M-K2.3 (incremental update) переиспользует normalize/dispatch логику.
- DRY: `metadata_suggest` сейчас сам нормализует объекты — этот код будет
  заменён вызовом `bulk_refresh_metadata_cache()`.

**Что делает `bulk_refresh_metadata_cache()`:**
1. Вызывает `MCPClient.call_tool("get_metadata", {"detail": False})`
2. Парсит результат в list[NormalizedMetadata] через `_parse_metadata_result`
3. Транзакционно: DELETE + INSERT batch в `metadata_cache`
4. Возвращает IndexerProgress с метриками

**Чего НЕ делает (M-K2.2+):**
- Не управляет state machine (pending → running → done | failed)
- Не пишет в `index_runs` (этой таблицы пока нет — миграция v12)
- Не emit'ит SSE прогресс
- Не делает incremental update (только full re-index)
- Не работает background — синхронный вызов под управлением caller'а
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from app.clients.mcp import MCPClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NormalizedMetadata:
    """Одна запись метаданных в нормализованном виде.

    После парсинга MCP-ответа все варианты ключей (`Name`/`name`,
    `Synonym`/`presentation`, `path`/`full_path`) сводятся к этой
    единой форме. Дальше идёт прямо в `metadata_cache` INSERT.
    """

    object_path: str  # «Документ.ОПП»
    object_type: str  # «Документ»
    name: str         # «ОПП»
    presentation: str | None  # «Отгрузка под перевозку» | None

    def as_cache_row(self, channel_id: str) -> tuple[str, str, str, str, str | None]:
        """Возвращает tuple для INSERT в `metadata_cache` (5 первых колонок)."""
        return (
            channel_id,
            self.object_path,
            self.object_type,
            self.name,
            self.presentation,
        )


@dataclass(frozen=True, slots=True)
class IndexerProgress:
    """Метрики и итог одной indexing-run.

    Иммутабельный результат — caller может сохранить в `index_runs`
    table (M-K2.2) или просто залогировать.

    Attrs:
        channel_id: канал на котором выполнялся indexing
        objects_total: сколько объектов вернул MCP get_metadata
        objects_written: сколько успешно записано в кеш
        objects_skipped: сколько пропущено (невалидные / без path)
        duration_ms: общее время indexing run в миллисекундах
        started_at / finished_at: ISO timestamp границ run
        status: 'done' | 'failed' (running — только в state machine M-K2.2)
        error: текст ошибки если status='failed', иначе None
    """

    channel_id: str
    objects_total: int
    objects_written: int
    objects_skipped: int
    duration_ms: int
    started_at: str
    finished_at: str
    status: str  # 'done' | 'failed'
    error: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == "done"


class IndexerError(Exception):
    """Indexer не смог выполнить full refresh.

    Caller (HTTP route или background task) переоборачивает в
    подходящий response код / SSE error event.
    """


def _normalize_metadata_object(obj: dict[str, Any]) -> NormalizedMetadata | None:
    """Нормализует один объект из MCP-ответа к `NormalizedMetadata`.

    Возвращает None если объект невалидный (нет name + type — невозможно
    построить object_path). Логирует на debug-уровне.

    Поддерживаемые синонимы ключей (унаследовано из existing code):
    - name / Name
    - type / object_type / Type
    - presentation / synonym / Synonym
    - full_path / path
    """
    name = str(obj.get("name") or obj.get("Name") or "").strip()
    obj_type = str(
        obj.get("type") or obj.get("object_type") or obj.get("Type") or ""
    ).strip()

    if not name and not obj_type:
        return None

    # full_path может быть явно задан, иначе собираем из type + name
    full_path = str(obj.get("full_path") or obj.get("path") or "").strip()
    if not full_path:
        if obj_type and name:
            full_path = f"{obj_type}.{name}"
        elif name:
            full_path = name
        else:
            return None

    presentation_raw = obj.get("presentation") or obj.get("synonym") or obj.get("Synonym")
    presentation = str(presentation_raw).strip() if presentation_raw else None

    return NormalizedMetadata(
        object_path=full_path,
        object_type=obj_type,
        name=name or full_path.rsplit(".", 1)[-1],
        presentation=presentation or None,
    )


def parse_metadata_result(result: object) -> list[NormalizedMetadata]:
    """Извлекает list[NormalizedMetadata] из MCP-ответа `get_metadata`.

    MCP-формат varies — обрабатываем известные варианты:
    - `list[dict]` напрямую
    - `dict` обёрнутый в `{"content": [...]}` / `{"objects": [...]}` /
      `{"items": [...]}` / `{"result": [...]}`
    - `str` с JSON внутри
    - MCP wrap `{"content": [{"type": "text", "text": "<json>"}]}`

    Невалидные / повреждённые items пропускаются (с debug-log).
    """
    if isinstance(result, list):
        return [
            normalized
            for item in result
            if isinstance(item, dict)
            and (normalized := _normalize_metadata_object(item)) is not None
        ]

    if isinstance(result, dict):
        # MCP wrap {"content": [{"type": "text", "text": "<json>"}]}
        content = result.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    try:
                        parsed = json.loads(text)
                        return parse_metadata_result(parsed)
                    except (json.JSONDecodeError, TypeError):
                        continue

        # Прямые wrap-ключи
        for key in ("content", "objects", "items", "result"):
            value = result.get(key)
            if isinstance(value, list):
                return [
                    normalized
                    for item in value
                    if isinstance(item, dict)
                    and (normalized := _normalize_metadata_object(item)) is not None
                ]

        # Одиночный объект как dict
        normalized = _normalize_metadata_object(result)
        return [normalized] if normalized else []

    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return []
        return parse_metadata_result(parsed)

    return []


async def write_cache_batch(
    db: aiosqlite.Connection,
    channel_id: str,
    objects: list[NormalizedMetadata],
    *,
    replace_existing: bool = True,
) -> int:
    """Записывает batch объектов в `metadata_cache` транзакционно.

    Args:
        db: aiosqlite connection (caller владеет жизненным циклом)
        channel_id: канал — namespace в metadata_cache
        objects: что писать
        replace_existing: True — DELETE WHERE channel_id перед INSERT (full refresh).
                          False — INSERT OR REPLACE (incremental, sparse update).

    Returns:
        Количество фактически записанных строк (== len(objects)).

    Транзакция: один COMMIT в конце. На SQLAlchemy/aiosqlite это атомарно —
    либо все строки видны другим сессиям, либо ни одной.
    """
    if replace_existing:
        await db.execute(
            "DELETE FROM metadata_cache WHERE channel_id = ?",
            (channel_id,),
        )

    insert_sql = """
        INSERT OR REPLACE INTO metadata_cache
            (channel_id, object_path, object_type, name, presentation, fetched_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """
    rows = [obj.as_cache_row(channel_id) for obj in objects]
    if rows:
        await db.executemany(insert_sql, rows)
    await db.commit()
    return len(rows)


async def bulk_refresh_metadata_cache(
    db: aiosqlite.Connection,
    channel_id: str,
    mcp_endpoint: str,
    *,
    anon_headers: dict[str, str] | None = None,
) -> IndexerProgress:
    """Full-refresh metadata_cache для канала через MCP `get_metadata`.

    Шаги:
    1. Connect MCP → initialize → list_tools
    2. Проверить что `get_metadata` exposed
    3. Call get_metadata(detail=False) → parse → normalize
    4. Транзакционно DELETE + INSERT batch
    5. Вернуть `IndexerProgress`

    Args:
        db: aiosqlite connection
        channel_id: канал (namespace + ID для logging)
        mcp_endpoint: HTTP endpoint MCP (для MCPClient)
        anon_headers: опциональные `X-Anon-Enabled` headers если нужно

    Returns:
        IndexerProgress с метриками. На ошибке возвращается status='failed'
        + error message (не raise — caller сам решает что делать).

    Не raise'ит IndexerError в текущем M-K2.1 — все ошибки попадают в
    IndexerProgress.error. M-K2.2 добавит вариант where эскалация
    нужна (например при попытке двойного запуска).
    """
    started_dt = datetime.now(timezone.utc)
    started_iso = started_dt.isoformat()

    objects: list[NormalizedMetadata] = []
    try:
        async with MCPClient(mcp_endpoint, headers=anon_headers) as client:
            await client.initialize()
            tools = await client.list_tools()
            tool_names = {t.get("name") for t in tools if isinstance(t, dict)}

            if "get_metadata" not in tool_names:
                finished_dt = datetime.now(timezone.utc)
                return IndexerProgress(
                    channel_id=channel_id,
                    objects_total=0,
                    objects_written=0,
                    objects_skipped=0,
                    duration_ms=int((finished_dt - started_dt).total_seconds() * 1000),
                    started_at=started_iso,
                    finished_at=finished_dt.isoformat(),
                    status="failed",
                    error="MCP канал не предоставляет get_metadata tool",
                )

            result = await client.call_tool("get_metadata", {"detail": False})
            objects = parse_metadata_result(result)
    except Exception as exc:  # noqa: BLE001 — индексер — best-effort граница
        logger.exception(
            "bulk_refresh_metadata_cache: MCP call failed для канала %s",
            channel_id,
        )
        finished_dt = datetime.now(timezone.utc)
        return IndexerProgress(
            channel_id=channel_id,
            objects_total=0,
            objects_written=0,
            objects_skipped=0,
            duration_ms=int((finished_dt - started_dt).total_seconds() * 1000),
            started_at=started_iso,
            finished_at=finished_dt.isoformat(),
            status="failed",
            error=f"MCP вызов не удался: {exc}",
        )

    # Best-effort statistics: parse_metadata_result уже отфильтровал
    # невалидные — мы не знаем точное `skipped`, но можем оценить как 0
    # (валидные = вернувшиеся). Для будущего incremental update сюда же
    # попадут конфликты PRIMARY KEY (channel_id, object_path).
    try:
        written = await write_cache_batch(db, channel_id, objects, replace_existing=True)
    except Exception as exc:  # noqa: BLE001 — SQLite граница
        logger.exception(
            "bulk_refresh_metadata_cache: cache write failed для канала %s",
            channel_id,
        )
        finished_dt = datetime.now(timezone.utc)
        return IndexerProgress(
            channel_id=channel_id,
            objects_total=len(objects),
            objects_written=0,
            objects_skipped=0,
            duration_ms=int((finished_dt - started_dt).total_seconds() * 1000),
            started_at=started_iso,
            finished_at=finished_dt.isoformat(),
            status="failed",
            error=f"Запись в metadata_cache не удалась: {exc}",
        )

    finished_dt = datetime.now(timezone.utc)
    duration_ms = int((finished_dt - started_dt).total_seconds() * 1000)

    logger.info(
        "Indexer: канал %s — %d объектов записано за %d мс",
        channel_id,
        written,
        duration_ms,
    )

    return IndexerProgress(
        channel_id=channel_id,
        objects_total=len(objects),
        objects_written=written,
        objects_skipped=0,
        duration_ms=duration_ms,
        started_at=started_iso,
        finished_at=finished_dt.isoformat(),
        status="done",
    )
