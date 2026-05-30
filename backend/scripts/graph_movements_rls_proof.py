"""Валидация фиксов движений (Phase F) и RLS per-right на пересобранном УТ.

Гоняет РЕАЛЬНЫЕ инструменты (dispatch_typical_tool) против
data/graph-index/ut115.db (channel _bench) и сверяет:
  T1 движения: ТоварыНаСкладах теперь имеет писателей-документы (было 0);
  T2 движения: РеализацияТоваровУслуг пишет в свой набор регистров;
  T3 RLS: пара (роль,объект) с разными условиями отдаёт ВСЕ права/условия;
  T4 агрегаты: WRITES_TO/RESTRICTS итоги.

Запуск из backend/:  python scripts/graph_movements_rls_proof.py
Вывод UTF-8 → ../data/graph-index/_mov_rls_proof.txt
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sqlite3
import sys

import aiosqlite

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.knowledge.typical.tool import dispatch_typical_tool  # noqa: E402

DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "graph-index", "ut115.db")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "graph-index", "_mov_rls_proof.txt")
CH = "_bench"
TOVARY = "AccumulationRegister.ТоварыНаСкладах"
RTU = "Document.РеализацияТоваровУслуг"


def pick_lossy_rls_object() -> tuple[str, str] | None:
    """Находит (object_qname, role_qname) с >1 разными условиями в одном ребре."""
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    q = ("select d.qualified_name obj, s.qualified_name role, e.attributes a "
         "from graph_edges e join graph_nodes d on d.id=e.dst_id "
         "join graph_nodes s on s.id=e.src_id where e.edge_kind='RESTRICTS'")
    for r in c.execute(q):
        a = json.loads(r["a"]) if r["a"] else {}
        rlist = a.get("restrictions")
        if isinstance(rlist, list) and len({x.get("condition") for x in rlist}) > 1:
            c.close()
            return r["obj"], r["role"]
    c.close()
    return None


async def main(buf: io.StringIO):
    def w(s=""):
        buf.write(s + "\n")

    db = await aiosqlite.connect(DB)
    db.row_factory = aiosqlite.Row
    try:
        # T1 — писатели ТоварыНаСкладах (movements writes)
        w("=" * 72)
        w(f"ТЕСТ 1  trace_typical_movements(writes)  {TOVARY}")
        ok, res, err = await dispatch_typical_tool(
            db, "trace_typical_movements",
            {"channel_id": CH, "register_qualified_name": TOVARY, "direction": "writes"})
        if not ok:
            w(f"  ОШИБКА: {err}")
        else:
            writers = res.get("writes", [])
            docs = [x["method_qualified_name"] for x in writers
                    if x["method_qualified_name"].startswith("Document.")]
            w(f"  писателей всего: {res.get('total_writes')}, из них документов: {len(docs)}")
            for d in sorted(docs)[:8]:
                w(f"     <- {d}")
            verdict = "PASS" if len(docs) >= 30 else "FAIL (было 0 — фикс не сработал)"
            w(f"  ВЕРДИКТ ТЕСТ 1: {verdict}  (ожидалось ~44 документа)")

        # T2 — РеализацияТоваровУслуг пишет в свои регистры (через документ-узел)
        w("")
        w("=" * 72)
        w(f"ТЕСТ 2  WRITES_TO от {RTU} (Document→Register, метадата)")
        rtu = await db.execute(
            "select id from graph_nodes where channel_id=? and qualified_name=?",
            (CH, RTU))
        row = await rtu.fetchone()
        if not row:
            w("  ОШИБКА: документ не найден")
        else:
            cur = await db.execute(
                "select d.qualified_name qn from graph_edges e "
                "join graph_nodes d on d.id=e.dst_id "
                "where e.edge_kind='WRITES_TO' and e.src_id=?", (row["id"],))
            regs = [r["qn"] for r in await cur.fetchall()]
            has_tovary = TOVARY in regs
            w(f"  регистров движений у РТУ: {len(regs)}  (ожидалось ~43)")
            w(f"  включает ТоварыНаСкладах: {has_tovary}")
            verdict = "PASS" if len(regs) >= 30 and has_tovary else "FAIL"
            w(f"  ВЕРДИКТ ТЕСТ 2: {verdict}")

        # T3 — RLS per-right: объект с разными условиями отдаёт все
        w("")
        w("=" * 72)
        w("ТЕСТ 3  explain_rls_restrictions — сохранение per-right условий")
        pick = pick_lossy_rls_object()
        if pick is None:
            w("  не нашёл пары с разными условиями — возможно RLS v2 не применился")
            w("  ВЕРДИКТ ТЕСТ 3: FAIL")
        else:
            obj, role = pick
            ok, res, err = await dispatch_typical_tool(
                db, "explain_rls_restrictions",
                {"channel_id": CH, "object_qualified_name": obj})
            role_entries = [r for r in res["restrictions"] if r["role"] == role]
            conds = {r["condition"] for r in role_entries}
            w(f"  объект: {obj}")
            w(f"  роль:   {role}")
            w(f"  записей для роли: {len(role_entries)}, различных условий: {len(conds)}")
            w(f"  roles_total={res.get('roles_total')}  total(per-right)={res.get('total')}")
            verdict = "PASS" if len(conds) > 1 else "FAIL (условия схлопнулись)"
            w(f"  ВЕРДИКТ ТЕСТ 3: {verdict}")

        # T4 — агрегаты
        w("")
        w("=" * 72)
        w("ТЕСТ 4  агрегаты графа")
        for kind in ("WRITES_TO", "RESTRICTS", "CALLS"):
            cur = await db.execute(
                "select count(*) n from graph_edges where edge_kind=?", (kind,))
            n = (await cur.fetchone())["n"]
            w(f"  {kind:12} = {n}")
        cur = await db.execute(
            "select count(*) n from graph_edges e join graph_nodes s on s.id=e.src_id "
            "where e.edge_kind='WRITES_TO' and s.qualified_name like 'Document.%'")
        doc_writes = (await cur.fetchone())["n"]
        w(f"  WRITES_TO от документов (метадата): {doc_writes}  (ожидалось ~2391)")
    finally:
        await db.close()


if __name__ == "__main__":
    buf = io.StringIO()
    asyncio.run(main(buf))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print(f"written -> {OUT}")
