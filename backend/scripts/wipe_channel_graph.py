"""Полный wipe графа одного канала в pilot.db перед пересборкой.

build_typical_graph НЕ чистит канал (insert дедуплицирует по ON CONFLICT),
поэтому stale-узлы и collapsed RLS-рёбра блокируют RLS-v2. Удаляем рёбра
(по src/dst в узлах канала) и узлы канала.

    python -m scripts.wipe_channel_graph --channel _ut115_17_226 --db data/pilot.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--channel", required=True)
    p.add_argument("--db", default="data/pilot.db")
    a = p.parse_args(argv if argv is not None else sys.argv[1:])

    db = sqlite3.connect(a.db)
    c = db.cursor()
    n0 = c.execute("SELECT COUNT(*) FROM graph_nodes WHERE channel_id=?", (a.channel,)).fetchone()[0]
    e0 = c.execute(
        "SELECT COUNT(*) FROM graph_edges WHERE src_id IN "
        "(SELECT id FROM graph_nodes WHERE channel_id=?) OR dst_id IN "
        "(SELECT id FROM graph_nodes WHERE channel_id=?)",
        (a.channel, a.channel),
    ).fetchone()[0]
    print(f"before: nodes={n0} edges(touching)={e0}")

    c.execute(
        "DELETE FROM graph_edges WHERE src_id IN "
        "(SELECT id FROM graph_nodes WHERE channel_id=?) OR dst_id IN "
        "(SELECT id FROM graph_nodes WHERE channel_id=?)",
        (a.channel, a.channel),
    )
    c.execute("DELETE FROM graph_nodes WHERE channel_id=?", (a.channel,))
    db.commit()

    n1 = c.execute("SELECT COUNT(*) FROM graph_nodes WHERE channel_id=?", (a.channel,)).fetchone()[0]
    print(f"after: nodes={n1}  (deleted nodes={n0-n1}, edges={e0})")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
