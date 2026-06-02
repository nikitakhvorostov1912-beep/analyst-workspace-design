"""Демо grounding по свежему графу pilot.db: документ УТ → ответы по факту.

    python -m scripts.demo_grounding > demo.txt
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.knowledge.typical.card_context import build_card_context  # noqa: E402

DB = "C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db"
_ap = argparse.ArgumentParser()
_ap.add_argument("--channel", default="_ut115_17_226")
_ap.add_argument("--qname", default="Document.РеализацияТоваровУслуг")
_ap.add_argument("--out", default="C:/CLOUDE_PR/projects/analyst-workspace-design/demo_grounding_out.txt")
_args, _ = _ap.parse_known_args()
CH = _args.channel
QN = _args.qname

OUT = []
def p(s=""): OUT.append(s)


async def rls(db, qn):
    """RESTRICTS-рёбра, касающиеся объекта (роль -> объект, по правам)."""
    rows = await (await db.execute(
        """SELECT s.qualified_name, e.attributes FROM graph_edges e
           JOIN graph_nodes s ON e.src_id=s.id
           JOIN graph_nodes d ON e.dst_id=d.id
           WHERE d.channel_id=? AND e.edge_kind='RESTRICTS'
             AND d.qualified_name=?""", (CH, qn))).fetchall()
    return rows


async def main():
    db = await aiosqlite.connect(DB)
    # семантика — карточка
    row = await (await db.execute(
        "SELECT card_payload FROM typical_object_cards "
        "WHERE channel_id=? AND object_qualified_name=?", (CH, QN))).fetchone()
    card = json.loads(row[0]) if row else {}

    ctx = await build_card_context(db, channel_id=CH, object_qualified_name=QN)
    d = ctx.to_dict() if ctx else {}

    _names = {"_ut115_17_226": "УТ 11.5", "_erp25_21_118": "ЕРП 2.5",
              "_ka2_25_92": "КА 2.5", "_bp30_138_24": "БП 3.0"}
    p("=" * 72)
    p(f"ДЕМО GROUNDING — {QN}  (канал {_names.get(CH, CH)}, из pilot.db)")
    p("=" * 72)

    p("\n■ СЛОЙ «КАРТОЧКА» (смысл — что это):")
    p(f"  summary: {card.get('summary','—')}")
    p(f"  purpose: {(card.get('purpose','—') or '')[:300]}")

    p("\n" + "─" * 72)
    p("Вопрос 1: «Что меняется в учёте при проведении этого документа?»")
    p("Ответ из графа (WRITES_TO — движения по регистрам):")
    writes = d.get("writes_to") or []
    p(f"  → {len(writes)} регистров:")
    for w in writes[:25]:
        p(f"     • {w}")
    if len(writes) > 25:
        p(f"     … ещё {len(writes)-25}")

    p("\n" + "─" * 72)
    p("Вопрос 2: «Откуда документ читает данные?» (READS_FROM)")
    reads = d.get("reads_from") or []
    seen = []
    for r in reads:
        q = r.get("register") if isinstance(r, dict) else r
        if q and q not in seen:
            seen.append(q)
    p(f"  → {len(seen)} источников:")
    for q in seen[:15]:
        p(f"     • {q}")

    p("\n" + "─" * 72)
    p("Вопрос 3: «Кто завязан на этот документ / где используется?» (impact)")
    refs = d.get("referenced_by") or []
    bases = []
    for ref in refs:
        b = ref.split(".Реквизит.")[0].split(".ТабличнаяЧасть.")[0]
        if b not in bases:
            bases.append(b)
    p(f"  → ссылаются {len(bases)} объектов (топ-15):")
    for b in bases[:15]:
        p(f"     • {b}")

    p("\n" + "─" * 72)
    p("Вопрос 4: «Какие роли ограничивают доступ к документу?» (RLS / RESTRICTS)")
    rrows = await rls(db, QN)
    p(f"  → {len(rrows)} ролей с ограничениями (топ-10):")
    for qn_role, attrs in rrows[:10]:
        rights = ""
        try:
            a = json.loads(attrs) if attrs else {}
            rl = a.get("rights") or a.get("conditions") or a
            rights = ", ".join(x.get("right", "") for x in rl) if isinstance(rl, list) else ""
        except Exception:
            pass
        p(f"     • {qn_role}{('  [' + rights + ']') if rights else ''}")

    p("\n" + "─" * 72)
    p("Вопрос 5: «Какие процедуры запускаются от этого документа?» (CALLS — связи по коду)")
    crows = await (await db.execute(
        """SELECT d.qualified_name, COUNT(*) cnt FROM graph_edges e
           JOIN graph_nodes s ON e.src_id=s.id
           JOIN graph_nodes d ON e.dst_id=d.id
           WHERE s.channel_id=? AND e.edge_kind='CALLS'
             AND s.qualified_name LIKE ?
           GROUP BY d.qualified_name ORDER BY cnt DESC LIMIT 15""",
        (CH, QN + ".%"))).fetchall()
    p(f"  → вызывает {len(crows)} процедур (топ-15 по частоте):")
    for qn_t, cnt in crows:
        short = qn_t.replace("CommonModule.", "ОМ.").replace(".Module.", ".")
        p(f"     • ({cnt}×) {short}")

    p("\n" + "=" * 72)
    p("ИТОГ: на все 5 вопросов ответ собран ПО ФАКТУ из графа+карточки —")
    p("без выдумок. Это и есть grounding, который получит LLM в чате.")
    p("=" * 72)

    await db.close()
    Path(_args.out).write_text("\n".join(OUT), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
