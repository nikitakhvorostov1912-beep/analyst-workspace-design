"""Разбить compact batch на маленькие части (~10 объектов = ~30 KB).

Subagent prompt лимит — большой compact batch (166 KB) не помещается.
Разбиваем на части по 10-15 объектов чтобы каждая партия влезала в context.

## Использование

```bash
python -m scripts.split_batch \\
    --input batch-compact-006-bp50.json \\
    --chunk-size 10 \\
    --prefix batch-compact-006-bp
```

Создаст файлы batch-compact-006-bp-part1.json ... part5.json (по 10 объектов).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Compact batch file")
    parser.add_argument("--chunk-size", type=int, default=10)
    parser.add_argument("--prefix", required=True, help="Output prefix")
    parser.add_argument("--output-dir",
                        default="C:/CLOUDE_PR/projects/analyst-workspace-design/.planning/knowledge-layer-2026-05-24/phases/M-K2.5/claude-batches")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    src = Path(args.input)
    if not src.is_absolute():
        src = Path(args.output_dir) / src.name

    data = json.loads(src.read_text(encoding="utf-8"))
    items = data.get("items") or []
    chunks = [items[i:i + args.chunk_size] for i in range(0, len(items), args.chunk_size)]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    created = []
    for idx, chunk in enumerate(chunks, 1):
        part_data = {
            "channel_id": data["channel_id"],
            "format": data.get("format", "compact-v1"),
            "part": idx,
            "total_parts": len(chunks),
            "items": chunk,
        }
        out_path = out_dir / f"{args.prefix}-part{idx}.json"
        out_path.write_text(json.dumps(part_data, ensure_ascii=False, indent=2), encoding="utf-8")
        size_kb = out_path.stat().st_size / 1024
        created.append((out_path.name, len(chunk), size_kb))

    print(f"\nSplit {src.name} into {len(chunks)} parts:")
    for name, n, sz in created:
        print(f"  {name}: {n} items, {sz:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
