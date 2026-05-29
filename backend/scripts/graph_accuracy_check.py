"""Валидация ТОЧНОСТИ графа УТ: что граф считает вызовами метода vs реальный .bsl.

Не прод. Выгружает в UTF-8 отчёт: кандидатов-методы + для выбранных — список
CALLS-целей из графа и source_path, чтобы вручную сверить с исходником выгрузки.

Запуск:  cd backend && .venv/Scripts/python.exe -m scripts.graph_accuracy_check
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB = "../data/graph-index/ut115.db"
OUT = "../data/graph-index/_accuracy.txt"

lines: list[str] = []


def p(s: object = "") -> None:
    lines.append(str(s))


def dump_calls(c: sqlite3.Connection, mid: int, qname: str, src: str) -> None:
    out = c.execute(
        "SELECT t.node_kind, t.qualified_name FROM graph_edges e "
        "JOIN graph_nodes t ON t.id = e.dst_id "
        "WHERE e.src_id = ? AND e.edge_kind = 'CALLS' ORDER BY t.qualified_name",
        (mid,),
    ).fetchall()
    p(f"\n{'='*70}\nМЕТОД id={mid}: {qname}")
    p(f"src: {src}")
    p(f"CALLS из графа ({len(out)}):")
    for kind, q in out:
        p(f"   → {q}")


def main() -> None:
    c = sqlite3.connect(DB)

    p("### Кандидаты: ОбработкаПроведения (top по out-CALLS) ###")
    for r in c.execute(
        "SELECT n.id, n.qualified_name, n.source_path, "
        "(SELECT COUNT(*) FROM graph_edges e WHERE e.src_id=n.id AND e.edge_kind='CALLS') oc "
        "FROM graph_nodes n WHERE n.node_kind='Method' "
        "AND n.qualified_name LIKE '%ОбработкаПроведения%' ORDER BY oc DESC LIMIT 12"
    ):
        p(f"  id={r[0]:>7} out={r[3]:>3}  {r[1]}")

    # Тестовый метод 1: проведение Реализации товаров услуг
    row = c.execute(
        "SELECT n.id, n.qualified_name, n.source_path FROM graph_nodes n "
        "WHERE n.node_kind='Method' AND n.qualified_name LIKE '%РеализацияТоваровУслуг%' "
        "AND n.qualified_name LIKE '%ОбработкаПроведения%' LIMIT 1"
    ).fetchone()
    if row:
        dump_calls(c, row[0], row[1], row[2])
    else:
        p("\n[РеализацияТоваровУслуг.ОбработкаПроведения не найдена — беру top кандидата]")
        top = c.execute(
            "SELECT n.id, n.qualified_name, n.source_path, "
            "(SELECT COUNT(*) FROM graph_edges e WHERE e.src_id=n.id AND e.edge_kind='CALLS') oc "
            "FROM graph_nodes n WHERE n.node_kind='Method' "
            "AND n.qualified_name LIKE '%ОбработкаПроведения%' ORDER BY oc DESC LIMIT 1"
        ).fetchone()
        if top:
            dump_calls(c, top[0], top[1], top[2])

    # Тестовый метод 2: ходовой метод ОбщегоНазначения (БСП) по in-CALLS
    p(f"\n{'='*70}\n### Кандидаты: CommonModule.ОбщегоНазначения* (top по in-CALLS) ###")
    for r in c.execute(
        "SELECT n.id, n.qualified_name, "
        "(SELECT COUNT(*) FROM graph_edges e WHERE e.dst_id=n.id AND e.edge_kind='CALLS') ic "
        "FROM graph_nodes n WHERE n.node_kind='Method' "
        "AND n.qualified_name LIKE 'CommonModule.ОбщегоНазначения%' ORDER BY ic DESC LIMIT 8"
    ):
        p(f"  id={r[0]:>7} in={r[2]:>4}  {r[1]}")

    Path(OUT).write_text("\n".join(lines), encoding="utf-8")
    print(f"OK -> {OUT}  ({len(lines)} строк)")


if __name__ == "__main__":
    main()
