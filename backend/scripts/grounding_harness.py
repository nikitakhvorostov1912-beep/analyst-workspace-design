"""Grounding-harness: ручное демо ценности графа через реальную MiMo.

Тонкая обёртка над app.knowledge.typical.grounding.run_grounding_turn:
прогоняет вопросы аналитика через MiMo с реальными TYPICAL_TOOL_SCHEMAS,
LLM сама дёргает trace_*/explain_* против ИСПРАВЛЕННОГО графа (ut115.db,
channel _bench). Прод-БД (app.db/pilot.db) не трогаются.

Детерминированные тесты grounding-цикла (без сети/ключа) — в
tests/test_typical_grounding.py. Этот скрипт — для ручной проверки с ключом.

Ключ читается из backend/.env (DEFAULT_LLM_API_KEY) через get_settings() —
скрипт ключ нигде не печатает и не сохраняет.

Запуск из backend/:  python scripts/grounding_harness.py
Вывод UTF-8 → ../data/graph-index/_grounding.txt
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys

import aiosqlite

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.clients.llm import LLMClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.knowledge.typical.grounding import run_grounding_turn  # noqa: E402
from app.knowledge.typical.tool import TYPICAL_TOOL_SCHEMAS  # noqa: E402

DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "graph-index", "ut115.db")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "graph-index", "_grounding.txt")
ENDPOINT = "https://api.xiaomimimo.com/v1"
MODEL = "mimo-v2.5-pro"

SYSTEM = (
    "Ты — ассистент бизнес-аналитика 1С. У тебя есть инструменты по ТИПОВЫМ "
    "конфигурациям 1С (граф структуры и поведения). Отвечай на русском, кратко "
    "и по делу, опираясь ТОЛЬКО на данные инструментов (не выдумывай). "
    "ВАЖНО: перед trace_*/explain_* сначала вызови list_typical_configurations, "
    "чтобы узнать channel_id загруженной типовой (это УТ). Затем используй его. "
    "В финальном ответе приводи конкретику из инструментов как пруфы."
)

QUESTIONS = [
    ("ДВИЖЕНИЯ", "В типовой УТ — какие документы формируют движения по регистру "
     "накопления ТоварыНаСкладах? Перечисли хотя бы 10."),
    ("ЦЕПОЧКА/IMPACT", "В УТ: что вызывается при проведении документа "
     "РеализацияТоваровУслуг (метод ОбработкаПроведения объектного модуля)? "
     "И насколько широко используется общий метод проведения "
     "ОбработкаПроведенияДокумента — сколько документов от него зависят?"),
    ("RLS", "В УТ — какие роли и какими условиями ограничивают доступ к "
     "справочнику ВнешниеПользователи (RLS)?"),
]


async def main(buf: io.StringIO):
    def w(s=""):
        buf.write(s + "\n")

    settings = get_settings()
    key = settings.resolve_default_api_key(ENDPOINT) or settings.default_llm_api_key
    if not key:
        w("ОШИБКА: ключ не найден. Добавь DEFAULT_LLM_API_KEY=... в backend/.env")
        return
    w(f"endpoint={ENDPOINT}  model={MODEL}  db=ut115.db (channel _bench)")
    w(f"инструментов в схеме: {len(TYPICAL_TOOL_SCHEMAS)}\n")

    db = await aiosqlite.connect(DB)
    db.row_factory = aiosqlite.Row
    client = LLMClient(ENDPOINT, MODEL, timeout=180.0)
    try:
        for label, q in QUESTIONS:
            w("=" * 72)
            w(f"ВОПРОС [{label}]: {q}")
            w("-" * 72)
            try:
                res = await run_grounding_turn(
                    client, db, api_key=key, question=q, system=SYSTEM,
                )
            except Exception as exc:  # noqa: BLE001
                w(f"  ОШИБКА: {type(exc).__name__}: {exc}\n")
                continue
            for t in res["tool_trace"]:
                short = json.dumps(t["result"], ensure_ascii=False)[:200]
                w(f"  [tool {t['name']}({json.dumps(t['args'], ensure_ascii=False)})] -> {short}…")
            w("ОТВЕТ LLM:")
            w(res["answer"] or "(не дала финальный ответ — лимит раундов)")
            w("")
    finally:
        await client.aclose()
        await db.close()


if __name__ == "__main__":
    buf = io.StringIO()
    asyncio.run(main(buf))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print(f"written -> {OUT}")
