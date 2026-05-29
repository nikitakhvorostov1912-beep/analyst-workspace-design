"""NIM-safe smoke киллер-UC инструментов на РЕАЛЬНОМ графе типовой.

Верифицирует, что уже существующие tools (typical/tool.py) реально отдают
осмысленный результат на построенном графе УТ — НЕ на синтетике. Читает
готовую bench-БД (по умолчанию Temp/graph_bench_ut115.db, channel _bench),
ничего не строит и НЕ трогает pilot.db.

Запуск:
    cd backend
    python -m scripts.graph_tools_smoke \\
        --db C:/Users/<...>/Temp/graph_bench_ut115.db --channel _bench
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.knowledge.typical.tool import dispatch_typical_tool  # noqa: E402


async def _pick(db, channel, sql) -> str | None:
    cur = await db.execute(sql, (channel,))
    row = await cur.fetchone()
    return row[0] if row else None


async def run(db_path: str, channel: str) -> None:
    db = await aiosqlite.connect(db_path)
    await db.execute("PRAGMA foreign_keys = ON")
    try:
        # Метод с исходящими CALLS — реальная точка вызова.
        method_with_calls = await _pick(
            db, channel,
            "SELECT n.qualified_name FROM graph_nodes n JOIN graph_edges e "
            "ON e.src_id = n.id WHERE n.channel_id = ? AND n.node_kind = 'Method' "
            "AND e.edge_kind = 'CALLS' LIMIT 1",
        )
        # Реальный регистр с входящими WRITES_TO (методы, которые в него пишут).
        register = await _pick(
            db, channel,
            "SELECT n.qualified_name FROM graph_nodes n JOIN graph_edges e "
            "ON e.dst_id = n.id WHERE n.channel_id = ? AND e.edge_kind = 'WRITES_TO' "
            "AND n.qualified_name LIKE 'AccumulationRegister.%' LIMIT 1",
        )
        # Объект метаданных для explain.
        obj = await _pick(
            db, channel,
            "SELECT qualified_name FROM graph_nodes WHERE channel_id = ? "
            "AND node_kind = 'MetadataObject' LIMIT 1",
        )

        print(f"channel={channel}")
        print(f"sample method (CALLS out): {method_with_calls}")
        print(f"sample register:           {register}")
        print(f"sample object:             {obj}")
        print("-" * 60)

        async def _call(name, args):
            ok, result, err = await dispatch_typical_tool(db, name, args)
            summary = None
            if isinstance(result, dict):
                summary = {
                    k: (f"list[{len(v)}]" if isinstance(v, list) else v)
                    for k, v in result.items()
                }
            print(f"[{name}] ok={ok} err={err}")
            if summary:
                print(f"   {json.dumps(summary, ensure_ascii=False)[:300]}")
            return ok, result

        if method_with_calls:
            await _call("trace_typical_calls", {
                "channel_id": channel, "qualified_name": method_with_calls,
                "direction": "out", "depth": 3,
            })
            await _call("trace_typical_calls", {
                "channel_id": channel, "qualified_name": method_with_calls,
                "direction": "in", "depth": 3,
            })
        if register:
            await _call("trace_typical_movements", {
                "channel_id": channel, "register_qualified_name": register,
                "direction": "both",
            })
        if obj:
            await _call("explain_typical_object", {
                "channel_id": channel, "object_qualified_name": obj,
            })
    finally:
        await db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Smoke киллер-UC на реальном графе")
    ap.add_argument("--db", required=True)
    ap.add_argument("--channel", default="_bench")
    a = ap.parse_args()
    asyncio.run(run(a.db, a.channel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
