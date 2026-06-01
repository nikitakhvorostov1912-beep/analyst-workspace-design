"""Live-проверка: после промпт-фикса LLM предпочитает живой Напарник (buddy)
для ИТС-вопросов, и имя с точкой `buddy.search_its` не ломает MiMo API.

Даёт MiMo набор инструментов (buddy.search_its [точка!] + search_its [наш
статический] + execute_query [не-ИТС шум]) и новый промпт-гайд. На ИТС-вопрос
ожидаем, что MiMo вызовет ПЕРВЫМ `buddy.search_its`. Результаты инструментов
стаблены (реальный ответ Напарника проверен отдельно) — здесь проверяем
МАРШРУТИЗАЦИЮ + приём dot-имени, не контент.

Запуск из backend/:  DEFAULT_LLM_API_KEY=... python scripts/buddy_routing_probe.py
Вывод UTF-8 → ../data/graph-index/_buddy_probe.txt
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.clients.llm import LLMClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.knowledge.typical.grounding import collect_stream  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "graph-index", "_buddy_probe.txt")
ENDPOINT = "https://api.xiaomimimo.com/v1"
MODEL = "mimo-v2.5-pro"

SYSTEM = (
    "Ты — ассистент бизнес-аналитика 1С. Отвечай на русском, опираясь на "
    "инструменты. ИТС/методики/инструкции 1С меняются ПОСТОЯННО, поэтому для "
    "вопросов о методологии/стандартах/инструкциях ИТС используй ПЕРВЫМ живой "
    "источник `buddy.search_its` (1С:Напарник). `search_its` (наш статический "
    "индекс) — только FALLBACK, если buddy недоступен. Для данных конкретной "
    "базы — execute_query."
)

# Инструменты как их видит LLM (buddy.* с ТОЧКОЙ — как реально префиксует orchestrator)
TOOLS = [
    {"type": "function", "function": {
        "name": "buddy.search_its",
        "description": "1С:Напарник — ЖИВОЙ поиск по ИТС (всегда актуально).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "search_its",
        "description": "Наш статический индекс ИТС (снапшот v8std, может устаревать). FALLBACK.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "execute_query",
        "description": "Запрос к конкретной базе 1С клиента (НЕ для методологии ИТС).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]

QUESTIONS = [
    "По стандартам ИТС — как правильно настроить ограничение доступа на уровне записей (RLS)?",
    "Какой методический стандарт 1С описывает работу с длительными операциями?",
]

# Стаб результата инструмента (контент не важен для проверки маршрутизации)
STUBS = {
    "buddy.search_its": {"source": "1С:Напарник (живой ИТС)", "found": 3,
                         "top": "Практическое пособие разработчика → RLS; БСП 3.2.1 → варианты RLS"},
    "search_its": {"source": "наш статический индекс", "found": 2, "top": "std-RLS-фрагмент"},
    "execute_query": {"rows": []},
}


async def probe(client, key, question, w):
    w("=" * 72)
    w(f"ВОПРОС: {question}")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    first_tool = None
    for _ in range(4):
        content, calls = await collect_stream(client, messages, key, TOOLS, 0.2)
        if not calls:
            w(f"  ОТВЕТ: {content.strip()[:300]}")
            break
        messages.append({"role": "assistant", "content": content or None, "tool_calls": [
            {"id": c["id"] or f"c{i}", "type": "function",
             "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
            for i, c in enumerate(calls)]})
        for i, c in enumerate(calls):
            if first_tool is None:
                first_tool = c["name"]
            w(f"  [LLM вызвала: {c['name']}({(c['args'] or '')[:80]})]")
            payload = STUBS.get(c["name"], {"ok": True})
            messages.append({"role": "tool", "tool_call_id": c["id"] or f"c{i}",
                             "content": json.dumps(payload, ensure_ascii=False)})
    verdict = "PASS (buddy первым)" if first_tool == "buddy.search_its" else f"FAIL (первым: {first_tool})"
    w(f"  ВЕРДИКТ: {verdict}")
    w("")
    return first_tool == "buddy.search_its"


async def main(buf):
    def w(s=""):
        buf.write(s + "\n")
    key = get_settings().resolve_default_api_key(ENDPOINT) or get_settings().default_llm_api_key
    if not key:
        w("ОШИБКА: нет ключа (DEFAULT_LLM_API_KEY)")
        return
    w(f"endpoint={ENDPOINT} model={MODEL}")
    w("Проверка: (1) dot-имя buddy.search_its принято API, (2) MiMo выбирает buddy первым\n")
    client = LLMClient(ENDPOINT, MODEL, timeout=180.0)
    passed = 0
    try:
        for q in QUESTIONS:
            try:
                if await probe(client, key, q, w):
                    passed += 1
            except Exception as exc:  # noqa: BLE001
                w(f"  ОШИБКА (возможно dot-имя отвергнуто API): {type(exc).__name__}: {exc}\n")
    finally:
        await client.aclose()
    w(f"ИТОГО: buddy выбран первым в {passed}/{len(QUESTIONS)} ИТС-вопросах")
    w("(если была ОШИБКА выше — dot-имя ломает MiMo → нужна санитизация в orchestrator)")


if __name__ == "__main__":
    buf = io.StringIO()
    asyncio.run(main(buf))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print(f"written -> {OUT}")
