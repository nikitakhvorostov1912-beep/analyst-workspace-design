"""Bulk validate карточки против графа (M-K2.5.10.8).

Прогоняет `validate_card_against_graph()` на всех существующих карточках
БД, сохраняет результат в колонки `validation_status` / `validation_issues`
/ `validated_at` (Migration v20).

Не требует LLM ключа — это только graph queries. Можно запускать на
mock-карточках чтобы увидеть где mock-генератор уже неаккуратен.

## Использование

```bash
# Validate все 63k карточки (~5-10 минут):
python -m scripts.typical_cards_validate_all --confirm

# Один канал:
python -m scripts.typical_cards_validate_all --channel-id _bp30_138_24 --confirm

# Dry-run (показать сколько будет, не писать):
python -m scripts.typical_cards_validate_all --dry-run
```

## Выход

Сводка per channel:
- total / valid / issues_found / object_not_in_graph
- error_count (phantom_movement / phantom_related)
- info_count (missing_movement)

Acceptance для real LLM rebuild: error_rate / total < 5% per channel.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import aiosqlite

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.knowledge.typical.card_storage import list_cards_by_channel  # noqa: E402
from app.knowledge.typical.card_validator import (  # noqa: E402
    save_validation_result,
    validate_card_against_graph,
)
from app.knowledge.typical.storage import list_configurations  # noqa: E402
from app.storage.migrations import apply_migrations  # noqa: E402

logger = logging.getLogger("typical_cards_validate_all")


async def validate_channel(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Validate всех карточек одного канала. Возвращает stats dict."""
    cards = await list_cards_by_channel(db, channel_id=channel_id, limit=999_999)
    if limit:
        cards = cards[:limit]

    stats: dict[str, Any] = {
        "channel_id": channel_id,
        "total": len(cards),
        "valid": 0,
        "issues_found": 0,
        "object_not_in_graph": 0,
        "errors": 0,
        "warnings": 0,
        "infos": 0,
        "issue_codes": Counter(),
        "elapsed_s": 0.0,
    }

    if dry_run:
        return stats

    print(f"\n{'-' * 70}")
    print(f"Validating channel {channel_id} -- {stats['total']:,} cards")
    print(f"{'-' * 70}")

    start = time.monotonic()
    for i, rec in enumerate(cards, 1):
        try:
            result = await validate_card_against_graph(
                db, channel_id=channel_id, card=rec.card,
            )

            if result.status == "valid":
                stats["valid"] += 1
            elif result.status == "issues_found":
                stats["issues_found"] += 1
            elif result.status == "object_not_in_graph":
                stats["object_not_in_graph"] += 1

            for issue in result.issues:
                if issue.severity == "error":
                    stats["errors"] += 1
                elif issue.severity == "warning":
                    stats["warnings"] += 1
                elif issue.severity == "info":
                    stats["infos"] += 1
                stats["issue_codes"][issue.code] += 1

            await save_validation_result(
                db, channel_id=channel_id,
                object_qualified_name=rec.object_qualified_name,
                result=result,
            )

        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to validate %s: %s", rec.object_qualified_name, e)

        if i % 1000 == 0 or i == len(cards):
            elapsed = time.monotonic() - start
            rate = i / elapsed if elapsed > 0 else 0
            eta_s = (len(cards) - i) / rate if rate > 0 else 0
            print(
                f"  [{i:6d}/{len(cards):6d}] {i / len(cards) * 100:5.1f}%  "
                f"valid={stats['valid']:5d}  issues={stats['issues_found']:5d}  "
                f"errors={stats['errors']:5d}  rate={rate:.0f}/s  ETA={eta_s/60:5.1f}min",
                flush=True,
            )

    stats["elapsed_s"] = round(time.monotonic() - start, 1)
    stats["issue_codes"] = dict(stats["issue_codes"])
    return stats


async def amain(args: argparse.Namespace) -> int:
    if not args.dry_run and not args.confirm:
        print("ОШИБКА: для реальной записи нужен флаг --confirm. "
              "Используй --dry-run для проверки.", file=sys.stderr)
        return 1

    db = await aiosqlite.connect(args.db_path)
    try:
        await apply_migrations(db)

        if args.channel_id:
            channels = [args.channel_id]
        else:
            configs = await list_configurations(db)
            channels = [c.channel_id for c in configs]

        all_stats: list[dict[str, Any]] = []
        for ch in channels:
            stats = await validate_channel(
                db, channel_id=ch, dry_run=args.dry_run, limit=args.limit,
            )
            all_stats.append(stats)

        # Финальный сводный отчёт
        print(f"\n{'=' * 70}")
        print(f"FINAL VALIDATION SUMMARY")
        print(f"{'=' * 70}")
        total_cards = sum(s["total"] for s in all_stats)
        total_valid = sum(s["valid"] for s in all_stats)
        total_issues = sum(s["issues_found"] for s in all_stats)
        total_not_in_graph = sum(s["object_not_in_graph"] for s in all_stats)
        total_errors = sum(s["errors"] for s in all_stats)
        total_warnings = sum(s["warnings"] for s in all_stats)
        total_infos = sum(s["infos"] for s in all_stats)

        print(f"  Total carts validated:   {total_cards:,}")
        print(f"  Status valid:            {total_valid:,} ({total_valid/max(total_cards,1)*100:.1f}%)")
        print(f"  Status issues_found:     {total_issues:,}")
        print(f"  Status object_not_in_graph: {total_not_in_graph:,}")
        print(f"  Errors (severity=error): {total_errors:,}")
        print(f"  Warnings:                {total_warnings:,}")
        print(f"  Infos:                   {total_infos:,}")

        print(f"\n  Per-channel:")
        for s in all_stats:
            err_rate = s["errors"] / max(s["total"], 1) * 100
            print(
                f"    {s['channel_id']:25s}  "
                f"total={s['total']:6,d}  "
                f"valid={s['valid']:6,d}  "
                f"errors={s['errors']:5,d} ({err_rate:4.1f}%)  "
                f"elapsed={s['elapsed_s']:5.1f}s"
            )

        # Aggregate issue codes
        all_codes: Counter = Counter()
        for s in all_stats:
            for code, count in (s["issue_codes"] or {}).items():
                all_codes[code] += count

        if all_codes:
            print(f"\n  Issue codes (top 10):")
            for code, count in all_codes.most_common(10):
                print(f"    {code:30s}  {count:,}")

        print(f"{'=' * 70}\n")

        # Exit code: 0 если error_rate < 5% (acceptance threshold)
        if total_cards == 0:
            return 0
        error_rate = total_errors / total_cards
        if error_rate >= 0.05:
            print(f"ВНИМАНИЕ: error_rate = {error_rate * 100:.1f}% >= 5% threshold",
                  file=sys.stderr)
            return 1
        return 0

    finally:
        await db.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk validate карточек против графа (M-K2.5.10.8)",
    )
    parser.add_argument(
        "--db-path",
        default="C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db",
    )
    parser.add_argument(
        "--channel-id", default=None,
        help="Один канал (default: все configurations)",
    )
    parser.add_argument("--limit", type=int, default=None,
                        help="Ограничение карточек (для тестов)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Только посчитать, не валидировать")
    parser.add_argument("--confirm", action="store_true",
                        help="Обязательно для реальной записи")
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
