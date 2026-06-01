"""Apply-loop: применяет response-haiku-erp8-part*.json в БД по мере появления.

Не зависит от Claude-лимита (чистый Python+SQLite). Идемпотентно: upsert по
(channel_id, qname). Трекает применённые файлы по (name, mtime); при изменении —
переприменяет. Печатает прогресс. Останавливается, когда все --expect частей
применены и N проходов подряд без новых файлов, либо по достижении max-passes.

    python -m scripts.apply_loop_erp8 --expect 153
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import aiosqlite

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import json  # noqa: E402

from scripts.apply_claude_batch import apply_batch  # noqa: E402

DB_PATH = "C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db"


def salvage_items(text: str) -> list[dict]:
    """Вытащить валидные item-объекты из (возможно битого) items-массива."""
    i = text.find('"items"')
    if i < 0:
        return []
    j = text.find('[', i)
    if j < 0:
        return []
    items: list[dict] = []
    n = len(text)
    k = j + 1
    start = None
    depth = 0
    in_str = False
    esc = False
    while k < n:
        ch = text[k]
        if start is None:
            if ch == '{':
                start, depth, in_str, esc = k, 1, False, False
            elif ch == ']':
                break
        else:
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        items.append(json.loads(text[start:k + 1]))
                    except Exception:  # noqa: BLE001
                        pass
                    start = None
        k += 1
    return items


async def apply_with_salvage(db, f: Path) -> dict:
    """apply_batch; при битом JSON — salvage валидных items и apply их."""
    try:
        return await apply_batch(db, f)
    except json.JSONDecodeError:
        text = f.read_text(encoding="utf-8")
        items = salvage_items(text)
        sf = f.with_suffix(".salvaged.json")
        sf.write_text(json.dumps({
            "channel_id": "_erp25_21_118",
            "generated_by": "claude-haiku-4.5-subagent",
            "prompt_version": "v8-haiku",
            "items": items,
        }, ensure_ascii=False), encoding="utf-8")
        stats = await apply_batch(db, sf)
        stats["salvaged"] = len(items)
        print(f"  salvaged {f.name}: {len(items)} items recovered", flush=True)
        return stats
RESP_DIR = Path(
    "C:/CLOUDE_PR/projects/analyst-workspace-design/.planning/"
    "knowledge-layer-2026-05-24/phases/M-K2.5/claude-responses")
GLOB = "response-haiku-erp8-part*.json"
CHANNEL = "_erp25_21_118"


async def mock_count(db: aiosqlite.Connection) -> int:
    row = await (await db.execute(
        "SELECT COUNT(*) FROM typical_object_cards WHERE channel_id=? AND is_mock=1",
        (CHANNEL,))).fetchone()
    return row[0]


async def amain(args: argparse.Namespace) -> int:
    applied: dict[str, float] = {}  # filename -> mtime
    total_cards = 0
    idle = 0
    db = await aiosqlite.connect(args.db_path)
    try:
        for p in range(1, args.max_passes + 1):
            files = sorted(RESP_DIR.glob(GLOB))
            new = 0
            for f in files:
                mt = f.stat().st_mtime
                if applied.get(f.name) == mt:
                    continue
                try:
                    stats = await apply_with_salvage(db, f)
                    await db.commit()
                    applied[f.name] = mt
                    total_cards += stats.get("applied", 0)
                    new += 1
                except Exception as e:  # noqa: BLE001
                    print(f"apply failed {f.name}: {e}", file=sys.stderr, flush=True)
            mc = await mock_count(db)
            print(f"[pass {p}] files={len(files)}/{args.expect} new={new} "
                  f"cards+={total_cards} erp25_mock={mc}", flush=True)
            if len(files) >= args.expect and new == 0:
                idle += 1
                if idle >= 3:
                    print(f"DONE: all {args.expect} parts applied, mock={mc}", flush=True)
                    return 0
            else:
                idle = 0
            time.sleep(args.interval)
        print(f"max-passes reached; applied {len(applied)} files", flush=True)
        return 0
    finally:
        await db.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--expect", type=int, default=153)
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--max-passes", type=int, default=600)
    return asyncio.run(amain(ap.parse_args(argv if argv is not None else sys.argv[1:])))


if __name__ == "__main__":
    sys.exit(main())
