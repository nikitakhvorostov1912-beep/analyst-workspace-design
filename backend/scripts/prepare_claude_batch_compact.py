"""Compact batch для subagent — урезанный context (1-2 KB на объект вместо ~30 KB).

При prepare_claude_batch полный CardContext получается ~30 KB на объект
(attributes с типами, methods с module_kind, reads_from с virtual_kind, etc).
Для 50 объектов batch ~1.5 MB — это превышает лимит prompt size в subagent
("Prompt is too long" error).

Compact extractor берёт только то что эксперту-методологу нужно для генерации
качественной карточки:
- qname, kind, name, comment
- attributes с references (топ-12)
- tabular_sections — только names
- handler_methods — только names (топ-6)
- writes_to — полный список (критично для movements)
- reads_from — только qnames (топ-10)
- referenced_by (топ-8)

Размер: ~1-2 KB на объект × 50 = 50-100 KB batch. Помещается в любой subagent.

## Использование

```bash
python -m scripts.prepare_claude_batch_compact \\
    --channel-id _bp30_138_24 --auto-top 50 --output batch-compact-bp50.json
```
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import aiosqlite

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.knowledge.typical.card_context import build_card_context  # noqa: E402
from app.storage.migrations import apply_migrations  # noqa: E402
from scripts.prepare_claude_batch import (  # noqa: E402
    PRIORITY_MAP,
    resolve_qnames,
    select_top_by_contains_count,
)

logger = logging.getLogger("prepare_claude_batch_compact")


def _compact_context(ctx_dict: dict[str, Any]) -> dict[str, Any]:
    """Compact representation: top attrs/methods/reads, full writes/refs."""
    attrs_with_refs = [
        {"name": a["name"], "ref": ",".join(a.get("references", []))[:80], "req": bool(a.get("fill_check"))}
        for a in ctx_dict.get("attributes") or []
        if a.get("references")
    ][:12]

    ts_names = [ts["name"] for ts in (ctx_dict.get("tabular_sections") or [])][:8]

    handlers = [m["name"] for m in (ctx_dict.get("methods") or []) if m.get("is_handler")][:6]

    writes = list(ctx_dict.get("writes_to") or [])

    reads = []
    seen_reads: set[str] = set()
    for r in ctx_dict.get("reads_from") or []:
        qn = r.get("register")
        if qn and qn not in seen_reads:
            seen_reads.add(qn)
            reads.append(qn)
        if len(reads) >= 10:
            break

    refs = []
    seen_refs: set[str] = set()
    for ref in ctx_dict.get("referenced_by") or []:
        # Берём только qname верхнего уровня (отрезаем .Реквизит.X и .ТабличнаяЧасть.X)
        base = ref.split(".Реквизит.")[0].split(".ТабличнаяЧасть.")[0]
        if base not in seen_refs:
            seen_refs.add(base)
            refs.append(base)
        if len(refs) >= 8:
            break

    return {
        "qname": ctx_dict["object_qualified_name"],
        "kind": ctx_dict["object_kind"],
        "name": ctx_dict.get("object_name", ""),
        "comment": (ctx_dict.get("object_comment") or "")[:200],
        "attrs": attrs_with_refs,
        "ts": ts_names,
        "handlers": handlers,
        "writes_to": writes,
        "reads_from": reads,
        "referenced_by": refs,
    }


async def amain(args: argparse.Namespace) -> int:
    db = await aiosqlite.connect(args.db_path)
    try:
        await apply_migrations(db)

        qnames = resolve_qnames(args)
        if not qnames and args.auto_top:
            qnames = await select_top_by_contains_count(db, args.channel_id, args.auto_top)

        if not qnames:
            print("ОШИБКА: не задан ни --qnames, ни --priority, ни --auto-top", file=sys.stderr)
            return 1

        items: list[dict[str, Any]] = []
        skipped: list[str] = []
        for qname in qnames:
            try:
                ctx = await build_card_context(
                    db, channel_id=args.channel_id, object_qualified_name=qname,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("build_card_context failed for %s: %s", qname, e)
                skipped.append(qname)
                continue

            if ctx is None:
                skipped.append(qname)
                continue

            items.append({
                **_compact_context(ctx.to_dict()),
                "source_hash": ctx.compute_source_hash(),
            })

        output_path = Path(args.output)
        if not output_path.is_absolute():
            default_dir = Path(
                "C:/CLOUDE_PR/projects/analyst-workspace-design/.planning/"
                "knowledge-layer-2026-05-24/phases/M-K2.5/claude-batches"
            )
            default_dir.mkdir(parents=True, exist_ok=True)
            output_path = default_dir / output_path.name

        output_path.parent.mkdir(parents=True, exist_ok=True)
        batch_data = {
            "channel_id": args.channel_id,
            "format": "compact-v1",
            "total_requested": len(qnames),
            "total_built": len(items),
            "skipped": skipped,
            "items": items,
        }
        output_path.write_text(
            json.dumps(batch_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        size_kb = output_path.stat().st_size / 1024
        print(f"\nCompact batch: {args.channel_id} | items={len(items)} | size={size_kb:.1f} KB | file={output_path}")
        return 0
    finally:
        await db.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact batch для subagent")
    parser.add_argument(
        "--db-path",
        default="C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db",
    )
    parser.add_argument("--channel-id", required=True)
    parser.add_argument("--output", required=True)

    sel = parser.add_mutually_exclusive_group(required=False)
    sel.add_argument("--qnames", default=None)
    sel.add_argument("--priority", action="store_true")
    sel.add_argument("--auto-top", type=int, default=None)

    parser.add_argument("--log-level", default="WARNING")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
