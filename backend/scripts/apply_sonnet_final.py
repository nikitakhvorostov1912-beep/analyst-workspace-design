"""Применить response-sonnet-*.json в БД (любой канал, с salvage)."""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import aiosqlite

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.apply_claude_batch import apply_batch  # noqa: E402

RESP = Path(
    "C:/CLOUDE_PR/projects/analyst-workspace-design/.planning/"
    "knowledge-layer-2026-05-24/phases/M-K2.5/claude-responses")


def salvage(text: str) -> list[dict]:
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
    ins = False
    esc = False
    while k < n:
        ch = text[k]
        if start is None:
            if ch == '{':
                start, depth, ins, esc = k, 1, False, False
            elif ch == ']':
                break
        else:
            if ins:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    ins = False
            elif ch == '"':
                ins = True
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


async def main() -> None:
    db = await aiosqlite.connect(
        "C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db")
    files = sorted(RESP.glob("response-sonnet-*.json"))
    files = [f for f in files if not f.name.endswith(".salvaged.json")]
    print("файлов:", len(files))
    for f in files:
        try:
            st = await apply_batch(db, f)
            await db.commit()
            print(f"{f.name}: applied={st.get('applied')} total={st.get('total')}")
        except json.JSONDecodeError:
            text = f.read_text(encoding="utf-8")
            items = salvage(text)
            m = re.search(r'"channel_id"\s*:\s*"([^"]+)"', text)
            sf = f.with_suffix(".salvaged.json")
            sf.write_text(json.dumps({
                "channel_id": m.group(1),
                "generated_by": "claude-sonnet-4.6",
                "prompt_version": "v-final-sonnet",
                "items": items,
            }, ensure_ascii=False), encoding="utf-8")
            st = await apply_batch(db, sf)
            await db.commit()
            print(f"{f.name}: SALVAGED items={len(items)} applied={st.get('applied')}")
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
