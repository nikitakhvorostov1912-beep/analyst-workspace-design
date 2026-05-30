"""Расширенная валидация точности графа: для N методов выгружает graph CALLS
+ реальный исходник метода (по line_start/line_end), чтобы вручную сверить
покрытие. Вывод — UTF-8 отчёт.

Запуск:  cd backend && .venv/Scripts/python.exe -m scripts.graph_validate_methods
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = "../data/graph-index/ut115.db"
SNAP = Path("../data/typical-snapshots/ut115-demotrd")
OUT = "../data/graph-index/_validate.txt"
MAX_SRC_LINES = 80

lines: list[str] = []


def p(s: object = "") -> None:
    lines.append(str(s))


def dump(mid: int, qn: str, src: str, attrs: str | None) -> None:
    a = json.loads(attrs or "{}")
    ls, le = a.get("line_start"), a.get("line_end")
    calls = c.execute(
        "SELECT t.qualified_name FROM graph_edges e JOIN graph_nodes t ON t.id=e.dst_id "
        "WHERE e.src_id=? AND e.edge_kind='CALLS' ORDER BY t.qualified_name",
        (mid,),
    ).fetchall()
    p("=" * 72)
    p(qn)
    p(f"src={src}  lines={ls}..{le}")
    p(f"--- ГРАФ CALLS ({len(calls)}): ---")
    for (q,) in calls:
        p(f"   -> {q.split('.')[-1]:42s} [{q}]")
    f = SNAP / src
    if f.exists() and ls:
        slice_ = f.read_text(encoding="utf-8", errors="replace").splitlines()[ls - 1 : le]
        if len(slice_) > MAX_SRC_LINES:
            slice_ = slice_[:MAX_SRC_LINES] + ["    ... [обрезано] ..."]
        p(f"--- ИСХОДНИК {ls}..{le}: ---")
        p("\n".join(slice_))
    p("")


c = sqlite3.connect(DB)

# Фиксированные интересные методы
for qn in (
    "Document.РеализацияТоваровУслуг.ObjectModule.ОбработкаПроведения",
    "CommonModule.ПроведениеДокументов.CommonModuleBody.ОбработкаПроведенияДокумента",
):
    r = c.execute(
        "SELECT id, qualified_name, source_path, attributes FROM graph_nodes "
        "WHERE qualified_name=?",
        (qn,),
    ).fetchone()
    if r:
        dump(*r)

# Ещё 2 документа ОбработкаПроведения по out-degree (теперь cross работает)
for r in c.execute(
    "SELECT n.id, n.qualified_name, n.source_path, n.attributes, "
    "(SELECT COUNT(*) FROM graph_edges e WHERE e.src_id=n.id AND e.edge_kind='CALLS') oc "
    "FROM graph_nodes n WHERE n.node_kind='Method' "
    "AND n.qualified_name LIKE 'Document.%.ObjectModule.ОбработкаПроведения' "
    "AND n.qualified_name != 'Document.РеализацияТоваровУслуг.ObjectModule.ОбработкаПроведения' "
    "ORDER BY oc DESC LIMIT 2"
):
    dump(r[0], r[1], r[2], r[3])

Path(OUT).write_text("\n".join(lines), encoding="utf-8")
print(f"OK -> {OUT} ({len(lines)} строк)")
