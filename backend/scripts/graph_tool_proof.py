"""Доказательство слоя инструментов на ИСПРАВЛЕННОМ графе.

Запускает РЕАЛЬНЫЙ dispatch_typical_tool (тот же путь, что loop.py:1775)
против data/graph-index/ut115.db (channel `_bench`, Phase-2 fix) и сверяет,
что trace_typical_calls отдаёт скорректированные cross-module цепочки,
а не 28%-внутримодульный обрубок.

Запуск из backend/:  python scripts/graph_tool_proof.py
Вывод UTF-8 → ../data/graph-index/_toolproof.txt
"""

from __future__ import annotations

import asyncio
import io
import os
import sys

import aiosqlite

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.knowledge.typical.tool import dispatch_typical_tool  # noqa: E402

DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "graph-index", "ut115.db")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "graph-index", "_toolproof.txt")
CH = "_bench"

REAL = "Document.РеализацияТоваровУслуг.ObjectModule.ОбработкаПроведения"
SAT = "Document.АктИнвентаризацииСАТУРН.ObjectModule.ОбработкаПроведения"
COMMON = "CommonModule.ПроведениеДокументов.CommonModuleBody.ОбработкаПроведенияДокумента"

# Эталон из _validate.txt (ручная сверка с исходником .bsl), 7/7:
EXPECTED_REAL = {
    "CommonModule.ДоставкаТоваров.CommonModuleBody.ОтразитьСостояниеДоставки",
    "CommonModule.ПроведениеДокументов.CommonModuleBody.ОбработкаПроведенияДокумента",
    "CommonModule.РеализацияТоваровУслугЛокализация.CommonModuleBody.ОбработкаПроведения",
    "CommonModule.УчетНДСУП.CommonModuleBody.АктуализироватьСчетаФактурыВыданныеПриПроведении",
    "Document.РеализацияТоваровУслуг.ManagerModule.ПараметрыРегистрацииСчетовФактурВыданных",
    "Document.РеализацияТоваровУслуг.ObjectModule.ИнициализироватьПараметрыЗаполненияВидовЗапасовДляПроведения",
    "Document.РеализацияТоваровУслуг.ObjectModule.ПропуститьПроверкуЗапретаИзмененияРегистров",
}


async def trace(db, qname, direction, depth=1):
    ok, res, err = await dispatch_typical_tool(
        db, "trace_typical_calls",
        {"channel_id": CH, "qualified_name": qname, "direction": direction, "depth": depth},
    )
    return ok, res, err


async def main(buf: io.StringIO):
    def w(s=""):
        buf.write(s + "\n")

    db = await aiosqlite.connect(DB)
    db.row_factory = aiosqlite.Row
    try:
        # ── ТЕСТ 1: out depth=1 — прямые вызовы РеализацияТоваровУслуг ──
        w("=" * 72)
        w(f"ТЕСТ 1  trace_typical_calls(out, d=1)  {REAL}")
        ok, res, err = await trace(db, REAL, "out", 1)
        if not ok:
            w(f"  ОШИБКА: {err}")
        else:
            got = {h["qualified_name"] for h in res["hits"] if h["depth"] == 1}
            w(f"  hits depth=1: {len(got)}  (всего hits {res['total']})")
            cross = {q for q in got if not q.startswith("Document.РеализацияТоваровУслуг.ObjectModule.")}
            w(f"  из них cross-module/manager: {len(cross)}")
            missing = EXPECTED_REAL - got
            extra = got - EXPECTED_REAL
            w(f"  покрытие эталона 7/7: {len(EXPECTED_REAL & got)}/7")
            if missing:
                w("  ПРОПУЩЕНО:")
                for m in sorted(missing):
                    w(f"     - {m}")
            if extra:
                w("  ЛИШНЕЕ (depth=1, сверх эталона):")
                for e in sorted(extra):
                    w(f"     + {e}")
            verdict = "PASS" if not missing else "FAIL"
            w(f"  ВЕРДИКТ ТЕСТ 1: {verdict}")

        # ── ТЕСТ 2: in depth=1 — impact: кто зовёт общий метод проведения ──
        w("")
        w("=" * 72)
        w(f"ТЕСТ 2  trace_typical_calls(in, d=1)  {COMMON}")
        w("  (impact-анализ: до фикса было бы 0 входящих cross-module)")
        ok, res, err = await trace(db, COMMON, "in", 1)
        if not ok:
            w(f"  ОШИБКА: {err}")
        else:
            callers = [h["qualified_name"] for h in res["hits"] if h["depth"] == 1]
            doc_callers = [c for c in callers if c.startswith("Document.")]
            w(f"  входящих depth=1: {len(callers)}  (показ лимитирован {res['total']})")
            w(f"  из них вызывающих документов: {len(doc_callers)}")
            for c in sorted(callers)[:12]:
                w(f"     <- {c}")
            verdict = "PASS" if len(callers) >= 2 else "FAIL (cross-module не резолвится!)"
            w(f"  ВЕРДИКТ ТЕСТ 2: {verdict}")

        # ── ТЕСТ 3: САТУРН — менеджеры регистров (Phase-2) ──
        w("")
        w("=" * 72)
        w(f"ТЕСТ 3  trace_typical_calls(out, d=1)  {SAT}")
        w("  (проверка резолва вызовов менеджеров регистров)")
        ok, res, err = await trace(db, SAT, "out", 1)
        if not ok:
            w(f"  ОШИБКА: {err}")
        else:
            got = {h["qualified_name"] for h in res["hits"] if h["depth"] == 1}
            mgr = {q for q in got if ".ManagerModule." in q}
            w(f"  hits depth=1: {len(got)}")
            w(f"  из них вызовов менеджеров (.ManagerModule.): {len(mgr)}")
            for q in sorted(got):
                tag = "  [MGR]" if ".ManagerModule." in q else ""
                w(f"     -> {q}{tag}")
            verdict = "PASS" if mgr else "FAIL (менеджеры регистров не резолвятся)"
            w(f"  ВЕРДИКТ ТЕСТ 3: {verdict}")

        # ── ТЕСТ 4: depth=2 — транзитивная цепочка ──
        w("")
        w("=" * 72)
        w(f"ТЕСТ 4  trace_typical_calls(out, d=2)  {REAL}")
        w("  (глубина 2 — цепочка проведение → общий метод → его вызовы)")
        ok, res, err = await trace(db, REAL, "out", 2)
        if not ok:
            w(f"  ОШИБКА: {err}")
        else:
            d1 = sum(1 for h in res["hits"] if h["depth"] == 1)
            d2 = sum(1 for h in res["hits"] if h["depth"] == 2)
            w(f"  hits: depth1={d1}  depth2={d2}  total={res['total']}")
            verdict = "PASS" if d2 >= 1 else "FAIL (нет транзитивных рёбер)"
            w(f"  ВЕРДИКТ ТЕСТ 4: {verdict}")
    finally:
        await db.close()


if __name__ == "__main__":
    buf = io.StringIO()
    asyncio.run(main(buf))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print(f"written -> {OUT}")
