"""Pilot CLI: генерирует TypicalObjectCard для заданных объектов
типовой конфигурации (M-K2.5.5).

Запуск:
    cd backend
    python -m scripts.typical_cards_pilot \\
        --channel _bp30_138_24 \\
        --db data/pilot.db \\
        --kinds Document AccumulationRegister \\
        --limit 10

По умолчанию использует MockLLMCaller — реальный LLM-call не идёт,
токены не расходуются. Это для smoke pipeline (context → mock → upsert)
и для предварительной проверки структуры карточек.

Реальный LLM-call (OpenAI / NVIDIA / xAI) подключается отдельно через
`--use-llm openai` (в этом коммите не реализовано — TODO Phase 5.2).

Что делает:
1. Подключается к pilot.db
2. Находит typical_configurations запись по channel_id
3. Список MetadataObject node'ов (с фильтрами kinds + limit)
4. Для каждого:
   a. build_card_context → CardContext
   b. compute_source_hash, сравнить с existing — skip если совпал
   c. generate_card (через MockLLMCaller / LLM)
   d. upsert_card
5. Стат + JSON-сводка в stdout
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

from app.knowledge.graph_storage import list_nodes  # noqa: E402
from app.knowledge.typical import (  # noqa: E402
    CardStatus,
    MockLLMCaller,
    PROMPT_VERSION,
    build_card_context,
    generate_card_for_channel,
    get_configuration_by_channel,
    get_existing_source_hash,
    upsert_card,
)
from app.storage.migrations import apply_migrations  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cards_pilot")


async def _ensure_db(db_path: Path) -> aiosqlite.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    await conn.execute("PRAGMA foreign_keys = ON")
    await apply_migrations(conn)
    return conn


async def run_pilot(
    *,
    channel_id: str,
    db_path: Path,
    kinds: set[str] | None = None,
    limit: int = 10,
) -> dict:
    db = await _ensure_db(db_path)
    try:
        config = await get_configuration_by_channel(db, channel_id)
        if config is None:
            raise SystemExit(f"channel_id {channel_id!r} не найден в БД")

        logger.info(
            "Pilot for channel=%s kind=%s version=%s kinds=%s limit=%d",
            config.channel_id, config.config_kind, config.config_version,
            kinds or "all", limit,
        )

        # Список MetadataObject node'ов
        # Используем limit×3 чтобы был запас если есть фильтр kinds,
        # но не меньше 100k чтобы покрыть полные типовые (КА 2 ~ 20k объектов).
        fetch_limit = max(limit * 3, 100_000)
        nodes = await list_nodes(
            db, channel_id=channel_id, node_kind="MetadataObject",
            limit=fetch_limit,
        )
        if kinds:
            nodes = [n for n in nodes if n.attributes.get("kind") in kinds]
        nodes = nodes[:limit]

        llm = MockLLMCaller()

        generated = 0
        skipped = 0
        failed = 0
        tokens_in_total = 0
        tokens_out_total = 0

        t0 = time.perf_counter()
        for i, node in enumerate(nodes, start=1):
            qname = node.qualified_name
            try:
                ctx = await build_card_context(
                    db, channel_id=channel_id, object_qualified_name=qname,
                )
                if ctx is None:
                    logger.warning("Context not built for %s", qname)
                    failed += 1
                    continue

                source_hash = ctx.compute_source_hash()
                existing_hash = await get_existing_source_hash(
                    db, channel_id=channel_id, object_qualified_name=qname,
                )
                if existing_hash == source_hash:
                    logger.info("[%d/%d] SKIP %s (hash unchanged)", i, len(nodes), qname)
                    skipped += 1
                    continue

                result = await generate_card_for_channel(
                    context=ctx, channel_id=channel_id, llm=llm,
                )
                await upsert_card(
                    db,
                    card=result.card,
                    source_hash=source_hash,
                    prompt_version=PROMPT_VERSION,
                    llm_model=result.model,
                    token_usage_in=result.tokens_in,
                    token_usage_out=result.tokens_out,
                    status=CardStatus.GENERATED,
                )
                generated += 1
                if result.tokens_in:
                    tokens_in_total += result.tokens_in
                if result.tokens_out:
                    tokens_out_total += result.tokens_out
                logger.info("[%d/%d] %s — generated", i, len(nodes), qname)
            except Exception as exc:  # noqa: BLE001
                logger.exception("[%d/%d] FAIL %s: %s", i, len(nodes), qname, exc)
                failed += 1

        duration = time.perf_counter() - t0

        summary = {
            "channel_id": channel_id,
            "kinds_filter": sorted(kinds) if kinds else None,
            "limit": limit,
            "objects_processed": len(nodes),
            "generated": generated,
            "skipped": skipped,
            "failed": failed,
            "tokens_in_total": tokens_in_total,
            "tokens_out_total": tokens_out_total,
            "duration_seconds": round(duration, 3),
            "llm_model": "mock-generator-v1",
        }
        logger.info("DONE: %s", summary)
        return summary
    finally:
        await db.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pilot Object Cards Generator (mock LLM by default)"
    )
    parser.add_argument(
        "--channel", required=True,
        help="channel_id типовой (например _bp30_138_24)",
    )
    parser.add_argument(
        "--db", default="data/pilot.db",
        help="Путь к SQLite БД (default: data/pilot.db)",
    )
    parser.add_argument(
        "--kinds", nargs="*", default=None,
        help="Фильтр по MetadataKind (Document, Catalog, AccumulationRegister, ...). "
             "По умолчанию: все",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="Максимум объектов для обработки (default: 10)",
    )
    args = parser.parse_args()

    result = asyncio.run(
        run_pilot(
            channel_id=args.channel,
            db_path=Path(args.db),
            kinds=set(args.kinds) if args.kinds else None,
            limit=args.limit,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
