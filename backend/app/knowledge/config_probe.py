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
    concurrency: int = 10,
) -> set[str]:
    """Параллельно пробит присутствие каждого маркера через MCP get_metadata.

    Для каждого маркера «Тип.Имя» делает targeted-пробу name_mask=<Имя>,
    limit=5 и считает маркер присутствующим, если среди результатов есть точное
    совпадение object_path. ~40 проб с ограничением параллелизма — sub-second
    суммарно на локальном MCP (эмпирика КА Демо :6012).

    Никогда не бросает наружу: пробы — best-effort; маркер, чья проба упала,
    считается отсутствующим (детекция деградирует консервативно).
    """
    sem = asyncio.Semaphore(concurrency)
    present: set[str] = set()

    async def probe(marker: str) -> None:
        short_name = marker.split(".")[-1]
        async with sem:
            try:
                objs = await live_metadata_suggest(
                    mcp_endpoint, short_name, 5, anon_headers=anon_headers,
                )
            except Exception:  # noqa: BLE001 — best-effort граница пробы
                return
        if any(o.object_path == marker for o in objs):
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
