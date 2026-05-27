"""Подготовка batch контекстов для генерации карточек через Claude в сессии (M-K2.5.11.1).

Выгружает CardContext для топ-N объектов типовой в JSON батч-файл, чтобы
Claude (как Opus 4.7 в этой сессии) мог их прочитать и сгенерировать
эталонные карточки в одном ответе.

## Workflow

```
prepare_claude_batch.py
    ↓ читает БД, выбирает топ-N объектов
    ↓ build_card_context для каждого
    ↓ сохраняет в .planning/.../claude-batches/batch-NNN.json
              ↓
Claude (Opus 4.7 в сессии) читает batch через Read tool
    ↓ генерирует JSON ответ — массив карточек
    ↓ Write tool сохраняет в .planning/.../claude-responses/response-NNN.json
              ↓
apply_claude_batch.py
    ↓ читает response, парсит карточки, валидирует против графа
    ↓ upsert в БД с llm_model="claude-opus-4-7-via-session", is_mock=False
```

## Приоритет объектов

При выборе топ-N используется эвристика «важность для аналитика»:
1. Если задан `--qnames` — берём явный список (контролируемый pilot)
2. Если задан `--priority-bp` / `--priority-ut` / `--priority-erp` / `--priority-ka` —
   список «звёзд» для каждой типовой (Реализация, Поступление, СчётФактура, etc.)
3. Иначе `--auto-top-N` по числу CONTAINS edges в графе (proxy для размера/важности)

## Использование

```bash
# Pilot: явные 10 топ-объектов БП
python -m scripts.prepare_claude_batch \\
    --channel-id _bp30_138_24 \\
    --priority-bp \\
    --output batch-001-bp-pilot.json

# Auto top-50 БП по CONTAINS count
python -m scripts.prepare_claude_batch \\
    --channel-id _bp30_138_24 \\
    --auto-top 50 \\
    --output batch-002-bp-auto.json

# Кастомный список:
python -m scripts.prepare_claude_batch \\
    --channel-id _bp30_138_24 \\
    --qnames "Document.A,Document.B,Catalog.C" \\
    --output batch-003-custom.json
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

logger = logging.getLogger("prepare_claude_batch")


# ── Приоритетные «звёздные» объекты для каждой типовой ────────────────
#
# Это объекты которые аналитики спрашивают чаще всего. Покрытие топ-N
# дает Pareto эффект — 90% запросов закрываются.

PRIORITY_BP_30 = [
    # Документы — самые часто используемые в учёте
    "Document.РеализацияТоваровУслуг",
    "Document.ПоступлениеТоваровУслуг",
    "Document.СчетФактураВыданный",
    "Document.СчетФактураПолученный",
    "Document.АвансовыйОтчет",
    "Document.ПриходныйКассовыйОрдер",
    "Document.РасходныйКассовыйОрдер",
    "Document.ПлатежноеПоручение",
    # Справочники и план счетов
    "Catalog.Контрагенты",
    "ChartOfAccounts.Хозрасчетный",
]

PRIORITY_UT_115 = [
    "Document.РеализацияТоваровУслуг",
    "Document.ПоступлениеТоваровУслуг",
    "Document.ЗаказКлиента",
    "Document.ЗаказПоставщику",
    "Document.ПеремещениеТоваров",
    "Document.СчетФактураВыданный",
    "Document.КассоваяСмена",
    "Catalog.Номенклатура",
    "Catalog.Партнеры",
    "Catalog.Контрагенты",
]

PRIORITY_KA_2 = [
    "Document.РеализацияТоваровУслуг",
    "Document.ПоступлениеТоваровУслуг",
    "Document.ЗаказКлиента",
    "Document.СчетФактураВыданный",
    "Document.АвансовыйОтчет",
    "Document.ПриходныйКассовыйОрдер",
    "Catalog.Контрагенты",
    "Catalog.Номенклатура",
    "ChartOfAccounts.Хозрасчетный",
    "Document.ПлатежноеПоручение",
]

PRIORITY_ERP_25 = [
    "Document.РеализацияТоваровУслуг",
    "Document.ПоступлениеТоваровУслуг",
    "Document.ЗаказКлиента",
    "Document.ЗаказПоставщику",
    "Document.ПеремещениеТоваров",
    "Document.СчетФактураВыданный",
    "Document.АвансовыйОтчет",
    "Document.КорректировкаРеализации",
    "Catalog.Номенклатура",
    "ChartOfAccounts.Хозрасчетный",
]


PRIORITY_MAP = {
    "_bp30_138_24": PRIORITY_BP_30,
    "_ut115_17_226": PRIORITY_UT_115,
    "_ka2_25_92": PRIORITY_KA_2,
    "_erp25_21_118": PRIORITY_ERP_25,
}


async def select_top_by_contains_count(
    db: aiosqlite.Connection,
    channel_id: str,
    limit: int,
) -> list[str]:
    """Авто-выборка топ-N по числу CONTAINS edges от объекта.

    Объекты с большим количеством CONTAINS (методов / реквизитов / ТЧ)
    обычно — крупные документы / справочники, аналитики о них чаще спрашивают.
    """
    cursor = await db.execute(
        """
        SELECT n.qualified_name, COUNT(e.id) AS containment_count
        FROM graph_nodes n
        LEFT JOIN graph_edges e ON e.src_id = n.id AND e.edge_kind = 'CONTAINS'
        WHERE n.channel_id = ?
          AND n.node_kind = 'MetadataObject'
          AND (n.qualified_name LIKE 'Document.%'
               OR n.qualified_name LIKE 'Catalog.%'
               OR n.qualified_name LIKE 'AccumulationRegister.%'
               OR n.qualified_name LIKE 'AccountingRegister.%'
               OR n.qualified_name LIKE 'InformationRegister.%'
               OR n.qualified_name LIKE 'ChartOfAccounts.%')
        GROUP BY n.qualified_name
        ORDER BY containment_count DESC
        LIMIT ?
        """,
        (channel_id, limit),
    )
    rows = await cursor.fetchall()
    return [r[0] for r in rows]


def resolve_qnames(args: argparse.Namespace) -> list[str]:
    """Resolve целевой список qnames из flags."""
    if args.qnames:
        return [q.strip() for q in args.qnames.split(",") if q.strip()]
    if args.priority:
        priority = PRIORITY_MAP.get(args.channel_id)
        if not priority:
            raise SystemExit(
                f"Нет priority списка для {args.channel_id!r}. "
                f"Доступны: {list(PRIORITY_MAP.keys())}"
            )
        return priority
    # auto-top будет резолвиться через БД
    return []


async def amain(args: argparse.Namespace) -> int:
    db = await aiosqlite.connect(args.db_path)
    try:
        await apply_migrations(db)

        # Resolve qnames
        qnames = resolve_qnames(args)
        if not qnames and args.auto_top:
            qnames = await select_top_by_contains_count(db, args.channel_id, args.auto_top)

        if not qnames:
            print("ОШИБКА: не задан ни --qnames, ни --priority, ни --auto-top", file=sys.stderr)
            return 1

        # Build CardContext для каждого
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
                "qname": qname,
                "context": ctx.to_dict(),
                "source_hash": ctx.compute_source_hash(),
            })

        # Сохранить batch
        output_path = Path(args.output)
        if not output_path.is_absolute():
            # По умолчанию в .planning/.../claude-batches/
            default_dir = Path(
                "C:/CLOUDE_PR/projects/analyst-workspace-design/.planning/"
                "knowledge-layer-2026-05-24/phases/M-K2.5/claude-batches"
            )
            default_dir.mkdir(parents=True, exist_ok=True)
            output_path = default_dir / output_path.name

        output_path.parent.mkdir(parents=True, exist_ok=True)
        batch_data = {
            "channel_id": args.channel_id,
            "total_requested": len(qnames),
            "total_built": len(items),
            "skipped": skipped,
            "items": items,
        }
        output_path.write_text(
            json.dumps(batch_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"\n{'=' * 70}")
        print(f"BATCH READY")
        print(f"{'=' * 70}")
        print(f"  Channel:         {args.channel_id}")
        print(f"  Requested:       {len(qnames)}")
        print(f"  Built contexts:  {len(items)}")
        print(f"  Skipped:         {len(skipped)}")
        if skipped:
            for s in skipped:
                print(f"    - {s}")
        print(f"  Output file:     {output_path}")
        size_kb = output_path.stat().st_size / 1024
        print(f"  File size:       {size_kb:.1f} KB")
        print(f"{'=' * 70}\n")

        return 0
    finally:
        await db.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare batch для генерации карточек через Claude в сессии (M-K2.5.11.1)",
    )
    parser.add_argument(
        "--db-path",
        default="C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db",
    )
    parser.add_argument("--channel-id", required=True,
                        help="Channel ID типовой (e.g. _bp30_138_24)")
    parser.add_argument("--output", required=True,
                        help="Имя output JSON файла (default dir: .planning/.../claude-batches/)")

    selection = parser.add_mutually_exclusive_group(required=False)
    selection.add_argument("--qnames", default=None,
                           help="Явный список qnames через запятую")
    selection.add_argument("--priority", action="store_true",
                           help="Использовать priority список для channel (топ-10 'звёзд')")
    selection.add_argument("--auto-top", type=int, default=None,
                           help="Авто-выборка топ-N по числу CONTAINS edges")

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
