"""One-off: собрать compact-чанки из ТЕКУЩИХ is_mock=1 объектов канала.

Берёт живой остаток mock (не stale-снимок), строит compact context и режет
на части по --chunk-size в part{n}.json — формат идентичен wave7 (для Haiku-workflow).

    python -m scripts.build_chunks_from_mock --channel-id _erp25_21_118 \
        --out-dir <abs>/wave8-erp --chunk-size 60
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.knowledge.typical.card_context import build_card_context  # noqa: E402
from scripts.prepare_claude_batch_compact import _compact_context  # noqa: E402

DB_PATH = "C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db"


async def amain(args: argparse.Namespace) -> int:
    db = await aiosqlite.connect(args.db_path)
    try:
        rows = await (await db.execute(
            "SELECT object_qualified_name FROM typical_object_cards "
            "WHERE channel_id=? AND is_mock=1 ORDER BY object_qualified_name",
            (args.channel_id,),
        )).fetchall()
        qnames = [r[0] for r in rows]
        print(f"mock qnames: {len(qnames)}")

        items: list[dict] = []
        skipped = 0
        sem = asyncio.Semaphore(24)

        async def build(qn: str):
            nonlocal skipped
            async with sem:
                try:
                    ctx = await build_card_context(
                        db, channel_id=args.channel_id, object_qualified_name=qn)
                    if ctx is None:
                        skipped += 1
                        return None
                    return _compact_context(ctx.to_dict())
                except Exception as e:  # noqa: BLE001
                    skipped += 1
                    print(f"skip {qn}: {e}", file=sys.stderr)
                    return None

        built = await asyncio.gather(*[build(q) for q in qnames])
        items = [it for it in built if it is not None]
        print(f"built: {len(items)} | skipped: {skipped}")

        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        cs = args.chunk_size
        nparts = (len(items) + cs - 1) // cs
        for i in range(nparts):
            part = items[i * cs:(i + 1) * cs]
            (out_dir / f"part{i+1}.json").write_text(
                json.dumps({"channel_id": args.channel_id, "items": part},
                           ensure_ascii=False, indent=2),
                encoding="utf-8")
        print(f"wrote {nparts} parts -> {out_dir}")
        return 0
    finally:
        await db.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db-path", default=DB_PATH)
    p.add_argument("--channel-id", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--chunk-size", type=int, default=60)
    return asyncio.run(amain(p.parse_args(argv if argv is not None else sys.argv[1:])))


if __name__ == "__main__":
    sys.exit(main())
