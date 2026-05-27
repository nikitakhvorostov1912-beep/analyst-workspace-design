"""Apply сгенерированных Claude карточек в БД (M-K2.5.11.2).

Читает response JSON файл (сгенерированный Claude в сессии), парсит каждую
карточку через _payload_to_card (с defensive truncation), валидирует против
графа через validate_card_against_graph, сохраняет в БД с метками:
- llm_model = "claude-opus-4-7-via-session"
- prompt_version = "v2-claude-opus"
- is_mock = False

## Формат response JSON

```json
{
  "channel_id": "_bp30_138_24",
  "items": [
    {
      "qname": "Document.РеализацияТоваровУслуг",
      "source_hash": "...",  // из batch файла, для идемпотентности
      "card": {
        "summary": "...",
        "purpose": "...",
        "key_attributes": [{"name": "...", "role": "..."}, ...],
        "movements": [{"register": "...", "direction": "...", "condition": "..."}, ...],
        "posting_flow": [...],
        "typical_scenarios": [...],
        "preconditions": [...],
        "related_objects": [...],
        "its_links": []
      }
    },
    ...
  ]
}
```

## Workflow

1. Прочитать response JSON
2. Для каждой карточки:
   a. Реконструировать TypicalObjectCard через CardContext-like структуру
   b. Validate через validate_card_against_graph
   c. upsert_card(is_mock=False, llm_model="claude-opus-4-7-via-session")
   d. save_validation_result
3. Финальный отчёт: applied / failed / validation stats

## Использование

```bash
python -m scripts.apply_claude_batch \\
    --response .planning/.../claude-responses/response-001-bp-pilot.json \\
    --confirm
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

from app.knowledge.typical.card_models import (  # noqa: E402
    CardAttribute,
    CardMovement,
    CardStatus,
    TypicalObjectCard,
    normalize_direction,
)
from app.knowledge.typical.card_models import (  # noqa: E402
    MAX_ATTR_NAME_LEN,
    MAX_ATTR_ROLE_LEN,
    MAX_ITS_LINK_LEN,
    MAX_ITS_LINKS,
    MAX_KEY_ATTRIBUTES,
    MAX_MOVEMENT_CONDITION_LEN,
    MAX_MOVEMENTS,
    MAX_POSTING_FLOW,
    MAX_POSTING_STEP_LEN,
    MAX_PRECONDITION_LEN,
    MAX_PRECONDITIONS,
    MAX_PURPOSE_LEN,
    MAX_REGISTER_NAME_LEN,
    MAX_RELATED_NAME_LEN,
    MAX_RELATED_OBJECTS,
    MAX_SCENARIO_LEN,
    MAX_SUMMARY_LEN,
    MAX_TYPICAL_SCENARIOS,
)
from app.knowledge.typical.card_storage import upsert_card  # noqa: E402
from app.knowledge.typical.card_validator import (  # noqa: E402
    save_validation_result,
    validate_card_against_graph,
)
from app.storage.migrations import apply_migrations  # noqa: E402

logger = logging.getLogger("apply_claude_batch")


LLM_MODEL_TAG = "claude-opus-4-7-via-session"
PROMPT_VERSION_TAG = "v2-claude-opus"


def _build_card_from_response_item(
    item: dict[str, Any],
    channel_id: str,
) -> TypicalObjectCard:
    """Парсит item из response JSON в TypicalObjectCard с защитной truncation.

    Использует те же лимиты что Pydantic — лучше обрезать defensive чем
    падать ValidationError.
    """
    qname = item["qname"]
    object_kind = qname.split(".", 1)[0] if "." in qname else "Unknown"
    card_data = item.get("card") or {}

    # Atomic truncation для безопасности (даже если Claude нечаянно превысил)
    def _trunc(s: Any, n: int) -> str:
        return str(s or "")[:n]

    summary = _trunc(card_data.get("summary"), MAX_SUMMARY_LEN)
    purpose = _trunc(card_data.get("purpose"), MAX_PURPOSE_LEN)

    # key_attributes
    raw_attrs = (card_data.get("key_attributes") or [])[:MAX_KEY_ATTRIBUTES]
    key_attributes = tuple(
        CardAttribute(
            name=_trunc(a.get("name"), MAX_ATTR_NAME_LEN),
            role=_trunc(a.get("role"), MAX_ATTR_ROLE_LEN),
        )
        for a in raw_attrs
        if isinstance(a, dict) and a.get("name")
    )

    # movements — Claude должен выдать canonical, но нормализуем на всякий случай
    raw_movements = (card_data.get("movements") or [])[:MAX_MOVEMENTS]
    movements_list: list[CardMovement] = []
    for m in raw_movements:
        if not isinstance(m, dict):
            continue
        register = _trunc(m.get("register"), MAX_REGISTER_NAME_LEN)
        if not register:
            continue
        # Skip если префикс не canonical (защита от LLM ошибки)
        kind_prefix = register.split(".", 1)[0]
        if kind_prefix not in ("AccumulationRegister", "InformationRegister",
                                "AccountingRegister", "CalculationRegister"):
            logger.warning("Skip movement с неканоническим префиксом: %s", register)
            continue
        try:
            mv = CardMovement(
                register=register,
                direction=normalize_direction(m.get("direction")),
                condition=_trunc(m.get("condition"), MAX_MOVEMENT_CONDITION_LEN),
            )
            movements_list.append(mv)
        except Exception as e:  # noqa: BLE001
            logger.warning("Skip movement %r — %s", register, e)
    movements = tuple(movements_list)

    # Строковые списки с per-element trunc
    def _str_tuple(value: Any, max_items: int, max_len: int) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        result = []
        for v in value[:max_items]:
            if v is None:
                continue
            s = str(v).strip()[:max_len]
            if s:
                result.append(s)
        return tuple(result)

    return TypicalObjectCard(
        object_qualified_name=qname,
        object_kind=object_kind,
        channel_id=channel_id,
        summary=summary,
        purpose=purpose,
        key_attributes=key_attributes,
        movements=movements,
        posting_flow=_str_tuple(card_data.get("posting_flow"),
                                MAX_POSTING_FLOW, MAX_POSTING_STEP_LEN),
        typical_scenarios=_str_tuple(card_data.get("typical_scenarios"),
                                      MAX_TYPICAL_SCENARIOS, MAX_SCENARIO_LEN),
        preconditions=_str_tuple(card_data.get("preconditions"),
                                  MAX_PRECONDITIONS, MAX_PRECONDITION_LEN),
        related_objects=_str_tuple(card_data.get("related_objects"),
                                    MAX_RELATED_OBJECTS, MAX_RELATED_NAME_LEN),
        its_links=_str_tuple(card_data.get("its_links"),
                              MAX_ITS_LINKS, MAX_ITS_LINK_LEN),
    )


async def apply_batch(
    db: aiosqlite.Connection,
    response_path: Path,
) -> dict[str, Any]:
    """Применить response JSON в БД."""
    data = json.loads(response_path.read_text(encoding="utf-8"))
    channel_id = data["channel_id"]
    items = data.get("items") or []

    stats = {
        "channel_id": channel_id,
        "total": len(items),
        "applied": 0,
        "failed": 0,
        "validation_valid": 0,
        "validation_issues": 0,
        "validation_not_in_graph": 0,
        "per_qname": [],
    }

    for item in items:
        qname = item.get("qname", "?")
        try:
            card = _build_card_from_response_item(item, channel_id)
            source_hash = item.get("source_hash") or f"claude-applied-{qname}"

            # Validate
            validation = await validate_card_against_graph(
                db, channel_id=channel_id, card=card,
            )

            if validation.status == "valid":
                stats["validation_valid"] += 1
            elif validation.status == "issues_found":
                stats["validation_issues"] += 1
            else:
                stats["validation_not_in_graph"] += 1

            # Save card
            await upsert_card(
                db,
                card=card,
                source_hash=source_hash,
                prompt_version=PROMPT_VERSION_TAG,
                llm_model=LLM_MODEL_TAG,
                status=CardStatus.GENERATED,
                is_mock=False,
            )
            # Save validation
            await save_validation_result(
                db, channel_id=channel_id,
                object_qualified_name=qname, result=validation,
            )

            stats["applied"] += 1
            stats["per_qname"].append({
                "qname": qname,
                "status": "applied",
                "validation": validation.status,
                "errors": validation.error_count,
                "warnings": validation.warning_count,
                "summary_len": len(card.summary),
                "purpose_len": len(card.purpose),
                "movements_count": len(card.movements),
                "scenarios_count": len(card.typical_scenarios),
            })
        except Exception as e:  # noqa: BLE001
            logger.exception("Apply failed for %s", qname)
            stats["failed"] += 1
            stats["per_qname"].append({
                "qname": qname,
                "status": "failed",
                "error": f"{type(e).__name__}: {e}",
            })

    return stats


async def amain(args: argparse.Namespace) -> int:
    response_path = Path(args.response)
    if not response_path.exists():
        print(f"ОШИБКА: response file не найден: {response_path}", file=sys.stderr)
        return 1

    if not args.confirm:
        print("ОШИБКА: для реальной записи в БД нужен флаг --confirm", file=sys.stderr)
        return 1

    db = await aiosqlite.connect(args.db_path)
    try:
        await apply_migrations(db)
        stats = await apply_batch(db, response_path)

        print(f"\n{'=' * 70}")
        print(f"APPLY REPORT")
        print(f"{'=' * 70}")
        print(f"  Channel:                 {stats['channel_id']}")
        print(f"  Total in response:       {stats['total']}")
        print(f"  Applied successfully:    {stats['applied']}")
        print(f"  Failed:                  {stats['failed']}")
        print(f"\n  Validation:")
        print(f"    valid:                 {stats['validation_valid']}")
        print(f"    issues_found:          {stats['validation_issues']}")
        print(f"    object_not_in_graph:   {stats['validation_not_in_graph']}")
        print(f"\n  Per-card:")
        for r in stats["per_qname"]:
            if r["status"] == "applied":
                print(
                    f"    OK   {r['qname']:50s}  "
                    f"sum={r['summary_len']:3d}  "
                    f"pur={r['purpose_len']:3d}  "
                    f"mov={r['movements_count']:2d}  "
                    f"sc={r['scenarios_count']:2d}  "
                    f"valid={r['validation']} (err={r['errors']}, warn={r['warnings']})"
                )
            else:
                print(f"    FAIL {r['qname']:50s}  {r.get('error', '')}")
        print(f"{'=' * 70}\n")

        return 0 if stats["failed"] == 0 else 1
    finally:
        await db.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply Claude-generated cards into БД (M-K2.5.11.2)",
    )
    parser.add_argument(
        "--db-path",
        default="C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db",
    )
    parser.add_argument("--response", required=True,
                        help="Путь к response JSON файлу")
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
