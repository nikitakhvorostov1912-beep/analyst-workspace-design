"""Тесты для typical/tool.py (M-K2.5.6 LLM Tools)."""

from __future__ import annotations

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.graph_storage import EdgeKind, NodeKind, insert_edge, insert_node
from app.knowledge.typical.card_models import CardStatus, TypicalObjectCard
from app.knowledge.typical.card_storage import upsert_card
from app.knowledge.typical.registry import TypicalConfigKind
from app.knowledge.typical.storage import create_configuration
from app.knowledge.typical.tool import (
    TOOL_COMPARE,
    TOOL_EXPLAIN,
    TOOL_LIST_CONFIGS,
    TOOL_SEARCH_OBJECTS,
    TOOL_TRACE_CALLS,
    TOOL_TRACE_MOVEMENTS,
    TYPICAL_TOOL_SCHEMAS,
    dispatch_typical_tool,
    is_typical_tool,
)
from app.storage.migrations import apply_migrations


@pytest_asyncio.fixture
async def db_ready():
    conn = await aiosqlite.connect(":memory:")
    try:
        await conn.execute("PRAGMA foreign_keys = ON")
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def db_with_seed(db_ready):
    """БД с typical config + минимальным графом + одной карточкой."""
    await create_configuration(
        db_ready, TypicalConfigKind.BP_30, "3.0.138.24",
        source_path="data/typical-snapshots/bp30-accounting",
    )

    channel = "_bp30_138_24"

    # MetadataObject Document.Заказ
    doc_id = await insert_node(
        db_ready, channel_id=channel, node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="Document.Заказ",
        attributes={"name": "Заказ", "kind": "Document", "comment": "Документ заказа"},
    )
    # Register
    reg_id = await insert_node(
        db_ready, channel_id=channel, node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="AccumulationRegister.ТоварыНаСкладах",
        attributes={"name": "ТоварыНаСкладах", "kind": "AccumulationRegister"},
    )
    # Module + Method
    mod_id = await insert_node(
        db_ready, channel_id=channel, node_kind=NodeKind.MODULE.value,
        qualified_name="Document.Заказ.ObjectModule",
        attributes={"module_kind": "ObjectModule"},
    )
    method_id = await insert_node(
        db_ready, channel_id=channel, node_kind=NodeKind.METHOD.value,
        qualified_name="Document.Заказ.ObjectModule.ОбработкаПроведения",
        attributes={"name": "ОбработкаПроведения", "module_kind": "ObjectModule"},
    )
    await insert_edge(db_ready, src_id=doc_id, dst_id=mod_id, edge_kind=EdgeKind.CONTAINS.value)
    await insert_edge(db_ready, src_id=mod_id, dst_id=method_id, edge_kind=EdgeKind.CONTAINS.value)
    await insert_edge(db_ready, src_id=method_id, dst_id=reg_id, edge_kind=EdgeKind.WRITES_TO.value)
    await insert_edge(
        db_ready, src_id=method_id, dst_id=reg_id,
        edge_kind=EdgeKind.READS_FROM.value,
        attributes={"via": "virtual_table", "virtual_kind": "Остатки"},
    )

    # Карточка для Заказа
    card = TypicalObjectCard(
        object_qualified_name="Document.Заказ",
        object_kind="Document",
        channel_id=channel,
        summary="Документ заказа покупателя.",
        purpose="Фиксирует заказ для последующей отгрузки.",
    )
    await upsert_card(
        db_ready, card=card, source_hash="h1",
        status=CardStatus.GENERATED,
    )

    return db_ready


# ─── Schemas ──────────────────────────────────────────────────────────


def test_typical_tool_schemas_count():
    assert len(TYPICAL_TOOL_SCHEMAS) == 6


def test_typical_tool_schemas_valid_openai_format():
    for s in TYPICAL_TOOL_SCHEMAS:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "description" in s["function"]
        assert "parameters" in s["function"]
        params = s["function"]["parameters"]
        assert params["type"] == "object"


def test_is_typical_tool_recognises_all_names():
    assert is_typical_tool(TOOL_LIST_CONFIGS)
    assert is_typical_tool(TOOL_SEARCH_OBJECTS)
    assert is_typical_tool(TOOL_EXPLAIN)
    assert is_typical_tool(TOOL_TRACE_CALLS)
    assert is_typical_tool(TOOL_TRACE_MOVEMENTS)
    assert is_typical_tool(TOOL_COMPARE)


def test_is_typical_tool_rejects_others():
    assert not is_typical_tool("search_its")
    assert not is_typical_tool("search_bsp")
    assert not is_typical_tool("get_metadata")


# ─── list_typical_configurations ──────────────────────────────────────


@pytest.mark.asyncio
async def test_list_configs_empty(db_ready):
    ok, result, err = await dispatch_typical_tool(
        db_ready, TOOL_LIST_CONFIGS, {},
    )
    assert ok is True
    assert err is None
    assert result["total"] == 0
    assert result["configurations"] == []


@pytest.mark.asyncio
async def test_list_configs_with_data(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_LIST_CONFIGS, {},
    )
    assert ok is True
    assert result["total"] == 1
    assert result["configurations"][0]["channel_id"] == "_bp30_138_24"
    assert result["configurations"][0]["config_version"] == "3.0.138.24"


# ─── search_typical_objects ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_by_qname_substring(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_SEARCH_OBJECTS,
        {"channel_id": "_bp30_138_24", "query": "заказ"},
    )
    assert ok is True
    assert result["total"] >= 1
    assert any("Заказ" in r["qualified_name"] for r in result["results"])


