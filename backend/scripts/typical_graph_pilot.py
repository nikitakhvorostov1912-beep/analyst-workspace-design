"""Pilot CLI: строит семантический граф поверх уже загруженной типовой.

Запуск:
    cd backend
    python -m scripts.typical_graph_pilot \\
        --channel _bp30_138_24 \\
        --db data/pilot.db

Опционально --bsl-limit N — ограничить количество BSL модулей (для
быстрого smoke). Без лимита парсит все доступные модули.

Что делает:
1. Подключается к pilot.db (создаст таблицы если новая).
2. Находит typical_configurations записи по channel_id.
3. Запускает build_typical_graph(snapshot_root) — Phase B/C/D billder'а.
4. Сохраняет stats в typical_indexing_runs.metadata.
5. Меняет конфиг status на GRAPH_BUILT при успехе.

Печатает сводку в stdout (по типам node/edge + время).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

import aiosqlite

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.knowledge.graph_storage import count_edges, count_nodes  # noqa: E402
from app.knowledge.typical import (  # noqa: E402
    ConfigurationStatus,
    IndexingPhase,
    IndexingRunStatus,
    build_typical_graph,
    create_run,
    get_configuration_by_channel,
    update_configuration_status,
    update_run_progress,
)
from app.storage.migrations import apply_migrations  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("graph_pilot")


async def _ensure_db(db_path: Path) -> aiosqlite.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    await conn.execute("PRAGMA foreign_keys = ON")
    await apply_migrations(conn)
    return conn


def _progress_logger(phase: str, current: int, total: int) -> None:
    pct = (current / total * 100) if total else 0.0
    logger.info("phase=%s progress=%d/%d (%.1f%%)", phase, current, total, pct)


async def run_graph_pilot(
    *,
    channel_id: str,
    db_path: Path,
    bsl_limit: int | None = None,
) -> dict:
    db = await _ensure_db(db_path)
    try:
        config = await get_configuration_by_channel(db, channel_id)
        if config is None:
            raise SystemExit(f"channel_id {channel_id!r} не найден в БД {db_path}")
        if not config.source_path:
            raise SystemExit(f"config #{config.id} не имеет source_path — нечего парсить")

        snapshot_root = Path(config.source_path)
        if not snapshot_root.exists():
            raise SystemExit(f"source_path не существует на диске: {snapshot_root}")

        logger.info(
            "Building graph for channel=%s kind=%s version=%s",
            config.channel_id, config.config_kind, config.config_version,
        )
        logger.info("Snapshot root: %s", snapshot_root)
        if bsl_limit is not None:
            logger.info("BSL limit: %d", bsl_limit)

        # Phase GRAPH в журнале runs
        run = await create_run(db, config.id, IndexingPhase.GRAPH)
        await update_run_progress(db, run.id, status=IndexingRunStatus.IN_PROGRESS)

        t0 = time.perf_counter()
        try:
            stats = await build_typical_graph(
                db,
                channel_id=config.channel_id,
                snapshot_root=snapshot_root,
                bsl_file_limit=bsl_limit,
                progress_callback=_progress_logger,
            )
        except Exception as exc:
            await update_run_progress(
                db, run.id,
                status=IndexingRunStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
                finished=True,
            )
            await update_configuration_status(
                db, config.channel_id, ConfigurationStatus.FAILED,
            )
            raise
        duration = time.perf_counter() - t0

        # Финальный итог в run.metadata
        metadata_payload = {
            "stats": stats.to_dict(),
            "duration_seconds": round(duration, 3),
            "bsl_limit": bsl_limit,
        }
        await update_run_progress(
            db, run.id,
            status=IndexingRunStatus.COMPLETED,
            items_total=stats.bsl_files_parsed + stats.bsl_files_failed + stats.bsl_files_skipped,
            items_processed=stats.bsl_files_parsed,
            metadata_patch=metadata_payload,
            finished=True,
        )

        await update_configuration_status(
            db, config.channel_id, ConfigurationStatus.GRAPH_BUILT,
        )

        total_nodes = await count_nodes(db, config.channel_id)
        total_edges = await count_edges(db, config.channel_id)
        logger.info(
            "DONE channel=%s nodes=%d edges=%d duration=%.1fs",
            config.channel_id, total_nodes, total_edges, duration,
        )

        return {
            "channel_id": config.channel_id,
            "config_kind": config.config_kind,
            "config_version": config.config_version,
            "stats": stats.to_dict(),
            "total_nodes": total_nodes,
            "total_edges": total_edges,
        }
    finally:
        await db.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Прогон семантического графа поверх загруженной типовой"
    )
    parser.add_argument(
        "--channel", required=True,
        help="channel_id типовой в pilot.db (например _bp30_138_24)",
    )
    parser.add_argument(
        "--db", default="data/pilot.db",
        help="Путь к SQLite БД (default: data/pilot.db)",
    )
    parser.add_argument(
        "--bsl-limit", type=int, default=None,
        help="Лимит BSL модулей (default: все)",
    )
    args = parser.parse_args()

    result = asyncio.run(
        run_graph_pilot(
            channel_id=args.channel,
            db_path=Path(args.db),
            bsl_limit=args.bsl_limit,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
