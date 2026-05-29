"""Точечная проба: какие вызовы граф поймал у Document.РеализацияТоваровУслуг.ОбработкаПроведения
и существуют ли узлы-цели межмодульных вызовов (чтобы понять — парсер не нашёл цель
или не распознал call-выражение). Вывод в UTF-8 файл.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB = "../data/graph-index/ut115.db"
OUT = "../data/graph-index/_probe.txt"
lines: list[str] = []


def p(s: object = "") -> None:
    lines.append(str(s))


# (имя для отчёта, фрагмент qualified_name цели вызова из исходника)
EXPECTED = [
    ("ПроведениеДокументов.ОбработкаПроведенияДокумента", "ПроведениеДокументов%ОбработкаПроведенияДокумента"),
    ("ДоставкаТоваров.ОтразитьСостояниеДоставки", "ДоставкаТоваров%ОтразитьСостояниеДоставки"),
    ("УчетНДСУП.АктуализироватьСчетаФактурыВыданныеПриПроведении", "УчетНДСУП%АктуализироватьСчетаФактурыВыданныеПриПроведении"),
    ("РеализацияТоваровУслугЛокализация.ОбработкаПроведения", "РеализацияТоваровУслугЛокализация%ОбработкаПроведения"),
]


def main() -> None:
    c = sqlite3.connect(DB)
    m = c.execute(
        "SELECT id, qualified_name FROM graph_nodes "
        "WHERE qualified_name = 'Document.РеализацияТоваровУслуг.ObjectModule.ОбработкаПроведения'"
    ).fetchone()
    if not m:
        p("НЕ НАЙДЕН узел Document.РеализацияТоваровУслуг.ObjectModule.ОбработкаПроведения")
        Path(OUT).write_text("\n".join(lines), encoding="utf-8")
        print("done (not found)")
        return
    mid, mq = m
    p(f"МЕТОД id={mid}: {mq}")
    calls = c.execute(
        "SELECT t.qualified_name FROM graph_edges e JOIN graph_nodes t ON t.id=e.dst_id "
        "WHERE e.src_id=? AND e.edge_kind='CALLS' ORDER BY t.qualified_name",
        (mid,),
    ).fetchall()
    p(f"\nCALLS из графа ({len(calls)}):")
    for (q,) in calls:
        p(f"   → {q}")

    p("\nПРОБА межмодульных вызовов из реального исходника:")
    for name, like in EXPECTED:
        # есть ли вообще такой метод-узел в графе
        node = c.execute(
            "SELECT id, qualified_name FROM graph_nodes WHERE node_kind='Method' "
            "AND qualified_name LIKE ? LIMIT 1",
            (f"%{like}",),
        ).fetchone()
        if not node:
            p(f"  [{name}] узел-цель В ГРАФЕ НЕ НАЙДЕН")
            continue
        tid = node[0]
        edge = c.execute(
            "SELECT 1 FROM graph_edges WHERE src_id=? AND dst_id=? AND edge_kind='CALLS'",
            (mid, tid),
        ).fetchone()
        status = "✓ ребро ЕСТЬ" if edge else "✗ ребра НЕТ (вызов потерян)"
        p(f"  [{name}] узел есть (id={tid}) → {status}")

    Path(OUT).write_text("\n".join(lines), encoding="utf-8")
    print(f"OK -> {OUT}")


if __name__ == "__main__":
    main()