@pytest.mark.asyncio
async def test_search_filter_by_kind(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_SEARCH_OBJECTS,
        {"channel_id": "_bp30_138_24", "query": "товары", "object_kind": "AccumulationRegister"},
    )
    assert ok is True
    for r in result["results"]:
        assert r["kind"] == "AccumulationRegister"


@pytest.mark.asyncio
async def test_search_missing_query_raises(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_SEARCH_OBJECTS,
        {"channel_id": "_bp30_138_24"},
    )
    assert ok is False
    assert err is not None
    assert "query" in err.lower()


@pytest.mark.asyncio
async def test_search_finds_by_summary(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_SEARCH_OBJECTS,
        {"channel_id": "_bp30_138_24", "query": "фиксирует"},
    )
    assert ok is True
    assert any(r["has_card"] for r in result["results"])


# ─── explain_typical_object ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_explain_with_card(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_EXPLAIN,
        {"channel_id": "_bp30_138_24", "object_qualified_name": "Document.Заказ"},
    )
    assert ok is True
    assert result["object_kind"] == "Document"
    assert result["card"] is not None
    assert result["card"]["summary"] == "Документ заказа покупателя."
    assert result["card_status"] == "generated"


@pytest.mark.asyncio
async def test_explain_without_card(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_EXPLAIN,
        {"channel_id": "_bp30_138_24",
         "object_qualified_name": "AccumulationRegister.ТоварыНаСкладах"},
    )
    assert ok is True
    assert result["card"] is None
    assert result["card_status"] == "not_generated"


@pytest.mark.asyncio
async def test_explain_missing_object(db_with_seed):
    """M-K2.5.9.7 — Cold start fallback.

    Раньше возвращали (False, None, error). Теперь возвращаем
    (True, structured_payload, None) с card_status='not_in_graph',
    чтобы LLM не галлюцинировала и могла предложить suggestions.
    """
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_EXPLAIN,
        {"channel_id": "_bp30_138_24", "object_qualified_name": "Document.Unknown"},
    )
    assert ok is True
    assert err is None
    assert result["card_status"] == "not_in_graph"
    assert result["card"] is None
    assert "card_warning" in result
    assert "suggestions" in result  # may be [] if no similar names


@pytest.mark.asyncio
async def test_explain_includes_children_summary(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_EXPLAIN,
        {"channel_id": "_bp30_138_24", "object_qualified_name": "Document.Заказ"},
    )
    assert ok is True
    assert "Module" in result["children_summary"]


# ─── trace_typical_calls ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trace_calls_no_calls(db_with_seed):
    # У ОбработкаПроведения нет CALLS edges в seed
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_TRACE_CALLS,
        {
            "channel_id": "_bp30_138_24",
            "qualified_name": "Document.Заказ.ObjectModule.ОбработкаПроведения",
            "direction": "out",
        },
    )
    assert ok is True
    # Стартовый node всегда в hits (depth=0)
    assert result["total"] >= 1


@pytest.mark.asyncio
async def test_trace_calls_invalid_direction(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_TRACE_CALLS,
        {
            "channel_id": "_bp30_138_24",
            "qualified_name": "Document.Заказ.ObjectModule.ОбработкаПроведения",
            "direction": "both",  # не поддерживается в traverse_bfs
        },
    )
    assert ok is False
    assert err is not None


@pytest.mark.asyncio
async def test_trace_calls_unknown_node(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_TRACE_CALLS,
        {
            "channel_id": "_bp30_138_24",
            "qualified_name": "Module.X.МетодНетВГрафе",
            "direction": "out",
        },
    )
    assert ok is False
    assert "не найден" in err.lower()


# ─── trace_typical_movements ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_trace_movements_both(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_TRACE_MOVEMENTS,
        {
            "channel_id": "_bp30_138_24",
            "register_qualified_name": "AccumulationRegister.ТоварыНаСкладах",
        },
    )
    assert ok is True
    assert result["total_writes"] == 1
    assert result["total_reads"] == 1
    assert "ОбработкаПроведения" in result["writes"][0]["method_qualified_name"]


@pytest.mark.asyncio
async def test_trace_movements_writes_only(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_TRACE_MOVEMENTS,
        {
            "channel_id": "_bp30_138_24",
            "register_qualified_name": "AccumulationRegister.ТоварыНаСкладах",
            "direction": "writes",
        },
    )
    assert ok is True
    assert result["total_writes"] == 1
    assert result["reads"] == []


@pytest.mark.asyncio
async def test_trace_movements_register_not_found(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_TRACE_MOVEMENTS,
        {
            "channel_id": "_bp30_138_24",
            "register_qualified_name": "AccumulationRegister.НесуществующийРегистр",
        },
    )
    assert ok is False


# ─── compare_with_typical ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compare_returns_not_implemented(db_with_seed):
    ok, result, err = await dispatch_typical_tool(
        db_with_seed, TOOL_COMPARE,
        {
            "typical_channel_id": "_bp30_138_24",
            "client_channel_id": "_client_x_",
            "object_qualified_name": "Document.Заказ",
        },
    )
    assert ok is True
    assert result["status"] == "not_implemented"


# ─── Dispatcher edge cases ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_unknown_tool(db_ready):
    ok, result, err = await dispatch_typical_tool(
        db_ready, "search_xyz", {},
    )
    assert ok is False
    assert "неизвестн" in err.lower()


@pytest.mark.asyncio
async def test_dispatch_non_dict_args(db_ready):
    ok, result, err = await dispatch_typical_tool(
        db_ready, TOOL_LIST_CONFIGS, "not a dict",  # type: ignore[arg-type]
    )
    assert ok is False
    assert "dict" in err.lower()
