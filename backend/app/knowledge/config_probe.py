"""Live-пробы конфигурации через MCP (Multi-base онбординг, Phase 3).

Слой MCP-I/O поверх ЧИСТОГО config_detection. Детекция = targeted name_mask-пробы
по маркерам (sub-second), без полного индекса метаданных. config_detection при
этом не получает внешних зависимостей (требование дизайна).
"""
from __future__ import annotations

import asyncio
import logging

from app.knowledge.config_detection import (
    KNOWN_CONFIGURATIONS,
    DetectionResult,
    detect_configuration_type,
)
from app.knowledge.indexer import live_metadata_suggest

logger = logging.getLogger(__name__)


# Объединённый набор всех маркеров (характерные ∪ дискриминативные) по всем
# конфигурациям. Это РОВНО те object_path, по которым считается score, поэтому
# детекция по присутствию только этих маркеров даёт те же scores, что и полный
# каталог — но дёшево (targeted-пробы вместо полного индекса).
ALL_MARKERS: frozenset[str] = frozenset(
    obj
    for sig in KNOWN_CONFIGURATIONS
    for obj in (*sig.characteristic_objects, *sig.discriminative_objects)
)


async def collect_marker_presence(
    mcp_endpoint: str,
    *,
    anon_headers: dict[str, str] | None = None,
    concurrency: int = 1,
) -> set[str]:
    """Пробит присутствие каждого маркера через MCP get_metadata (ПОСЛЕДОВАТЕЛЬНО).

    Для каждого маркера «Тип.Имя» делает targeted-пробу name_mask=<Имя>,
    limit=5 и считает маркер присутствующим, если среди результатов есть точное
    совпадение object_path.

    Параллелизм по умолчанию = 1 (последовательно). Причина (эмпирика, F.2
    2026-06-06): 1С MCP Toolkit — это ОДИН однопоточный процесс 1cv8c на сессию.
    Конкурентные пробы перегружают его, часть падает по таймауту, и набор
    найденных маркеров «плавает» между прогонами → нестабильная детекция (КА
    Демо то определялась как КА, то как УТ/«самописная»). Замер на :6012:
    concurrency=1 → 13/13 маркеров стабильно (3/3 одинаково), ≈19с на 45 проб
    (фон — не блокирует чат/запросы); concurrency≥10 → 6-8 маркеров, флак.
    Параметр оставлен — для быстрых/устойчивых MCP-серверов можно поднять.

    Каждая проба — best-effort с 1 ретраем; маркер, чья проба упала дважды,
    считается отсутствующим (детекция деградирует консервативно, наружу не бросает).
    """
    sem = asyncio.Semaphore(concurrency)
    present: set[str] = set()

    async def probe(marker: str) -> None:
        short_name = marker.split(".")[-1]
        async with sem:
            objs = None
            for attempt in range(2):  # 1 ретрай на транзиентный сбой пробы
                try:
                    objs = await live_metadata_suggest(
                        mcp_endpoint, short_name, 5, anon_headers=anon_headers,
                    )
                    break
                except Exception as exc:  # noqa: BLE001 — best-effort граница пробы
                    if attempt == 1:
                        logger.debug("проба маркера %s не удалась: %s", marker, exc)
                        return
        if objs and any(o.object_path == marker for o in objs):
            present.add(marker)

    await asyncio.gather(*(probe(m) for m in ALL_MARKERS))
    return present


async def detect_from_live(
    mcp_endpoint: str,
    *,
    anon_headers: dict[str, str] | None = None,
) -> DetectionResult:
    """Полный live-цикл детекции: пробы маркеров → detect_configuration_type.

    Отвязан от полного индекса (метаданных-каталога). Возвращает DetectionResult
    с margin/confidence — caller применяет gate_decision().
    """
    present = await collect_marker_presence(mcp_endpoint, anon_headers=anon_headers)
    return detect_configuration_type(present)
