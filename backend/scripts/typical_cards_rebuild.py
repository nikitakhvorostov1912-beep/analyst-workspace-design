"""Production-ready bulk rebuild карточек через real LLM (M-K2.5.10.5).

Заменяет mock-карточки на эталонные карточки от real LLM (DeepSeek/OpenAI/etc.)
с rate limiting, retry, checkpoint, telemetry. Universal — работает с любым
OpenAI-compatible провайдером через `OpenAICompatLLMCaller`.

## Workflow на каждую карточку

```
для каждой карточки в фильтре:
    1. skip если уже в checkpoint (resume safe)
    2. skip если is_mock=False и --only-mock (default)
    3. загрузить CardContext через build_card_context()
    4. skip если context пустой (нет графа)
    5. generate_card() → LLM call с retry
    6. validate_card_against_graph() → проверка против факта
    7. upsert_card(is_mock=False) + save_validation_result()
    8. update checkpoint (atomic write)
    9. rate limit await
```

## Использование

```bash
# Pilot (10 объектов БП, smoke):
python -m scripts.typical_cards_rebuild --channel-id _bp30_138_24 --limit 10 --confirm

# Полный rebuild одного канала:
python -m scripts.typical_cards_rebuild --channel-id _bp30_138_24 --confirm

# Continue if crashed:
python -m scripts.typical_cards_rebuild --channel-id _bp30_138_24 --resume --confirm

# Dry-run (без LLM call, посчитать сколько будет):
python -m scripts.typical_cards_rebuild --channel-id _bp30_138_24 --dry-run
```

## Acceptance после прогона

- Все карточки: `is_mock = False`
- Все карточки: `validation_status IS NOT NULL`
- error_rate (phantom_movement / phantom_related) < 5%
- 0 карточек со status='failed' (либо generated, либо embedded)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiosqlite

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.knowledge.typical.card_context import build_card_context  # noqa: E402
from app.knowledge.typical.card_generator import (  # noqa: E402
    CardGenerationError,
    generate_card,
)
from app.knowledge.typical.card_models import (  # noqa: E402
    CardStatus,
    TypicalObjectCard,
)
from app.knowledge.typical.card_storage import (  # noqa: E402
    list_cards_by_channel,
    upsert_card,
)
from app.knowledge.typical.card_validator import (  # noqa: E402
    save_validation_result,
    validate_card_against_graph,
)
from app.knowledge.typical.openai_compat_llm_caller import (  # noqa: E402
    LLMAuthError,
    LLMBadRequestError,
    LLMCallError,
    OpenAICompatLLMCaller,
)
from app.storage.migrations import apply_migrations  # noqa: E402
from scripts.set_rebuild_credentials import load_rebuild_credentials  # noqa: E402

logger = logging.getLogger("typical_cards_rebuild")


# ─── Telemetry ────────────────────────────────────────────────────────


@dataclass
class RebuildStats:
    """Аккумулированная статистика прогона."""

    channel_id: str
    total_in_channel: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped_already_real: int = 0
    skipped_no_context: int = 0
    started_at: float = field(default_factory=time.monotonic)

    validation_valid: int = 0
    validation_issues: int = 0
    validation_not_in_graph: int = 0

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self.started_at

    @property
    def eta_s(self) -> float:
        if self.processed == 0:
            return 0.0
        remaining = self.total_in_channel - self.processed - self.skipped_already_real - self.skipped_no_context
        if remaining <= 0:
            return 0.0
        avg = self.elapsed_s / self.processed
        return avg * remaining

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "total_in_channel": self.total_in_channel,
            "processed": self.processed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped_already_real": self.skipped_already_real,
            "skipped_no_context": self.skipped_no_context,
            "elapsed_s": round(self.elapsed_s, 1),
            "validation_valid": self.validation_valid,
            "validation_issues": self.validation_issues,
            "validation_not_in_graph": self.validation_not_in_graph,
        }


# ─── Checkpoint ───────────────────────────────────────────────────────


def _checkpoint_path(checkpoint_dir: Path, channel_id: str) -> Path:
    return checkpoint_dir / f"rebuild-{channel_id}.json"


def load_checkpoint(checkpoint_dir: Path, channel_id: str) -> set[str]:
    """Возвращает set processed qnames (для resume)."""
    path = _checkpoint_path(checkpoint_dir, channel_id)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("processed_qnames") or [])
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Не удалось прочитать checkpoint %s: %s", path, e)
        return set()


def save_checkpoint(
    checkpoint_dir: Path,
    channel_id: str,
    processed_qnames: set[str],
    failed: list[dict[str, str]],
    stats: RebuildStats,
) -> None:
    """Atomic write checkpoint через temp + rename."""
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(checkpoint_dir, channel_id)
    tmp = path.with_suffix(".tmp")
    data = {
        "channel_id": channel_id,
        "processed_qnames": sorted(processed_qnames),
        "failed": failed,
        "stats": stats.to_dict(),
        "last_updated": time.time(),
    }
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# ─── Main rebuild routine ─────────────────────────────────────────────


async def rebuild_channel(
    *,
    db: aiosqlite.Connection,
    channel_id: str,
    llm: OpenAICompatLLMCaller,
    checkpoint_dir: Path,
    only_mock: bool = True,
    limit: int | None = None,
    object_kind: str | None = None,
    rate_limit_rps: float = 10.0,
    skip_validation: bool = False,
    dry_run: bool = False,
    resume: bool = False,
) -> RebuildStats:
    """Полный rebuild карточек одного канала.

    Возвращает RebuildStats. Telemetry LLM caller'a доступна через `llm.telemetry`.
    """
    stats = RebuildStats(channel_id=channel_id)
    processed_qnames: set[str] = load_checkpoint(checkpoint_dir, channel_id) if resume else set()
    failed_list: list[dict[str, str]] = []

    # Загрузить целевой список карточек
    cards = await list_cards_by_channel(db, channel_id=channel_id, limit=999_999)
    if object_kind:
        cards = [c for c in cards if c.object_kind == object_kind]
    if only_mock:
        cards = [c for c in cards if c.is_mock]
    if limit:
        cards = cards[:limit]

    stats.total_in_channel = len(cards)
    print(f"\n{'=' * 70}")
    print(f"Channel: {channel_id}")
    print(f"Cards to process: {stats.total_in_channel:,}")
    print(f"Rate limit: {rate_limit_rps} RPS")
    print(f"Dry-run: {dry_run}")
    print(f"Skip validation: {skip_validation}")
    print(f"Resume from checkpoint: {len(processed_qnames):,} already processed")
    print(f"{'=' * 70}\n")

    if dry_run:
        print(f"DRY-RUN: would process {stats.total_in_channel - len(processed_qnames)} cards")
        return stats

    rate_interval_s = 1.0 / rate_limit_rps if rate_limit_rps > 0 else 0.0
    last_call_time = 0.0

    for i, rec in enumerate(cards, 1):
        qname = rec.object_qualified_name

        # Resume safety
        if qname in processed_qnames:
            stats.skipped_already_real += 1
            continue

        # Загрузить контекст из графа
        try:
            context = await build_card_context(
                db, channel_id=channel_id, object_qualified_name=qname,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Не удалось построить контекст для %s: %s", qname, e)
            stats.skipped_no_context += 1
            continue

        if context is None:
            stats.skipped_no_context += 1
            continue

        # Rate limit await
        if rate_interval_s > 0:
            elapsed = time.monotonic() - last_call_time
            if elapsed < rate_interval_s:
                await asyncio.sleep(rate_interval_s - elapsed)

        # LLM call
        try:
            result = await generate_card(context=context, llm=llm)
            last_call_time = time.monotonic()

            # Установить правильный channel_id (generate_card возвращает пустую строку)
            card = TypicalObjectCard(
                object_qualified_name=result.card.object_qualified_name,
                object_kind=result.card.object_kind,
                channel_id=channel_id,
                summary=result.card.summary,
                purpose=result.card.purpose,
                key_attributes=result.card.key_attributes,
                movements=result.card.movements,
                posting_flow=result.card.posting_flow,
                typical_scenarios=result.card.typical_scenarios,
                preconditions=result.card.preconditions,
                related_objects=result.card.related_objects,
                its_links=result.card.its_links,
            )

            # Validate против графа
            if not skip_validation:
                validation = await validate_card_against_graph(
                    db, channel_id=channel_id, card=card,
                )
                if validation.status == "valid":
                    stats.validation_valid += 1
                elif validation.status == "issues_found":
                    stats.validation_issues += 1
                else:
                    stats.validation_not_in_graph += 1

            # Save (is_mock=False — это уже real LLM)
            source_hash = context.compute_source_hash()
            await upsert_card(
                db,
                card=card,
                source_hash=source_hash,
                prompt_version="v1",
                llm_model=result.model or llm.model,
                token_usage_in=result.tokens_in,
                token_usage_out=result.tokens_out,
                status=CardStatus.GENERATED,
                is_mock=False,
            )
            if not skip_validation:
                await save_validation_result(
                    db, channel_id=channel_id,
                    object_qualified_name=qname, result=validation,
                )

            stats.succeeded += 1
            processed_qnames.add(qname)

        except CardGenerationError as e:
            logger.warning("CardGenerationError %s: %s", qname, e)
            stats.failed += 1
            failed_list.append({"qname": qname, "error": f"CardGenerationError: {e}"})

        except (LLMAuthError, LLMBadRequestError) as e:
            # Критичные ошибки — STOP
            print(f"\n✗ КРИТИЧНАЯ ОШИБКА: {type(e).__name__}: {e}", file=sys.stderr)
            print("Прерываем rebuild. Проверь credentials через `set_rebuild_credentials test`.")
            stats.failed += 1
            failed_list.append({"qname": qname, "error": f"{type(e).__name__}: {e}"})
            save_checkpoint(checkpoint_dir, channel_id, processed_qnames, failed_list, stats)
            raise

        except LLMCallError as e:
            logger.warning("LLMCallError %s: %s", qname, e)
            stats.failed += 1
            failed_list.append({"qname": qname, "error": f"LLMCallError: {e}"})

        except Exception as e:  # noqa: BLE001 — universal safety net
            logger.exception("Unexpected error for %s", qname)
            stats.failed += 1
            failed_list.append({"qname": qname, "error": f"{type(e).__name__}: {e}"})

        stats.processed += 1

        # Checkpoint каждые 25 карточек + последняя
        if stats.processed % 25 == 0 or i == len(cards):
            save_checkpoint(checkpoint_dir, channel_id, processed_qnames, failed_list, stats)

        # Live progress каждые 10 карточек
        if stats.processed % 10 == 0 or i == len(cards):
            pct = (stats.processed / stats.total_in_channel * 100) if stats.total_in_channel else 0
            eta_min = stats.eta_s / 60
            print(
                f"  [{i:5d}/{stats.total_in_channel:5d}] {pct:5.1f}%  "
                f"ok={stats.succeeded:5d}  fail={stats.failed:3d}  "
                f"valid={stats.validation_valid:5d}  issues={stats.validation_issues:4d}  "
                f"cost=${llm.telemetry.total_cost_usd:7.4f}  "
                f"ETA={eta_min:5.1f}min",
                flush=True,
            )

    # Финальный checkpoint
    save_checkpoint(checkpoint_dir, channel_id, processed_qnames, failed_list, stats)
    return stats


# ─── Entry ────────────────────────────────────────────────────────────


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk rebuild карточек типовых через real LLM (M-K2.5.10).",
    )
    parser.add_argument(
        "--db-path",
        default="C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db",
    )
    parser.add_argument(
        "--channel-id", required=True,
        help="Channel ID типовой (e.g. _bp30_138_24)",
    )
    parser.add_argument("--object-kind", default=None,
                        help="Фильтр: Document / Catalog / ... (default: all)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Ограничение количества карточек (для тестов)")
    parser.add_argument(
        "--only-mock", action="store_true", default=True,
        help="Rebuild только is_mock=True (default; уже real пропускаются)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Override: rebuild ВСЕ карточки включая уже real",
    )
    parser.add_argument(
        "--rate-limit-rps", type=float, default=10.0,
        help="Max requests per second к LLM API (default 10)",
    )
    parser.add_argument(
        "--checkpoint-dir",
        default=".planning/knowledge-layer-2026-05-24/phases/M-K2.5/rebuild-checkpoints",
        help="Куда писать checkpoint files (default в .planning/)",
    )
    parser.add_argument("--resume", action="store_true",
                        help="Продолжить с последнего checkpoint")
    parser.add_argument("--skip-validation", action="store_true",
                        help="Не валидировать против графа (быстрее но без QA)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Не вызывать LLM, только посчитать сколько будет")
    parser.add_argument("--confirm", action="store_true",
                        help="ОБЯЗАТЕЛЬНО для реальной записи (защита)")
    parser.add_argument("--log-level", default="WARNING")
    return parser.parse_args(argv)


async def amain(args: argparse.Namespace) -> int:
    if not args.dry_run and not args.confirm:
        print("ОШИБКА: для реальной записи нужен флаг --confirm. "
              "Используй --dry-run для проверки без записи.", file=sys.stderr)
        return 1

    db = await aiosqlite.connect(args.db_path)
    try:
        await apply_migrations(db)
        creds = await load_rebuild_credentials(db)
    finally:
        if args.dry_run:
            await db.close()
            db = None  # type: ignore

    if creds is None and not args.dry_run:
        print("ОШИБКА: credentials не установлены. "
              "Используй `python -m scripts.set_rebuild_credentials set ...` сначала.",
              file=sys.stderr)
        return 1

    # Re-открыть БД если был dry-run path
    if db is None:
        db = await aiosqlite.connect(args.db_path)
        await apply_migrations(db)

    try:
        # Создать LLM caller (для dry-run — фейковый)
        if args.dry_run:
            llm = OpenAICompatLLMCaller(
                endpoint="http://dry-run.local/v1",
                model="dry-run-model",
                api_key="dry-run-key",
            )
        else:
            llm = OpenAICompatLLMCaller(
                endpoint=creds.endpoint,
                model=creds.model,
                api_key=creds.api_key,
                max_retries=5,
                temperature=0.2,
            )

        print(f"\nREBUILD CONFIG:")
        if not args.dry_run:
            print(f"  LLM endpoint: {creds.endpoint}")
            print(f"  LLM model:    {creds.model}")
            print(f"  API key:      {creds.masked_api_key()}")
        print(f"  Channel:      {args.channel_id}")
        print(f"  Mode:         {'DRY-RUN' if args.dry_run else 'APPLY'}")

        stats = await rebuild_channel(
            db=db,
            channel_id=args.channel_id,
            llm=llm,
            checkpoint_dir=Path(args.checkpoint_dir),
            only_mock=not args.all,
            limit=args.limit,
            object_kind=args.object_kind,
            rate_limit_rps=args.rate_limit_rps,
            skip_validation=args.skip_validation,
            dry_run=args.dry_run,
            resume=args.resume,
        )

        # Финальный отчёт
        print(f"\n{'=' * 70}")
        print(f"FINAL REPORT — channel {args.channel_id}")
        print(f"{'=' * 70}")
        print(f"  Total in channel:        {stats.total_in_channel:,}")
        print(f"  Processed:               {stats.processed:,}")
        print(f"  Succeeded:               {stats.succeeded:,}")
        print(f"  Failed:                  {stats.failed:,}")
        print(f"  Skipped (already real):  {stats.skipped_already_real:,}")
        print(f"  Skipped (no context):    {stats.skipped_no_context:,}")
        if not args.skip_validation:
            print(f"  Validation valid:        {stats.validation_valid:,}")
            print(f"  Validation issues:       {stats.validation_issues:,}")
            print(f"  Validation not_in_graph: {stats.validation_not_in_graph:,}")
        print(f"\n  LLM telemetry:")
        print(f"    Total tokens in:  {llm.telemetry.total_tokens_in:,}")
        print(f"    Total tokens out: {llm.telemetry.total_tokens_out:,}")
        print(f"    Total cost USD:   ${llm.telemetry.total_cost_usd:.4f}")
        print(f"    Avg latency:      {llm.telemetry.avg_latency_s:.2f}s")
        print(f"    Success rate:     {llm.telemetry.success_rate * 100:.1f}%")
        print(f"    Failures:         {llm.telemetry.failures_by_code}")
        print(f"  Elapsed wallclock:  {stats.elapsed_s / 60:.1f} min")
        print(f"{'=' * 70}\n")

        # Exit code: 0 если успешно > 95%, 1 иначе
        if stats.processed == 0:
            return 0
        success_rate = stats.succeeded / stats.processed
        return 0 if success_rate >= 0.95 else 1

    finally:
        await db.close()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
