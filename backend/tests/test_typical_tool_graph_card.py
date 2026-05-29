"""Tests for build_graph_card (M-K3.17.7) — graph-card из trace_typical_calls."""

from __future__ import annotations

import aiosqlite
import pytest

from app.knowledge.graph_storage import insert_edge, insert_node
from app.knowledge.typical.tool import build_graph_card
from app.storage.migrations import apply_migrations


@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON")
    await apply_migrations(conn)
    yield conn
    await conn.close()


async def _seed_calls(db, channel: str):
    a = await insert_node(db, channel_id=channel, node_kind="Method", qualified_name="Module.A")
    b = await insert_node(db, channel_id=channel, node_kind="Method", qualified_name="Module.B")
    c = await insert_node(db, channel_id=channel, node_kind="Method", qualified_name="Module.C")
    await insert_edge(db, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db, src_id=b, dst_id=c, edge_kind="CALLS")
    return a, b, c


@pytest.mark.asyncio
async def test_build_graph_card_trace_calls(db):
    await _seed_calls(db, "_t")
    card = await build_graph_card(db, "trace_typical_calls", {
        "channel_id": "_t", "qualified_name": "Module.A", "direction": "out", "depth": 3,
    })
    assert card is not None
    assert card["type"] == "graph"
    p = card["payload"]
    assert p["center"]["qualified_name"] == "Module.A"
    assert p["tool_name"] == "trace_typical_calls"
    names = {n["qualified_name"] for n in p["nodes"]}
    assert names == {"Module.A", "Module.B", "Module.C"}
    assert len(p["edges"]) == 2
    assert all(e["edge_kind"] == "CALLS" for e in p["edges"])


@pytest.mark.asyncio
async def test_build_graph_card_non_graph_tool(db):
    await _seed_calls(db, "_t")
    card = await build_graph_card(db, "explain_typical_object", {
        "channel_id": "_t", "object_qualified_name": "Module.A",
    })
    assert card is None


@pytest.mark.asyncio
async def test_build_graph_card_node_not_found(db):
    card = await build_graph_card(db, "trace_typical_calls", {
        "channel_id": "_t", "qualified_name": "НетТакого", "direction": "out", "depth": 2,
    })
    assert card is None


@pytest.mark.asyncio
async def test_build_graph_card_no_edges_returns_none(db):
    # Изолированный метод без CALLS → нет рёбер → карточка не строится.
    await insert_node(db, channel_id="_t", node_kind="Method", qualified_name="Module.Lonely")
    card = await build_graph_card(db, "trace_typical_calls", {
        "channel_id": "_t", "qualified_name": "Module.Lonely", "direction": "out", "depth": 2,
    })
    assert card is None


@pytest.mark.asyncio
async def test_build_graph_card_bad_direction_returns_none(db):
    await _seed_calls(db, "_t")
    card = await build_graph_card(db, "trace_typical_calls", {
        "channel_id": "_t", "qualified_name": "Module.A", "direction": "both", "depth": 2,
    })
    assert card is None
