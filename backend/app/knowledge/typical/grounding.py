"""Headless grounding-turn над типовым графом (текст, без SSE).

Один ход «вопрос аналитика → LLM сама дёргает typical-инструменты против
графа типовой → ответ с пруфами». Используется:
  - grounding_harness.py (ручное демо с реальным MiMo);
  - тестами (FakeLLMClient + синтетический граф) — детерминированно.

НЕ дублирует полный SSE-оркестратор loop.py: это сфокусированный
text-only примитив для grounding'а по ТИПОВЫМ конфигурациям. `client` —
duck-typed: любой объект с `stream_chat_completion(messages, api_key,
tools, temperature)` (async-итератор `choices[0]`-дельт OpenAI).
"""
from __future__ import annotations

import json
from typing import Any, Protocol

import aiosqlite

from app.knowledge.typical.tool import TYPICAL_TOOL_SCHEMAS, dispatch_typical_tool

_DEFAULT_TOOL_RESULT_CAP = 8000
# #38: 6 раундов не хватало на цепочку explain_typical_object → trace_typical_calls
# (резолв qname метода) — LLM упиралась в лимит. 10 даёт запас.
_DEFAULT_MAX_ROUNDS = 10


class _StreamingLLM(Protocol):
    def stream_chat_completion(
        self, messages: list[dict], api_key: str,
        tools: list[dict] | None = ..., temperature: float = ...,
    ) -> Any: ...


async def collect_stream(
    client: _StreamingLLM,
    messages: list[dict],
    api_key: str,
    tools: list[dict] | None,
    temperature: float,
) -> tuple[str, list[dict]]:
    """Собирает (content, tool_calls) из стрима OpenAI-дельт.

    tool_calls приходят фрагментами по index — реассемблируем id/name/args.
    Возвращает список `{"id","name","args"}` в порядке index.
    """
    content = ""
    tcs: dict[int, dict] = {}
    async for choice in client.stream_chat_completion(
        messages, api_key, tools=tools, temperature=temperature,
    ):
        delta = (choice or {}).get("delta") or {}
        if delta.get("content"):
            content += delta["content"]
        for tc in delta.get("tool_calls") or []:
            idx = tc.get("index", 0)
            slot = tcs.setdefault(idx, {"id": "", "name": "", "args": ""})
            if tc.get("id"):
                slot["id"] = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                slot["name"] = fn["name"]
            if fn.get("arguments"):
                slot["args"] += fn["arguments"]
    return content, [tcs[i] for i in sorted(tcs)]


async def run_grounding_turn(
    client: _StreamingLLM,
    db: aiosqlite.Connection,
    *,
    api_key: str,
    question: str,
    system: str,
    tools: list[dict] | None = None,
    max_rounds: int = _DEFAULT_MAX_ROUNDS,
    temperature: float = 0.2,
    tool_result_cap: int = _DEFAULT_TOOL_RESULT_CAP,
) -> dict[str, Any]:
    """Прогоняет один grounding-ход: NL-вопрос → tool-calls → ответ.

    Returns dict:
      - answer: финальный текст LLM (str) или None если исчерпан лимит раундов;
      - tool_trace: [{name, args, ok, result}] в порядке вызова (пруфы);
      - rounds: число итераций;
      - exhausted: True если уперлись в max_rounds без финального ответа.
    """
    if tools is None:
        tools = TYPICAL_TOOL_SCHEMAS
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
    trace: list[dict] = []
    for rnd in range(1, max_rounds + 1):
        content, calls = await collect_stream(client, messages, api_key, tools, temperature)
        if not calls:
            return {"answer": content.strip(), "tool_trace": trace,
                    "rounds": rnd, "exhausted": False}
        messages.append({
            "role": "assistant",
            "content": content or None,
            "tool_calls": [
                {"id": c["id"] or f"call_{i}", "type": "function",
                 "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
                for i, c in enumerate(calls)
            ],
        })
        for i, c in enumerate(calls):
            cid = c["id"] or f"call_{i}"
            try:
                args = json.loads(c["args"] or "{}")
            except json.JSONDecodeError:
                args = {}
            ok, result, err = await dispatch_typical_tool(db, c["name"], args)
            payload = result if ok else {"error": err}
            trace.append({"name": c["name"], "args": args, "ok": ok, "result": payload})
            messages.append({
                "role": "tool", "tool_call_id": cid,
                "content": json.dumps(payload, ensure_ascii=False)[:tool_result_cap],
            })
    return {"answer": None, "tool_trace": trace, "rounds": max_rounds, "exhausted": True}
