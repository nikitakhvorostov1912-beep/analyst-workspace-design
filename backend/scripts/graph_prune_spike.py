"""SPIKE (одноразовый замер) — насколько ужимается граф-БД для desktop-пака.

Не прод. Меряет 3 варианта на готовом ut115.db, ничего не теряя из call/impact/RLS:
  A — graph-only, всё как есть (без пустых продуктовых таблиц) + {}→NULL + VACUUM
  B — A + выкинуть CONTAINS-рёбра (иерархия модуль→метод; call-graph их не traversʼит)
  C — B + выкинуть node.attributes (uuid/comment/precision — для call-graph не нужны)

Запуск:  cd backend && .venv/Scripts/python.exe -m scripts.graph_prune_spike
"""
from __future__ import annotations

import os
import sqlite3

SRC = "../data/graph-index/ut115.db"
OUT = "../data/graph-index/_spike"

GRAPH_INDEXES = (
    "CREATE INDEX ix_n_qname ON graph_nodes(channel_id, qualified_name)",
    "CREATE INDEX ix_n_kind ON graph_nodes(channel_id, node_kind)",
    "CREATE INDEX ix_e_src ON graph_edges(src_id, edge_kind)",
    "CREATE INDEX ix_e_dst ON graph_edges(dst_id, edge_kind)",
)


# Ключи node.attributes, которые реально читает grounding (typical/tool.py):
# kind/name/module_kind/comment. Остальное (uuid, fill_check, indexed, length,
# precision) — для call/impact/RLS не нужно → слим без потери качества.
_SLIM_ATTR = (
    "json_object("
    "'kind', json_extract(attributes,'$.kind'),"
    "'name', json_extract(attributes,'$.name'),"
    "'module_kind', json_extract(attributes,'$.module_kind'),"
    "'comment', json_extract(attributes,'$.comment'))"
)


def build(path: str, *, drop_contains: bool, node_attr: str) -> tuple[float, int, int]:
    if os.path.exists(path):
        os.remove(path)
    d = sqlite3.connect(path)
    d.execute("PRAGMA journal_mode=OFF")
    d.execute(
        "CREATE TABLE graph_nodes(id INTEGER PRIMARY KEY, channel_id TEXT, "
        "node_kind TEXT, qualified_name TEXT, source_path TEXT, attributes TEXT)"
    )
    d.execute(
        "CREATE TABLE graph_edges(id INTEGER PRIMARY KEY, src_id INTEGER, "
        "dst_id INTEGER, edge_kind TEXT, attributes TEXT)"
    )
    d.execute("ATTACH ? AS s", (SRC,))
    d.execute(
        f"INSERT INTO graph_nodes SELECT id, channel_id, node_kind, "
        f"qualified_name, source_path, {node_attr} FROM s.graph_nodes"
    )
    where = "WHERE edge_kind != 'CONTAINS'" if drop_contains else ""
    d.execute(
        "INSERT INTO graph_edges SELECT id, src_id, dst_id, edge_kind, "
        "CASE WHEN attributes IN ('{}', '') THEN NULL ELSE attributes END "
        f"FROM s.graph_edges {where}"
    )
    d.commit()
    d.execute("DETACH s")
    for idx in GRAPH_INDEXES:
        d.execute(idx)
    n = d.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
    e = d.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
    d.commit()
    d.execute("VACUUM")
    d.close()
    return os.path.getsize(path) / 1048576, n, e


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    src_mb = os.path.getsize(SRC) / 1048576
    print(f"SOURCE ut115.db: {src_mb:.0f} MB (полная схема + граф)")
    variants = [
        ("A graph-only (lossless)", False, "attributes"),
        ("C  + drop node.attrs", False, "NULL"),
        ("D  slim attrs (qual-safe)", False, _SLIM_ATTR),
    ]
    for label, dc, na in variants:
        mb, n, e = build(f"{OUT}/ut115_{label[0]}.db", drop_contains=dc, node_attr=na)
        print(f"{label:30s} {mb:6.0f} MB   nodes={n}  edges={e}")


if __name__ == "__main__":
    main()
