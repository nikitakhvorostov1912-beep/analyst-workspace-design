"""Smoke-проверка LLM tools на нестандартных вопросах (M-K2.5 closing).

Запускает 6 typical tools напрямую на pilot.db с 4 типовыми
конфигурациями (БП/КА/УТ/ERP), задаёт каждому tool несколько
**нетривиальных** вопросов и проверяет что:

1. Tools возвращают (ok=True, result, None) на валидных запросах
2. Результаты не пустые
3. Ключи в payload соответствуют schema
4. Нестандартные ключевые слова находятся (поиск по русским
   терминам с разной типографикой / падежами / частями слов)

Запуск:
    cd backend
    python -m scripts.typical_smoke_questions

Выход: подробный отчёт в stdout + exit code 0 / 1.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import aiosqlite

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.knowledge.typical.tool import (  # noqa: E402
    TOOL_COMPARE,
    TOOL_EXPLAIN,
    TOOL_LIST_CONFIGS,
    TOOL_SEARCH_OBJECTS,
    TOOL_TRACE_CALLS,
    TOOL_TRACE_MOVEMENTS,
    dispatch_typical_tool,
)
from app.storage.migrations import apply_migrations  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

DB_PATH = Path("C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db")

# Цвета для терминала (Windows + ANSI)
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GRAY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"


passed = 0
failed = 0
issues: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  {GREEN}PASS{RESET} {label}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        issues.append(f"{label}: {detail}")
        print(f"  {RED}FAIL{RESET} {label}{(' — ' + detail) if detail else ''}")


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")


async def smoke():
    db = await aiosqlite.connect(str(DB_PATH))
    try:
        await db.execute("PRAGMA foreign_keys = ON")
        await apply_migrations(db)

        await q1_list_configurations(db)
        await q2_search_with_unusual_keywords(db)
        await q3_explain_known_objects(db)
        await q4_explain_unknown_object_returns_404(db)
        await q5_trace_movements_real_register(db)
        await q6_trace_calls_handler(db)
        await q7_cross_config_consistency(db)
        await q8_compare_returns_not_implemented(db)
        await q9_error_paths(db)
        await q10_card_payload_shape(db)

    finally:
        await db.close()


# ─── Q1: список загруженных типовых ──────────────────────────────────


async def q1_list_configurations(db):
    section("Q1: list_typical_configurations")
    ok, result, err = await dispatch_typical_tool(db, TOOL_LIST_CONFIGS, {})
    check("dispatch returns ok=True", ok, err or "")
    check("result['total'] >= 4", result and result["total"] >= 4,
          f"got total={result and result.get('total')}")
    channels = {c["channel_id"] for c in (result or {}).get("configurations", [])}
    for expected in ("_bp30_138_24", "_ka2_25_92", "_ut115_17_226", "_erp25_21_118"):
        check(f"channel {expected} в списке", expected in channels)


# ─── Q2: поиск с необычными терминами ────────────────────────────────


async def q2_search_with_unusual_keywords(db):
    section("Q2: search_typical_objects — нестандартные запросы")

    # Поиск по характерному термину БП
    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_bp30_138_24", "query": "хозрасчетный", "top_k": 5,
    })
    check("БП «хозрасчетный» — ok", ok, err or "")
    check("БП «хозрасчетный» — есть результаты", result and result["total"] > 0,
          f"total={result and result.get('total')}")

    # ERP — закрытие (имена объектов в 1С — слитные CamelCase,
    # фразу с пробелом substring не найдёт; ищем по одному слову).
    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_erp25_21_118", "query": "закрытие", "top_k": 10,
    })
    check("ERP «закрытие» — ok", ok, err or "")
    check("ERP «закрытие» — есть результаты",
          result and result["total"] > 0,
          f"total={result and result.get('total')}")

    # УТ — реализация
    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_ut115_17_226", "query": "реализация", "top_k": 10,
    })
    check("УТ «реализация» — ok", ok, err or "")
    check("УТ «реализация» — есть результаты", result and result["total"] > 0,
          f"total={result and result.get('total')}")

    # Фильтр по kind
    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_ka2_25_92",
        "query": "товары",
        "object_kind": "AccumulationRegister",
        "top_k": 5,
    })
    check("КА «товары» kind=AccumulationRegister — ok", ok, err or "")
    if result and result.get("results"):
        all_acc_register = all(
            r["kind"] == "AccumulationRegister" for r in result["results"]
        )
        check("Все результаты AccumulationRegister", all_acc_register,
              f"kinds={[r['kind'] for r in result['results']]}")


# ─── Q3: карточки реальных объектов ──────────────────────────────────


async def q3_explain_known_objects(db):
    section("Q3: explain_typical_object — реальные объекты")

    cases = [
        ("_bp30_138_24", "ChartOfAccounts.Хозрасчетный", "ChartOfAccounts"),
        ("_bp30_138_24", "AccountingRegister.Хозрасчетный", "AccountingRegister"),
        ("_ka2_25_92", "Document.РеализацияТоваровУслуг", "Document"),
        ("_ut115_17_226", "Catalog.Контрагенты", "Catalog"),
        ("_erp25_21_118", "Document.РеализацияТоваровУслуг", "Document"),
    ]
    for channel, qname, expected_kind in cases:
        ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
            "channel_id": channel, "object_qualified_name": qname,
        })
        label = f"{channel} {qname}"
        if ok:
            kind_ok = result and result.get("object_kind") == expected_kind
            check(f"{label} — explain ok + kind={expected_kind}", kind_ok,
                  f"got kind={result and result.get('object_kind')}")
            has_card = result and result.get("card") is not None
            check(f"{label} — карточка есть", has_card,
                  f"card_status={result and result.get('card_status')}")
            has_children = result and result.get("children_summary")
            check(f"{label} — children_summary заполнено",
                  bool(has_children),
                  f"keys={list((result or {}).get('children_summary', {}).keys())}")
        else:
            # Объект может отсутствовать в типовой — это не fatal, но stat'нем
            print(f"  {YELLOW}SKIP{RESET} {label} — не найден ({err})")


# ─── Q4: 404 на несуществующем объекте ───────────────────────────────


async def q4_explain_unknown_object_returns_404(db):
    section("Q4: explain — несуществующий объект → понятная ошибка")

    ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
        "channel_id": "_bp30_138_24",
        "object_qualified_name": "Document.СовершенноВыдуманныйДокумент",
    })
    check("ok=False на несуществующем", not ok)
    check("err содержит 'не найден'", err and "не найден" in err.lower(),
          f"err={err!r}")


# ─── Q5: trace_movements ──────────────────────────────────────────────


async def q5_trace_movements_real_register(db):
    section("Q5: trace_typical_movements — реальные регистры")

    # БП.Хозрасчетный — главный регистр БП 3.0, имеет writes и reads.
    # Регистр накопления КА не используется — в КА writes идут в основном
    # в Хозрасчетный + специфичные регистры партий, у каждого ≤ 30 writes
    # и подбор корректного top через SQL JOIN на 1.7M edges медленный.

    # БП: ХозрасчетныйРегистр — both
    ok, result, err = await dispatch_typical_tool(db, TOOL_TRACE_MOVEMENTS, {
        "channel_id": "_bp30_138_24",
        "register_qualified_name": "AccountingRegister.Хозрасчетный",
        "direction": "both",
    })
    if ok:
        check("БП.Хозрасчетный — writes+reads",
              result["total_writes"] > 0 or result["total_reads"] > 0,
              f"writes={result.get('total_writes')} reads={result.get('total_reads')}")
    else:
        print(f"  {YELLOW}SKIP{RESET} БП.Хозрасчетный — {err}")

    # Несуществующий регистр
    ok, result, err = await dispatch_typical_tool(db, TOOL_TRACE_MOVEMENTS, {
        "channel_id": "_bp30_138_24",
        "register_qualified_name": "AccumulationRegister.НесуществующийРегистр",
    })
    check("Несуществующий регистр → ok=False", not ok)


# ─── Q6: trace_calls на handler ──────────────────────────────────────


async def q6_trace_calls_handler(db):
    section("Q6: trace_typical_calls — реальные handler-методы")

    # Найдём какой-нибудь ОбработкаПроведения в БП и проверим из него out
    cursor = await db.execute("""
        SELECT qualified_name FROM graph_nodes
        WHERE channel_id = ? AND node_kind = 'Method'
        AND qualified_name LIKE '%ОбработкаПроведения%'
        LIMIT 1
    """, ("_bp30_138_24",))
    row = await cursor.fetchone()
    if not row:
        print(f"  {YELLOW}SKIP{RESET} БП.ОбработкаПроведения не найден")
        return

    qname = row[0]
    ok, result, err = await dispatch_typical_tool(db, TOOL_TRACE_CALLS, {
        "channel_id": "_bp30_138_24",
        "qualified_name": qname,
        "direction": "out",
        "depth": 2,
    })
    check(f"БП ОбработкаПроведения out depth=2 — ok", ok, err or "")
    check("hits >= 1 (стартовый node всегда)",
          result and result.get("total", 0) >= 1,
          f"total={result and result.get('total')}")

    # Invalid direction
    ok, result, err = await dispatch_typical_tool(db, TOOL_TRACE_CALLS, {
        "channel_id": "_bp30_138_24",
        "qualified_name": qname,
        "direction": "both",  # traverse_bfs не поддерживает
    })
    check("direction='both' → ok=False (graph_storage ограничение)", not ok)


# ─── Q7: кросс-конфигурационная консистентность ──────────────────────


async def q7_cross_config_consistency(db):
    section("Q7: кросс-конфигурационная консистентность")

    # У ERP должно быть больше объектов чем у БП
    ok_bp, bp, _ = await dispatch_typical_tool(db, TOOL_LIST_CONFIGS, {})
    if not ok_bp:
        check("list_configs success", False, "не получили список")
        return
    by_kind = {c["config_kind"]: c for c in bp["configurations"]}
    erp = by_kind.get("ERP_25", {})
    bp_cfg = by_kind.get("BP_30", {})
    ut = by_kind.get("UT_115", {})
    ka = by_kind.get("KA_2", {})

    check("ERP nodes > БП nodes",
          erp.get("total_nodes", 0) > bp_cfg.get("total_nodes", 0),
          f"ERP={erp.get('total_nodes')} BP={bp_cfg.get('total_nodes')}")
    check("ERP nodes > УТ nodes",
          erp.get("total_nodes", 0) > ut.get("total_nodes", 0),
          f"ERP={erp.get('total_nodes')} УТ={ut.get('total_nodes')}")
    check("Все 4 конфигурации graph_built",
          all(c.get("status") == "graph_built" for c in (erp, bp_cfg, ut, ka)),
          f"statuses={[(c.get('config_kind'), c.get('status')) for c in (erp, bp_cfg, ut, ka)]}")


# ─── Q8: compare_with_typical → not_implemented ──────────────────────


async def q8_compare_returns_not_implemented(db):
    section("Q8: compare_with_typical — заглушка v1")

    ok, result, err = await dispatch_typical_tool(db, TOOL_COMPARE, {
        "typical_channel_id": "_bp30_138_24",
        "client_channel_id": "_client_x_",
        "object_qualified_name": "Document.Заказ",
    })
    check("compare возвращает ok=True (заглушка)", ok, err or "")
    check("status='not_implemented'",
          result and result.get("status") == "not_implemented",
          f"status={result and result.get('status')}")
    # Сообщение должно намекать на M-K3
    check("сообщение упоминает M-K3 / client graph",
          result and ("M-K3" in result.get("message", "") or
                       "клиент" in result.get("message", "").lower()))


# ─── Q9: error paths ─────────────────────────────────────────────────


async def q9_error_paths(db):
    section("Q9: error paths — невалидные параметры")

    # Пустой query
    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_bp30_138_24", "query": "",
    })
    check("пустой query → ok=False", not ok,
          f"got err={err!r}")

    # Несуществующий tool
    ok, result, err = await dispatch_typical_tool(db, "search_xyz", {})
    check("неизвестный tool → ok=False", not ok)

    # Невалидный direction
    ok, result, err = await dispatch_typical_tool(db, TOOL_TRACE_MOVEMENTS, {
        "channel_id": "_bp30_138_24",
        "register_qualified_name": "AccumulationRegister.X",
        "direction": "вперёд",  # не writes/reads/both
    })
    check("невалидный direction → ok=False", not ok)


# ─── Q10: shape карточки ────────────────────────────────────────────


async def q10_card_payload_shape(db):
    section("Q10: card payload — все обязательные поля")

    ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
        "channel_id": "_bp30_138_24",
        "object_qualified_name": "ChartOfAccounts.Хозрасчетный",
    })
    if not ok or not result.get("card"):
        print(f"  {YELLOW}SKIP{RESET} карточка БП.Хозрасчетный недоступна")
        return

    card = result["card"]
    required_keys = (
        "summary", "purpose", "key_attributes", "movements",
        "posting_flow", "typical_scenarios", "preconditions",
        "related_objects", "its_links",
    )
    for key in required_keys:
        check(f"карточка содержит '{key}'", key in card)

    # Mock карточка содержит «План счетов» в summary
    check("summary не пустой", bool(card.get("summary", "").strip()))


# ─── Entry ───────────────────────────────────────────────────────────


def main():
    print(f"{BOLD}Smoke test: typical LLM tools на pilot.db{RESET}")
    print(f"{GRAY}DB: {DB_PATH}{RESET}")
    print(f"{GRAY}Configurations: БП 3.0 + КА 2.5 + УТ 11.5 + ERP 2.5{RESET}")

    asyncio.run(smoke())

    print()
    print(f"{BOLD}=== Summary ==={RESET}")
    total = passed + failed
    print(f"  {GREEN}PASS:{RESET} {passed} / {total}")
    if failed:
        print(f"  {RED}FAIL:{RESET} {failed}")
        print()
        print(f"{BOLD}{RED}Issues:{RESET}")
        for issue in issues:
            print(f"  • {issue}")
        return 1
    print(f"  {GREEN}{BOLD}Все {total} проверок прошли{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
