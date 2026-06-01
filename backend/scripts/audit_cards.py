"""Structural audit knowledge-карточек is_mock=0.

Без LLM — только правила. Каждая карточка получает score 0-5 по
взвешенным penalties за нарушения rubric. Карточки с score < threshold
помечаются is_mock=1 (если --apply) для пересборки через NIM.

## Rubric (kind-aware)

Базовый score = 5.0. Penalties:

- **−2.0** kind ∈ NO_ATTR_KINDS и key_attributes != []
  (CommonCommand/Module/Form/etc. не должны иметь атрибуты)
- **−1.5** key_attributes содержит META-поля ['name','kind','qname','handlers','comment']
  (модель скопировала JSON-payload в выход)
- **−1.0** kind ∈ HAS_ATTR_KINDS и key_attributes == []
  (Catalog/Document/Register должны иметь реквизиты)
- **−1.0** summary < 80 chars (слишком короткое)
- **−1.0** purpose < 200 chars (слишком краткое описание)
- **−1.0** typical_scenarios count < 2 (мало сценариев)
- **−1.0** referenced_by в графе непустое, но related_objects == []
  (модель забыла related)
- **−0.5** kind ∈ {Document, AccumulationRegister, AccountingRegister}
  и movements == [] но writes_to из графа непустое

## Использование

    # Только показать distribution + список violations:
    python -m scripts.audit_cards

    # Применить reset для нарушителей (score < 4.5):
    python -m scripts.audit_cards --apply

    # Только определённый канал:
    python -m scripts.audit_cards --channel-id _bp30_138_24

    # Альтернативный порог:
    python -m scripts.audit_cards --min-score 4.0 --apply
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import aiosqlite

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.knowledge.typical.card_context import build_card_context  # noqa: E402
from scripts.prepare_claude_batch_compact import _compact_context  # noqa: E402

logger = logging.getLogger("audit_cards")

DB_PATH = "C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db"

# Типы без собственных атрибутов
NO_ATTR_KINDS = {
    "CommonCommand", "CommonModule", "CommonForm", "CommandGroup",
    "Subsystem", "HTTPService", "WebService", "Style", "StyleItem",
    "FunctionalOption", "FunctionalOptionsParameter", "EventSubscription",
    "ScheduledJob", "Constant", "SessionParameter", "Language", "Role",
    "WSReference", "XDTOPackage", "CommonPicture", "CommonTemplate",
}

# Типы, у которых typical_scenarios не имеют смысла (картинки, макеты, подсистемы,
# параметры сеанса и пр. технические/структурные объекты) — не штрафуем за их отсутствие.
NO_SCENARIO_KINDS = {
    "CommonPicture", "CommonTemplate", "Style", "StyleItem",
    "Subsystem", "SessionParameter", "FunctionalOption",
    "FunctionalOptionsParameter", "DefinedType", "CommandGroup",
    "Language", "CommonAttribute", "XDTOPackage", "WSReference",
    "CommonCommand", "EventSubscription", "ScheduledJob", "Constant",
}

# Типы для которых key_attributes должен быть
HAS_ATTR_KINDS = {
    "Catalog", "Document", "ChartOfAccounts", "ChartOfCharacteristicTypes",
    "ChartOfCalculationTypes", "ExchangePlan", "BusinessProcess", "Task",
}

# Типы для которых ожидаются movements (документы пишут в регистры)
HAS_MOVEMENTS_KINDS = {"Document"}

# Типы регистров (сами имеют входящие writes_to)
REGISTER_KINDS = {
    "AccumulationRegister", "AccountingRegister",
    "InformationRegister", "CalculationRegister",
}

META_FIELDS_BLACKLIST = {
    "name", "kind", "qname", "handlers", "comment",
    "type", "имя", "тип", "комментарий", "обработчики",
}


def score_card(
    card: dict[str, Any],
    kind: str,
    ctx_summary: dict[str, Any] | None,
) -> tuple[float, list[str]]:
    """Возвращает (score, violations)."""
    score = 5.0
    violations: list[str] = []

    ka = card.get("key_attributes") or []
    if not isinstance(ka, list):
        ka = []
    ka_names_lower = [
        (a.get("name", "") if isinstance(a, dict) else str(a)).strip().lower()
        for a in ka
    ]

    # P1: NO_ATTR_KIND с непустым key_attributes
    if kind in NO_ATTR_KINDS and len(ka) > 0:
        score -= 2.0
        violations.append(f"NO_ATTR_KIND[{kind}] но key_attributes={len(ka)}")

    # P2: META-поля в key_attributes
    bad_meta = set(ka_names_lower) & META_FIELDS_BLACKLIST
    if bad_meta:
        score -= 1.5
        violations.append(f"META-поля в ka: {sorted(bad_meta)}")

    # P3: HAS_ATTR_KIND с пустым key_attributes — штраф ТОЛЬКО если у объекта
    # реально есть реквизиты в графе (иначе карточка корректна, штрафовать = гнать
    # модель выдумывать несуществующие реквизиты).
    if kind in HAS_ATTR_KINDS and len(ka) == 0:
        ctx_attrs = ctx_summary.get("attrs") if ctx_summary else None
        if ctx_attrs:
            score -= 1.0
            violations.append(
                f"HAS_ATTR_KIND[{kind}] но key_attributes пустой "
                f"(в графе attrs={len(ctx_attrs)})"
            )

    # P4: summary слишком короткое
    summary = card.get("summary") or ""
    if len(summary) < 80:
        score -= 1.0
        violations.append(f"summary слишком короткое ({len(summary)} < 80)")

    # P5: purpose слишком короткое
    purpose = card.get("purpose") or ""
    if len(purpose) < 200:
        score -= 1.0
        violations.append(f"purpose слишком короткое ({len(purpose)} < 200)")

    # P6: мало typical_scenarios — кроме видов, где сценарии не имеют смысла
    scenarios = card.get("typical_scenarios") or []
    if len(scenarios) < 2 and kind not in NO_SCENARIO_KINDS:
        score -= 1.0
        violations.append(f"typical_scenarios={len(scenarios)} < 2")

    # P7: graph context check (если есть)
    if ctx_summary is not None:
        ref_in = ctx_summary.get("referenced_by") or []
        rel_out = card.get("related_objects") or []
        # related_objects забыт когда есть referenced_by
        if len(ref_in) > 0 and len(rel_out) == 0:
            score -= 1.0
            violations.append(
                f"referenced_by={len(ref_in)} но related_objects пуст"
            )
        # movements забыты для Document когда есть writes_to
        if kind in HAS_MOVEMENTS_KINDS:
            writes_to = ctx_summary.get("writes_to") or []
            movements = card.get("movements") or []
            if len(writes_to) > 0 and len(movements) == 0:
                score -= 0.5
                violations.append(
                    f"Document с writes_to={len(writes_to)} но movements пуст"
                )

    return max(0.0, score), violations


async def audit_one(
    db: aiosqlite.Connection,
    rid: int,
    qn: str,
    kind: str,
    channel_id: str,
    payload: str,
    *,
    use_graph: bool = True,
) -> tuple[float, list[str]]:
    """Audit одной карточки."""
    try:
        card = json.loads(payload)
    except Exception as e:
        return 0.0, [f"JSON parse fail: {e}"]

    ctx_summary = None
    if use_graph:
        try:
            ctx = await build_card_context(
                db, channel_id=channel_id, object_qualified_name=qn
            )
            if ctx is not None:
                ctx_dict = (
                    dataclasses.asdict(ctx) if dataclasses.is_dataclass(ctx)
                    else dict(ctx)
                )
                ctx_summary = _compact_context(ctx_dict)
        except Exception as e:
            logger.debug("ctx fail %s: %s", qn, e)

    return score_card(card, kind, ctx_summary)


async def main(args: argparse.Namespace) -> int:
    db = await aiosqlite.connect(args.db_path)
    try:
        # Выгрузка всех is_mock=0 (опционально по каналу и kind)
        sql = (
            "SELECT id, object_qualified_name, object_kind, channel_id, "
            "card_payload, llm_model FROM typical_object_cards WHERE is_mock=0"
        )
        params: list[Any] = []
        if args.channel_id:
            sql += " AND channel_id = ?"
            params.append(args.channel_id)
        if args.kind:
            sql += " AND object_kind = ?"
            params.append(args.kind)

        rows = await (await db.execute(sql, params)).fetchall()
        total = len(rows)
        logger.info("Аудит %d карточек (is_mock=0)", total)

        scores: list[tuple[float, int, str, str, str, list[str]]] = []
        sem = asyncio.Semaphore(20)  # для concurrent graph queries

        async def process(row):
            async with sem:
                rid, qn, kind, ch, payload, model = row
                score, vios = await audit_one(
                    db, rid, qn, kind, ch, payload, use_graph=not args.no_graph
                )
                return (score, rid, qn, kind, model, vios)

        tasks = [process(r) for r in rows]
        for i, fut in enumerate(asyncio.as_completed(tasks), 1):
            scores.append(await fut)
            if i % 500 == 0:
                logger.info("Прогресс: %d/%d", i, total)

        # Distribution
        score_buckets = Counter()
        for s, *_ in scores:
            bucket = f"{int(s):d}.0-{int(s)+1:d}.0" if s >= 0 else "0.0"
            if s == 5.0:
                bucket = "5.0"
            elif s >= 4.5:
                bucket = "4.5-4.9"
            elif s >= 4.0:
                bucket = "4.0-4.4"
            elif s >= 3.0:
                bucket = "3.0-3.9"
            elif s >= 2.0:
                bucket = "2.0-2.9"
            else:
                bucket = "0.0-1.9"
            score_buckets[bucket] += 1

        print(f"\n{'='*70}\nAUDIT REPORT (total={total})\n{'='*70}")
        print("\n=== Distribution scores ===")
        for bucket in ["5.0", "4.5-4.9", "4.0-4.4", "3.0-3.9", "2.0-2.9", "0.0-1.9"]:
            n = score_buckets[bucket]
            pct = 100 * n / total if total else 0
            bar = "█" * int(pct / 2)
            print(f"  {bucket:>8s}: {n:>5d} ({pct:>5.1f}%) {bar}")

        # Violations stats
        violations_counter = Counter()
        for s, _, _, _, _, vios in scores:
            for v in vios:
                # Нормализовать к pattern
                key = v.split("(")[0].split(":")[0].strip()
                violations_counter[key] += 1

        print("\n=== Топ violations ===")
        for v, n in violations_counter.most_common(10):
            print(f"  {n:>5d}  {v}")

        # Bad cards (score < threshold)
        bad = [(s, rid, qn, kind, model, vios) for s, rid, qn, kind, model, vios in scores if s < args.min_score]
        bad.sort(key=lambda x: x[0])  # худшие первыми

        print(f"\n=== Карточек score < {args.min_score}: {len(bad)} ===")
        print("Распределение по kinds:")
        kinds = Counter(b[3] for b in bad)
        for k, n in kinds.most_common():
            print(f"  {k}: {n}")

        print(f"\nПримеры (топ-20 худших):")
        for s, rid, qn, kind, model, vios in bad[:20]:
            print(f"  {s:.1f} [{kind}] {qn}")
            for v in vios:
                print(f"      → {v}")

        # Apply reset
        if args.apply and bad:
            print(f"\n=== APPLY: reset {len(bad)} карточек в is_mock=1 ===")
            ids = [b[1] for b in bad]
            # Batch UPDATE
            for i in range(0, len(ids), 500):
                chunk = ids[i:i+500]
                await db.execute(
                    f"UPDATE typical_object_cards SET is_mock=1, "
                    f"llm_model='mock-generator-v1', prompt_version='v1' "
                    f"WHERE id IN ({','.join('?'*len(chunk))})",
                    chunk,
                )
            await db.commit()
            print(f"Reset done: {len(ids)} rows")
        elif bad:
            print(f"\n(dry-run; для применения: --apply)")

        return 0
    finally:
        await db.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Structural audit knowledge cards")
    p.add_argument("--db-path", default=DB_PATH)
    p.add_argument("--channel-id", help="Только этот канал")
    p.add_argument("--kind", help="Только этот object_kind")
    p.add_argument("--min-score", type=float, default=4.5, help="Порог пересборки")
    p.add_argument("--apply", action="store_true", help="Реально reset нарушителей")
    p.add_argument("--no-graph", action="store_true", help="Без проверок против графа (быстрее)")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def main_sync(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return asyncio.run(main(args))


if __name__ == "__main__":
    sys.exit(main_sync())
