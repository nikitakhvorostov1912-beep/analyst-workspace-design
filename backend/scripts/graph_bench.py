"""NIM-safe бенчмарк Knowledge Graph — верификация DoD M-K3.17.1.

Строит семантический граф на реальном снапшоте типовой в ОТДЕЛЬНУЮ временную
БД (НЕ pilot.db — там в фоне крутится NIM rebuild) и меряет:
  - count nodes / edges + разбивка по типам;
  - latency traverse_bfs depth=5 от самого «горячего» узла (median из 7).

Проверяет цели 17.1: ~5K nodes / ~50K edges, traversal ≤300ms.

Запуск:
    cd backend
    python -m scripts.graph_bench \\
        --snapshot data/typical-snapshots/ut115-demotrd \\
        --db data/graph_bench_ut115.db [--bsl-limit N]
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

from app.knowledge.graph_storage import (  # noqa: E402
    count_by_kind,
    count_edges,
    count_nodes,
    traverse_bfs,
)
from app.knowledge.typical import build_typical_graph  # noqa: E402
from app.storage.migrations import apply_migrations  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("graph_bench")

CHANNEL = "_bench"


async def _fresh_db(db_path: str) -> aiosqlite.Connection:
    p = Path(db_path)
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(p) + suffix)
        if f.exists():
            f.unlink()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(p))
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA synchronous = NORMAL")
    await apply_migrations(conn)
    return conn


async def _hot_node(db: aiosqlite.Connection):
    """Узел с максимальной out-степенью — самый тяжёлый случай для traversal."""
    cur = await db.execute(
        "SELECT n.id, n.qualified_name, COUNT(e.id) AS c "
        "FROM graph_nodes n JOIN graph_edges e ON e.src_id = n.id "
        "WHERE n.channel_id = ? GROUP BY n.id ORDER BY c DESC LIMIT 1",
        (CHANNEL,),
    )
    return await cur.fetchone()


async def run(
    snapshot: str, db_path: str, bsl_limit: int | None, traverse_only: bool = False
) -> dict:
    stats = None
    build_s: float | None = None
    if traverse_only:
        # Бенч traversal на УЖЕ построенном графе — без перестройки и без wipe.
        db = await aiosqlite.connect(db_path)
        await db.execute("PRAGMA foreign_keys = ON")
    else:
        db = await _fresh_db(db_path)
    try:
        if not traverse_only:
            t0 = time.perf_counter()
            stats = await build_typical_graph(
                db,
                channel_id=CHANNEL,
                snapshot_root=Path(snapshot),
                bsl_file_limit=bsl_limit,
            )
            build_s = time.perf_counter() - t0

        nodes = await count_nodes(db, CHANNEL)
        edges = await count_edges(db, CHANNEL)
        by_kind = await count_by_kind(db, CHANNEL)

        hot = await _hot_node(db)
        latencies: list[float] = []
        reached = 0
        if hot:
            for _ in range(7):
                ts = time.perf_counter()
                hits = await traverse_bfs(db, hot[0], max_depth=5, direction="out")
                latencies.append((time.perf_counter() - ts) * 1000)
            reached = len(hits)
            latencies.sort()

        def _med(xs: list[float]):
            return round(xs[len(xs) // 2], 1) if xs else None

        result = {
            "snapshot": str(snapshot),
            "bsl_limit": bsl_limit,
            "build_seconds": round(build_s, 1) if build_s is not None else None,
            "nodes": nodes,
            "edges": edges,
            "by_kind": by_kind,
            "stats": stats.to_dict() if stats is not None else None,
            "traversal_depth5": {
                "hot_node": hot[1] if hot else None,
                "out_degree": hot[2] if hot else 0,
                "reached_nodes": reached,
                "latency_ms_median": _med(latencies),
                "latency_ms_min": round(latencies[0], 1) if latencies else None,
                "latency_ms_max": round(latencies[-1], 1) if latencies else None,
            },
            "dod_17_1": {
                "nodes_ge_5000": nodes >= 5000,
                "edges_ge_50000": edges >= 50000,
                "traversal_le_300ms": (_med(latencies) is not None and _med(latencies) <= 300),
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    finally:
        await db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Бенчмарк Knowledge Graph (DoD M-K3.17.1)")
    ap.add_argument("--snapshot", required=True, help="папка DumpConfigToFiles типовой")
    ap.add_argument("--db", default="data/graph_bench.db", help="временная БД (НЕ pilot.db)")
    ap.add_argument("--bsl-limit", type=int, default=None, help="лимит BSL-файлов (smoke)")
    ap.add_argument(
        "--traverse-only", action="store_true",
        help="не строить граф — только бенч traversal на существующей БД",
    )
    a = ap.parse_args()
    asyncio.run(run(a.snapshot, a.db, a.bsl_limit, traverse_only=a.traverse_only))
    return 0


if __name__ == "__main__":
    sys.exit(main())
