"""Pере-эмбеддинг карточек типовых конфигураций (M-K2.5.9.6).

Используется при смене embedding-провайдера / правил text-extraction.
Идентифицирует карточки по `embedding_model_version` и помечает их для
повторной обработки.

## Use cases

- Смена `text-embedding-3-small` на `text-embedding-3-large` (другой dim).
- Изменение `TypicalObjectCard.embedding_text` (например, добавили
  posting_flow в эмбеддинг-текст).
- Обновление text-cleanup правил (удаление voice-of-the-bot, etc.).

## Безопасность

Скрипт **обязательно** требует флаг `--confirm`. Без него — dry-run:
показывает что планируется без записи в БД.

## Использование

```bash
# Dry-run: показать что будет сделано
python -m scripts.typical_cards_reembed \\
    --channel-id _bp30_138_24 \\
    --from-version "v0" \\
    --to-version "v1.0" \\
    --model "text-embedding-3-small"

# Apply (требует --confirm)
python -m scripts.typical_cards_reembed \\
    --channel-id _bp30_138_24 \\
    --from-version "v0" \\
    --to-version "v1.0" \\
    --model "text-embedding-3-small" \\
    --confirm
```

В рамках M-K2.5.9.6 скрипт **НЕ вызывает реальный embedding API** —
только обновляет метаданные. Реальный re-embed будет добавлен в M-K3
когда подключим LLM провайдера.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import aiosqlite

# Добавляем backend root в path чтобы импорты работали при запуске
# как скрипт (а не как модуль).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.knowledge.typical.card_storage import (  # noqa: E402
    list_cards_by_channel,
    update_card_status,
)
from app.knowledge.typical.card_models import CardStatus  # noqa: E402
from app.storage.migrations import apply_migrations  # noqa: E402

logger = logging.getLogger("typical_cards_reembed")


async def find_candidates_for_reembed(
    db: aiosqlite.Connection,
    *,
    channel_id: str | None,
    from_version: str | None,
) -> list[tuple[str, str, str | None]]:
    """Находит карточки которые нужно пере-эмбедить.

    Args:
        channel_id: фильтр по каналу (None = все каналы)
        from_version: фильтр по текущей embedding_model_version
            (None / "" = карточки без version)

    Returns:
        list of (channel_id, object_qualified_name, current_version)
    """
    where = ["1 = 1"]
    params: list = []
    if channel_id:
        where.append("channel_id = ?")
        params.append(channel_id)
    if from_version == "" or from_version is None:
        where.append("(embedding_model_version IS NULL OR embedding_model_version = '')")
    else:
        where.append("embedding_model_version = ?")
        params.append(from_version)

    sql = f"""
        SELECT channel_id, object_qualified_name, embedding_model_version
        FROM typical_object_cards
        WHERE {' AND '.join(where)}
        ORDER BY channel_id, object_qualified_name
    """
    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


async def reembed_cards(
    *,
    db_path: str,
    channel_id: str | None,
    from_version: str | None,
    to_version: str,
    model: str,
    confirm: bool,
    dim: int | None = None,
) -> dict:
    """Основной workflow.

    Returns dict: {found, updated, dry_run, errors}.
    """
    db = await aiosqlite.connect(db_path)
    try:
        await apply_migrations(db)

        candidates = await find_candidates_for_reembed(
            db, channel_id=channel_id, from_version=from_version,
        )

        result: dict = {
            "found": len(candidates),
            "updated": 0,
            "dry_run": not confirm,
            "errors": 0,
            "sample": [c[1] for c in candidates[:5]],
        }

        if not confirm:
            logger.info(
                "DRY-RUN: found=%d cards. Use --confirm to actually update.",
                len(candidates),
            )
            return result

        # Apply: обновляем metadata. Реальный embed API не вызываем
        # (отложено до подключения real LLM в M-K3).
        for ch, qname, _old in candidates:
            try:
                ok = await update_card_status(
                    db,
                    channel_id=ch,
                    object_qualified_name=qname,
                    status=CardStatus.GENERATED,  # pending → не нужно, оставляем как было
                    embedding_model=model,
                    embedding_dim=dim,
                    embedding_model_version=to_version,
                )
                if ok:
                    result["updated"] += 1
                else:
                    result["errors"] += 1
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to update card %s in channel %s", qname, ch,
                )
                result["errors"] += 1

        return result
    finally:
        await db.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-embed typical object cards (M-K2.5.9.6)"
    )
    parser.add_argument(
        "--db-path",
        default="C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db",
        help="Путь к SQLite БД (default: pilot.db)",
    )
    parser.add_argument(
        "--channel-id",
        default=None,
        help="Фильтр по channel_id (default: all channels)",
    )
    parser.add_argument(
        "--from-version",
        default=None,
        help="Текущая embedding_model_version карточек. Пустая строка / "
             "не задано = найти карточки без version.",
    )
    parser.add_argument(
        "--to-version",
        required=True,
        help="Новая embedding_model_version (например 'v1.0', 'v2.0')",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Имя embedding модели (например 'text-embedding-3-small')",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=None,
        help="Размерность эмбеддинга (default: не обновлять)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="ОБЯЗАТЕЛЬНО для реальной записи. Без флага — dry-run.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    result = asyncio.run(reembed_cards(
        db_path=args.db_path,
        channel_id=args.channel_id,
        from_version=args.from_version,
        to_version=args.to_version,
        model=args.model,
        dim=args.dim,
        confirm=args.confirm,
    ))

    print()
    print("=" * 60)
    print(f"Re-embed report:")
    print(f"  Found candidates:    {result['found']:,}")
    if result["dry_run"]:
        print(f"  Mode:                DRY-RUN (no --confirm)")
        print(f"  Would update:        {result['found']:,}")
    else:
        print(f"  Mode:                APPLIED (--confirm)")
        print(f"  Updated:             {result['updated']:,}")
        print(f"  Errors:              {result['errors']:,}")
    if result["sample"]:
        print(f"  Sample first 5:")
        for q in result["sample"]:
            print(f"    - {q}")
    print("=" * 60)

    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
