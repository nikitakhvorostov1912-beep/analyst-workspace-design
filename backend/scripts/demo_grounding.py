"""Демо grounding по свежему графу pilot.db: документ УТ → ответы по факту.

    python -m scripts.demo_grounding > demo.txt
"""
from __future__ import annotations

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
CH = "_ut115_17_226"
QN = "Document.РеализацияТоваровУслуг"

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

    p("=" * 72)
    p(f"ДЕМО GROUNDING — {QN}  (канал УТ 11.5, из pilot.db)")
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

    p("\n" + "=" * 72)
    p("ИТОГ: на все 4 вопроса ответ собран ПО ФАКТУ из графа+карточки —")
    p("без выдумок. Это и есть grounding, который получит LLM в чате.")
    p("=" * 72)

    await db.close()
    Path("C:/CLOUDE_PR/projects/analyst-workspace-design/demo_grounding_out.txt").write_text(
        "\n".join(OUT), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
