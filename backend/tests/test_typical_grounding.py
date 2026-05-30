"""Детерминированные тесты grounding-цикла (run_grounding_turn).

FakeLLMClient скриптует tool-calls (без сети/ключа), граф — синтетический
in-memory. Проверяется ВСЯ оркестрация: реассембл стрим-дельт, диспетч
реальных typical-инструментов, прокидывание результатов обратно в LLM,
сборка финального ответа. Покрывает 3 киллер-UC + краевые случаи.
"""
from __future__ import annotations

import json

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.graph_storage import EdgeKind, NodeKind, insert_edge, insert_node
from app.knowledge.typical.grounding import collect_stream, run_grounding_turn
from app.knowledge.typical.registry import TypicalConfigKind
from app.knowledge.typical.storage import create_configuration
from app.storage.migrations import apply_migrations

CHANNEL = "_bp30_138_24"
SYSTEM = "тест-система"
REGISTER = "AccumulationRegister.ТоварыНаСкладах"
RTU = "Document.РеализацияТоваровУслуг"
VVOD = "Document.ВводОстатков"
COMMON = "CommonModule.ПроведениеДокументов.CommonModuleBody.ОбработкаПроведенияДокумента"
RTU_METHOD = "Document.РеализацияТоваровУслуг.ObjectModule.ОбработкаПроведения"
CATALOG = "Catalog.ВнешниеПользователи"
ROLE = "Role.БазовыеПраваВнешних"


