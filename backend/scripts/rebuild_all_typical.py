"""Полный rebuild всех типовых конфигураций (M-K2.5 audit fix).

Запускает последовательно graph_pilot + cards_pilot для каждой
загруженной типовой. Использует исправленный _discover_modules
(включает Form Module + Command Module).

Запуск:
    cd backend
    python -m scripts.rebuild_all_typical
"""

from __future__ import annotations

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
    CardStatus,
    MockLLMCaller,
    PROMPT_VERSION,
    build_card_context,
    build_typical_graph,
    generate_card_for_channel,
    get_configuration_by_channel,
    get_existing_source_hash,
    list_configurations,
    upsert_card,
)
from app.knowledge.graph_storage import list_nodes  # noqa: E402
from app.knowledge.typical.storage import (  # noqa: E402
    ConfigurationStatus,
    IndexingPhase,
    IndexingRunStatus,
    create_run,
    update_configuration_status,
    update_run_progress,
)
from app.storage.migrations import apply_migrations  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rebuild")

DB_PATH = Path("C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db")


async def _ensure_db() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(str(DB_PATH))
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA synchronous = NORMAL")
    await apply_migrations(conn)
    return conn


def _progress(phase: str, current: int, total: int) -> None:
    pct = (current / total * 100) if total else 0.0
    logger.info("  %s: %d/%d (%.1f%%)", phase, current, total, pct)


async def rebuild_graph(db: aiosqlite.Connection, channel_id: str) -> dict:
    config = await get_configuration_by_channel(db, channel_id)
    snapshot_root = Path(config.source_path)
    if not snapshot_root.exists():
        raise SystemExit(f"snapshot {snapshot_root} не существует")

    logger.info("=== GRAPH BUILD: %s (%s %s) ===",
                channel_id, config.config_kind, config.config_version)

    run = await create_run(db, config.id, IndexingPhase.GRAPH)
    await update_run_progress(db, run.id, status=IndexingRunStatus.IN_PROGRESS)

    t0 = time.perf_counter()
    try:
        stats = await build_typical_graph(
            db, channel_id=channel_id, snapshot_root=snapshot_root,
            progress_callback=_progress,
        )
    except Exception as exc:
        await update_run_progress(
            db, run.id, status=IndexingRunStatus.FAILED,
            error=f"{type(exc).__name__}: {exc}", finished=True,
        )
        raise
    duration = time.perf_counter() - t0

    await update_run_progress(
        db, run.id, status=IndexingRunStatus.COMPLETED,
        items_total=stats.bsl_files_parsed,
        items_processed=stats.bsl_files_parsed,
        metadata_patch={"stats": stats.to_dict(), "duration_seconds": round(duration, 1)},
        finished=True,
    )
    await update_configuration_status(db, channel_id, ConfigurationStatus.GRAPH_BUILT)

    total_n = await count_nodes(db, channel_id)
    total_e = await count_edges(db, channel_id)
    logger.info("  DONE: nodes=%d edges=%d duration=%.1fs", total_n, total_e, duration)
    return {
        "channel_id": channel_id,
        "duration_seconds": round(duration, 1),
        "total_nodes": total_n,
        "total_edges": total_e,
        "bsl_files_parsed": stats.bsl_files_parsed,
        "methods_extracted": stats.methods_extracted,
        "by_node_kind": stats.by_node_kind,
        "by_edge_kind": stats.by_edge_kind,
    }


async def rebuild_cards(db: aiosqlite.Connection, channel_id: str) -> dict:
    logger.info("=== CARDS BUILD: %s ===", channel_id)
    config = await get_configuration_by_channel(db, channel_id)

    nodes = await list_nodes(
        db, channel_id=channel_id, node_kind="MetadataObject", limit=100_000,
    )
    total = len(nodes)
    llm = MockLLMCaller()

    generated = 0
    failed = 0
    t0 = time.perf_counter()

    for i, node in enumerate(nodes, start=1):
        qname = node.qualified_name
        try:
            ctx = await build_card_context(
                db, channel_id=channel_id, object_qualified_name=qname,
            )
            if ctx is None:
                failed += 1
                continue

            source_hash = ctx.compute_source_hash()
            existing = await get_existing_source_hash(
                db, channel_id=channel_id, object_qualified_name=qname,
            )
            if existing == source_hash:
                continue  # skip-если-неизменился

            result = await generate_card_for_channel(
                context=ctx, channel_id=channel_id, llm=llm,
            )
            await upsert_card(
                db, card=result.card, source_hash=source_hash,
                prompt_version=PROMPT_VERSION, llm_model=result.model,
                token_usage_in=result.tokens_in,
                token_usage_out=result.tokens_out,
                status=CardStatus.GENERATED,
            )
            generated += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("FAIL %s: %s", qname, exc)
            failed += 1

        if i % 2000 == 0:
            logger.info("  cards: %d/%d", i, total)

    duration = time.perf_counter() - t0
    logger.info("  DONE: generated=%d failed=%d duration=%.1fs",
                generated, failed, duration)
    return {
        "channel_id": channel_id,
        "objects_total": total,
        "generated": generated,
        "failed": failed,
        "duration_seconds": round(duration, 1),
    }


async def main():
    db = await _ensure_db()
    try:
        configs = await list_configurations(db)
        # Сортируем по размеру (БП самая маленькая → проверим fix быстрее)
        channels_in_order = ["_bp30_138_24", "_ut115_17_226", "_ka2_25_92", "_erp25_21_118"]
        channels_in_db = {c.channel_id for c in configs}
        targets = [ch for ch in channels_in_order if ch in channels_in_db]

        graph_results: list[dict] = []
        cards_results: list[dict] = []

        # Phase A: все графы последовательно
        for ch in targets:
            r = await rebuild_graph(db, ch)
            graph_results.append(r)

        # Phase B: все карточки
        for ch in targets:
            r = await rebuild_cards(db, ch)
            cards_results.append(r)

        summary = {
            "graphs": graph_results,
            "cards": cards_results,
        }
        print()
        print("=" * 60)
        print("REBUILD SUMMARY (with form modules)")
        print("=" * 60)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
