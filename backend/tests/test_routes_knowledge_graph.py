"""Tests for GET /knowledge/{channel}/graph/{qname} (M-K3.17.7).

Драйвит endpoint через AsyncClient (in-memory app.state.db) — happy-path
инжектит узлы/рёбра прямо в app.state.db (тот же connection, что и endpoint).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.knowledge.graph_storage import insert_edge, insert_node


@pytest.mark.asyncio
async def test_graph_route_404_when_no_graph(client: AsyncClient) -> None:
    resp = await client.get("/knowledge/ch-x/graph/ОбщегоНазначения.НетТакого")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["error"] == "node_not_found"
    assert "граф" in detail["hint"].lower()


@pytest.mark.asyncio
async def test_graph_route_invalid_depth_422(client: AsyncClient) -> None:
    """depth=0 нарушает Query(ge=1) → FastAPI 422 (валидация до get_subgraph)."""
    resp = await client.get("/knowledge/ch-x/graph/Модуль.Метод?depth=0")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_graph_route_invalid_direction_422(client: AsyncClient) -> None:
    resp = await client.get("/knowledge/ch-x/graph/Модуль.Метод?direction=both")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_graph_route_returns_subgraph(client: AsyncClient) -> None:
    """A→B→C в app.state.db → endpoint отдаёт 3 узла + 2 ребра с depth."""
    from app.main import app

    db = app.state.db
    a = await insert_node(
        db, channel_id="ch-g", node_kind="Method", qualified_name="ОбщегоНазначения.A"
    )
    b = await insert_node(
        db, channel_id="ch-g", node_kind="Method", qualified_name="ОбщегоНазначения.B"
    )
    c_id = await insert_node(
        db, channel_id="ch-g", node_kind="Method", qualified_name="ОбщегоНазначения.C"
    )
    await insert_edge(db, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db, src_id=b, dst_id=c_id, edge_kind="CALLS")

    resp = await client.get("/knowledge/ch-g/graph/ОбщегоНазначения.A?depth=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["center"]["qualified_name"] == "ОбщегоНазначения.A"
    names = {n["qualified_name"] for n in body["nodes"]}
    assert names == {"ОбщегоНазначения.A", "ОбщегоНазначения.B", "ОбщегоНазначения.C"}
    assert body["total_reached"] == 3
    assert body["truncated"] is False
    assert {e["edge_kind"] for e in body["edges"]} == {"CALLS"}
    assert len(body["edges"]) == 2  # A→B, B→C
    assert all("depth" in n for n in body["nodes"])


@pytest.mark.asyncio
async def test_graph_route_edge_kind_filter(client: AsyncClient) -> None:
    """edge_kind=CALLS → ребро USES не идёт в traversal и в подграф."""
    from app.main import app

    db = app.state.db
    a = await insert_node(db, channel_id="ch-ek", node_kind="Method", qualified_name="М.A")
    b = await insert_node(db, channel_id="ch-ek", node_kind="Method", qualified_name="М.B")
    cc = await insert_node(db, channel_id="ch-ek", node_kind="Method", qualified_name="М.C")
    await insert_edge(db, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db, src_id=a, dst_id=cc, edge_kind="USES")

    resp = await client.get("/knowledge/ch-ek/graph/М.A?depth=2&edge_kind=CALLS")
    assert resp.status_code == 200
    names = {n["qualified_name"] for n in resp.json()["nodes"]}
    assert names == {"М.A", "М.B"}