class FakeLLMClient:
    """Duck-typed двойник LLMClient. `script(messages)->(content, tool_calls)`.

    tool_calls: list[{"id","name","args"}]. split_args=True разбивает
    arguments на 2 дельты (проверка реассемблера).
    """

    def __init__(self, script, *, split_args: bool = False):
        self._script = script
        self.split_args = split_args
        self.turns = 0

    async def stream_chat_completion(self, messages, api_key, tools=None, temperature=0.3):
        self.turns += 1
        content, tool_calls = self._script(messages)
        for i, tc in enumerate(tool_calls):
            if self.split_args:
                args = tc["args"]
                mid = max(1, len(args) // 2)
                yield {"delta": {"tool_calls": [{
                    "index": i, "id": tc["id"],
                    "function": {"name": tc["name"], "arguments": args[:mid]}}]}}
                yield {"delta": {"tool_calls": [{
                    "index": i, "function": {"arguments": args[mid:]}}]}}
            else:
                yield {"delta": {"tool_calls": [{
                    "index": i, "id": tc["id"],
                    "function": {"name": tc["name"], "arguments": tc["args"]}}]}}
        if content:
            yield {"delta": {"content": content}}

    async def aclose(self):
        pass


@pytest_asyncio.fixture
async def db_seeded():
    """Синтетический граф: движения (Doc→Register), CALLS, RLS."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON")
    await apply_migrations(conn)
    await create_configuration(
        conn, TypicalConfigKind.BP_30, "3.0.138.24",
        source_path="data/typical-snapshots/bp30-accounting",
    )

    async def node(qname, kind=NodeKind.METADATA_OBJECT.value, **attrs):
        return await insert_node(conn, channel_id=CHANNEL, node_kind=kind,
                                 qualified_name=qname, attributes=attrs)

    # ── движения: 2 документа пишут в регистр (Phase F стиль) ──
    reg = await node(REGISTER, name="ТоварыНаСкладах", kind=NodeKind.METADATA_OBJECT.value)
    rtu = await node(RTU, name="РеализацияТоваровУслуг")
    vvod = await node(VVOD, name="ВводОстатков")
    for doc in (rtu, vvod):
        await insert_edge(conn, src_id=doc, dst_id=reg,
                          edge_kind=EdgeKind.WRITES_TO.value,
                          attributes={"resolution": "register_records"})

    # ── CALLS: метод проведения РТУ зовёт общий метод ──
    rtu_method = await node(RTU_METHOD, kind=NodeKind.METHOD.value,
                            name="ОбработкаПроведения", module_kind="ObjectModule")
    common = await node(COMMON, kind=NodeKind.METHOD.value,
                        name="ОбработкаПроведенияДокумента", module_kind="CommonModuleBody")
    vvod_method = await node(
        "Document.ВводОстатков.ObjectModule.ОбработкаПроведения",
        kind=NodeKind.METHOD.value, name="ОбработкаПроведения", module_kind="ObjectModule")
    await insert_edge(conn, src_id=rtu_method, dst_id=common,
                      edge_kind=EdgeKind.CALLS.value, attributes={"resolution": "cross_module"})
    # impact: и ВводОстатков зовёт тот же общий метод
    await insert_edge(conn, src_id=vvod_method, dst_id=common,
                      edge_kind=EdgeKind.CALLS.value, attributes={"resolution": "cross_module"})

    # ── RLS: роль ограничивает справочник, per-right условия ──
    cat = await node(CATALOG, name="ВнешниеПользователи")
    role = await insert_node(conn, channel_id=CHANNEL, node_kind=NodeKind.ROLE.value,
                             qualified_name=ROLE)
    await insert_edge(conn, src_id=role, dst_id=cat, edge_kind=EdgeKind.RESTRICTS.value,
                      attributes={"restrictions": [
                          {"right": "Read", "condition": "Условие_Чтение"},
                          {"right": "Update", "condition": "Условие_Изменение"},
                      ]})
    yield conn
    await conn.close()


def _channel_from_list(tool_content: str) -> str:
    return json.loads(tool_content)["configurations"][0]["channel_id"]


def _last_tool_results(messages) -> list[dict]:
    return [m for m in messages if m.get("role") == "tool"]


# ─── Киллер-UC 1: движения ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_grounding_movements_full_roundtrip(db_seeded):
    """list_configs → читает channel → trace_movements → ответ с документами."""
    def script(messages):
        tools = _last_tool_results(messages)
        if not tools:
            return "", [{"id": "c1", "name": "list_typical_configurations", "args": "{}"}]
        if len(tools) == 1:
            ch = _channel_from_list(tools[0]["content"])
            return "", [{"id": "c2", "name": "trace_typical_movements", "args": json.dumps(
                {"channel_id": ch, "register_qualified_name": REGISTER, "direction": "writes"})}]
        mv = json.loads(tools[1]["content"])
        docs = sorted(w["method_qualified_name"] for w in mv["writes"])
        return "Движения формируют: " + ", ".join(docs), []

    client = FakeLLMClient(script)
    res = await run_grounding_turn(client, db_seeded, api_key="x", question="движения?", system=SYSTEM)

    assert res["exhausted"] is False
    names = [t["name"] for t in res["tool_trace"]]
    assert names == ["list_typical_configurations", "trace_typical_movements"]
    # channel прокинулся из list_configs в trace_movements (round-trip):
    assert res["tool_trace"][1]["args"]["channel_id"] == CHANNEL
    assert res["tool_trace"][1]["result"]["total_writes"] == 2
    assert RTU in res["answer"] and VVOD in res["answer"]


# ─── Киллер-UC 2: цепочка/impact ──────────────────────────────────────


@pytest.mark.asyncio
async def test_grounding_calls_impact(db_seeded):
    """trace_typical_calls(in) от общего метода → impact = 2 документа."""
    def script(messages):
        tools = _last_tool_results(messages)
        if not tools:
            return "", [{"id": "c1", "name": "trace_typical_calls", "args": json.dumps(
                {"channel_id": CHANNEL, "qualified_name": COMMON, "direction": "in"})}]
        hits = json.loads(tools[0]["content"])["hits"]
        callers = [h["qualified_name"] for h in hits if h["depth"] == 1]
        return f"Зависят {len(callers)} вызывающих: " + ", ".join(sorted(callers)), []

    client = FakeLLMClient(script)
    res = await run_grounding_turn(client, db_seeded, api_key="x", question="impact?", system=SYSTEM)

    assert res["tool_trace"][0]["name"] == "trace_typical_calls"
    assert "Зависят 2" in res["answer"]
    assert RTU_METHOD in res["answer"]


# ─── Киллер-UC 3: RLS per-right ───────────────────────────────────────


@pytest.mark.asyncio
async def test_grounding_rls_per_right(db_seeded):
    """explain_rls_restrictions → оба права/условия в ответе."""
    def script(messages):
        tools = _last_tool_results(messages)
        if not tools:
            return "", [{"id": "c1", "name": "explain_rls_restrictions", "args": json.dumps(
                {"channel_id": CHANNEL, "object_qualified_name": CATALOG})}]
        data = json.loads(tools[0]["content"])
        pairs = [f'{r["right"]}={r["condition"]}' for r in data["restrictions"]]
        return "Ограничения: " + "; ".join(pairs), []

    client = FakeLLMClient(script)
    res = await run_grounding_turn(client, db_seeded, api_key="x", question="rls?", system=SYSTEM)

    data = res["tool_trace"][0]["result"]
    assert data["roles_total"] == 1 and data["total"] == 2
    assert "Read=Условие_Чтение" in res["answer"]
    assert "Update=Условие_Изменение" in res["answer"]


# ─── Краевые случаи оркестрации ───────────────────────────────────────


@pytest.mark.asyncio
async def test_grounding_direct_answer_without_tools(db_seeded):
    """LLM отвечает сразу, без инструментов → пустой trace, 1 раунд."""
    client = FakeLLMClient(lambda m: ("Прямой ответ.", []))
    res = await run_grounding_turn(client, db_seeded, api_key="x", question="?", system=SYSTEM)
    assert res["answer"] == "Прямой ответ."
    assert res["tool_trace"] == [] and res["rounds"] == 1 and res["exhausted"] is False


@pytest.mark.asyncio
async def test_grounding_max_rounds_guard(db_seeded):
    """LLM зацикливается на инструментах → exhausted, answer=None."""
    def loop_script(messages):
        return "", [{"id": "c", "name": "list_typical_configurations", "args": "{}"}]

    client = FakeLLMClient(loop_script)
    res = await run_grounding_turn(client, db_seeded, api_key="x", question="?",
                                   system=SYSTEM, max_rounds=3)
    assert res["exhausted"] is True and res["answer"] is None and res["rounds"] == 3


@pytest.mark.asyncio
async def test_grounding_handles_tool_error_gracefully(db_seeded):
    """Инструмент с битым qname → ошибка в trace, цикл не падает, даёт ответ."""
    def script(messages):
        tools = _last_tool_results(messages)
        if not tools:
            return "", [{"id": "c1", "name": "trace_typical_calls", "args": json.dumps(
                {"channel_id": CHANNEL, "qualified_name": "Нет.Такого.Узла", "direction": "out"})}]
        return "Узел не найден — уточните имя.", []

    client = FakeLLMClient(script)
    res = await run_grounding_turn(client, db_seeded, api_key="x", question="?", system=SYSTEM)
    assert res["tool_trace"][0]["ok"] is False
    assert res["answer"] == "Узел не найден — уточните имя."


# ─── Реассембл стрим-дельт ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_stream_reassembles_split_tool_args(db_seeded):
    """arguments tool-call, разбитые на 2 дельты, собираются корректно."""
    def script(messages):
        tools = _last_tool_results(messages)
        if not tools:
            return "", [{"id": "c1", "name": "trace_typical_movements", "args": json.dumps(
                {"channel_id": CHANNEL, "register_qualified_name": REGISTER, "direction": "writes"})}]
        return "ok", []

    client = FakeLLMClient(script, split_args=True)
    res = await run_grounding_turn(client, db_seeded, api_key="x", question="?", system=SYSTEM)
    # Если реассембл сломан — JSON args не распарсится и channel_id не дойдёт.
    assert res["tool_trace"][0]["args"]["register_qualified_name"] == REGISTER
    assert res["tool_trace"][0]["result"]["total_writes"] == 2


@pytest.mark.asyncio
async def test_collect_stream_direct(db_seeded):
    """collect_stream напрямую: content + 1 tool_call в одном проходе."""
    client = FakeLLMClient(lambda m: ("текст", [{"id": "c", "name": "list_typical_configurations", "args": "{}"}]))
    content, calls = await collect_stream(client, [], "x", None, 0.2)
    assert content == "текст"
    assert calls == [{"id": "c", "name": "list_typical_configurations", "args": "{}"}]
