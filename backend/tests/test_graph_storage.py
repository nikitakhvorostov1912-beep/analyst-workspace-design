"""Тесты для backend/app/knowledge/graph_storage.py (M-K3.17.1a).

Покрытие:
- Migration v16: graph_nodes / graph_edges tables + UNIQUE / индексы
- _serialize_attrs / _deserialize_attrs (JSON roundtrip)
- insert_node: новый / upsert / валидация
- get_node / find_node / list_nodes
- insert_edge: new / upsert / self-loop reject
- get_edges_from / get_edges_to / get_neighbors (out/in/both)
- traverse_bfs: depth=1 / depth=N / cycle protection / edge_kind filter
- counts + delete_channel_graph (cascade)
- NodeKind / EdgeKind enum coverage
"""

from __future__ import annotations

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.graph_storage import (
    MAX_TRAVERSAL_DEPTH,
    EdgeKind,
    GraphEdge,
    GraphNode,
    GraphStorageError,
    NodeKind,
    Subgraph,
    TraversalHit,
    _deserialize_attrs,
    _serialize_attrs,
    count_by_kind,
    count_edges,
    count_nodes,
    delete_channel_graph,
    find_node,
    get_edges_from,
    get_edges_to,
    get_neighbors,
    get_node,
    get_subgraph,
    insert_edge,
    insert_node,
    list_nodes,
    traverse_bfs,
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


# ---------- Migration v16 ----------


@pytest.mark.asyncio
async def test_migration_v16_creates_graph_tables():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('graph_nodes', 'graph_edges')"
        )
        rows = await cursor.fetchall()
        names = {r[0] for r in rows}
        assert names == {"graph_nodes", "graph_edges"}
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v16_indexes():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_graph_%'"
        )
        rows = await cursor.fetchall()
        names = {r[0] for r in rows}
        assert names == {
            "idx_graph_nodes_channel",
            "idx_graph_nodes_qname",
            "idx_graph_nodes_kind",
            "idx_graph_edges_src",
            "idx_graph_edges_dst",
            "idx_graph_edges_kind",
        }
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v16_nodes_unique_natural_key(db_ready):
    """UNIQUE(channel_id, qualified_name, node_kind) — повтор → IntegrityError."""
    await db_ready.execute(
        "INSERT INTO graph_nodes (channel_id, node_kind, qualified_name) "
        "VALUES ('ch-1', 'Method', 'X.Y')"
    )
    await db_ready.commit()
    with pytest.raises(aiosqlite.IntegrityError):
        await db_ready.execute(
            "INSERT INTO graph_nodes (channel_id, node_kind, qualified_name) "
            "VALUES ('ch-1', 'Method', 'X.Y')"
        )
        await db_ready.commit()


@pytest.mark.asyncio
async def test_migration_v16_edges_cascade(db_ready):
    """ON DELETE CASCADE: удаление node удаляет связанные edges."""
    id_a = await insert_node(
        db_ready, channel_id="ch-1", node_kind="Method", qualified_name="A",
    )
    id_b = await insert_node(
        db_ready, channel_id="ch-1", node_kind="Method", qualified_name="B",
    )
    await insert_edge(db_ready, src_id=id_a, dst_id=id_b, edge_kind="CALLS")

    await db_ready.execute("DELETE FROM graph_nodes WHERE id = ?", (id_a,))
    await db_ready.commit()

    cursor = await db_ready.execute("SELECT COUNT(*) FROM graph_edges")
    row = await cursor.fetchone()
    assert int(row[0]) == 0


# ---------- _serialize_attrs / _deserialize_attrs ----------


def test_serialize_empty_attrs():
    assert _serialize_attrs(None) == "{}"
    assert _serialize_attrs({}) == "{}"


def test_serialize_sort_keys_for_stability():
    s1 = _serialize_attrs({"b": 2, "a": 1})
    s2 = _serialize_attrs({"a": 1, "b": 2})
    assert s1 == s2


def test_serialize_unicode_preserved():
    s = _serialize_attrs({"имя": "Документ"})
    assert "имя" in s
    assert "\\u" not in s  # not escaped


def test_serialize_non_serializable_raises():
    class X:
        pass

    with pytest.raises(GraphStorageError):
        _serialize_attrs({"obj": X()})


def test_deserialize_handles_invalid_json():
    assert _deserialize_attrs("") == {}
    assert _deserialize_attrs(None) == {}
    assert _deserialize_attrs("not json") == {}


def test_deserialize_rejects_non_dict_json():
    """Если в attributes лежит список — deserializer вернёт {} (safe)."""
    assert _deserialize_attrs("[1,2,3]") == {}


# ---------- insert_node ----------


@pytest.mark.asyncio
async def test_insert_node_returns_id(db_ready):
    node_id = await insert_node(
        db_ready, channel_id="ch-1", node_kind="Method", qualified_name="ОбщегоНазначения.X",
    )
    assert node_id > 0


@pytest.mark.asyncio
async def test_insert_node_idempotent_upsert(db_ready):
    """Повторный вызов с теми же ключами → тот же id, обновлены attributes."""
    id1 = await insert_node(
        db_ready, channel_id="ch-1", node_kind="Method", qualified_name="X",
        attributes={"v": 1},
    )
    id2 = await insert_node(
        db_ready, channel_id="ch-1", node_kind="Method", qualified_name="X",
        attributes={"v": 2},
    )
    assert id1 == id2

    node = await get_node(db_ready, id1)
    assert node is not None
    assert node.attributes == {"v": 2}


@pytest.mark.asyncio
async def test_insert_node_rejects_empty_args(db_ready):
    with pytest.raises(GraphStorageError):
        await insert_node(db_ready, channel_id="", node_kind="Method", qualified_name="X")
    with pytest.raises(GraphStorageError):
        await insert_node(db_ready, channel_id="ch", node_kind="", qualified_name="X")
    with pytest.raises(GraphStorageError):
        await insert_node(db_ready, channel_id="ch", node_kind="M", qualified_name="")


# ---------- get_node / find_node / list_nodes ----------


@pytest.mark.asyncio
async def test_get_node_returns_full_record(db_ready):
    id1 = await insert_node(
        db_ready,
        channel_id="ch-1",
        node_kind="Method",
        qualified_name="Mod.M1",
        source_path="src/path",
        attributes={"line": 42},
    )
    node = await get_node(db_ready, id1)
    assert isinstance(node, GraphNode)
    assert node.id == id1
    assert node.qualified_name == "Mod.M1"
    assert node.source_path == "src/path"
    assert node.attributes == {"line": 42}


@pytest.mark.asyncio
async def test_get_node_returns_none_for_unknown(db_ready):
    assert await get_node(db_ready, 99999) is None


@pytest.mark.asyncio
async def test_find_node_by_natural_key(db_ready):
    await insert_node(db_ready, channel_id="ch-1", node_kind="Method", qualified_name="X")
    found = await find_node(
        db_ready, channel_id="ch-1", qualified_name="X", node_kind="Method",
    )
    assert found is not None
    assert found.qualified_name == "X"


@pytest.mark.asyncio
async def test_find_node_returns_none_for_unknown(db_ready):
    found = await find_node(
        db_ready, channel_id="ch-1", qualified_name="ghost", node_kind="Method",
    )
    assert found is None


@pytest.mark.asyncio
async def test_list_nodes_filters_by_channel(db_ready):
    await insert_node(db_ready, channel_id="ch-A", node_kind="Method", qualified_name="A1")
    await insert_node(db_ready, channel_id="ch-B", node_kind="Method", qualified_name="B1")

    nodes_a = await list_nodes(db_ready, channel_id="ch-A")
    assert [n.qualified_name for n in nodes_a] == ["A1"]


@pytest.mark.asyncio
async def test_list_nodes_filters_by_kind(db_ready):
    await insert_node(db_ready, channel_id="ch-1", node_kind="Method", qualified_name="M1")
    await insert_node(db_ready, channel_id="ch-1", node_kind="Module", qualified_name="Mod1")

    methods = await list_nodes(db_ready, channel_id="ch-1", node_kind="Method")
    assert len(methods) == 1
    assert methods[0].qualified_name == "M1"


# ---------- insert_edge ----------


@pytest.mark.asyncio
async def test_insert_edge_returns_id(db_ready):
    a = await insert_node(db_ready, channel_id="ch", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="ch", node_kind="Method", qualified_name="B")
    edge_id = await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    assert edge_id > 0


@pytest.mark.asyncio
async def test_insert_edge_idempotent(db_ready):
    a = await insert_node(db_ready, channel_id="ch", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="ch", node_kind="Method", qualified_name="B")
    e1 = await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    e2 = await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS",
                            attributes={"updated": True})
    assert e1 == e2


@pytest.mark.asyncio
async def test_insert_edge_rejects_self_loop(db_ready):
    a = await insert_node(db_ready, channel_id="ch", node_kind="Method", qualified_name="A")
    with pytest.raises(GraphStorageError, match="Self-loop"):
        await insert_edge(db_ready, src_id=a, dst_id=a, edge_kind="CALLS")


@pytest.mark.asyncio
async def test_insert_edge_multiple_kinds_between_same_nodes(db_ready):
    """A → B может иметь и CALLS, и USES — это разные edges."""
    a = await insert_node(db_ready, channel_id="ch", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="ch", node_kind="Method", qualified_name="B")
    e1 = await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    e2 = await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="USES")
    assert e1 != e2


# ---------- get_edges / get_neighbors ----------


@pytest.mark.asyncio
async def test_get_edges_from_returns_outgoing(db_ready):
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    c = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="C")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db_ready, src_id=a, dst_id=c, edge_kind="USES")

    edges = await get_edges_from(db_ready, a)
    assert len(edges) == 2
    kinds = {e.edge_kind for e in edges}
    assert kinds == {"CALLS", "USES"}


@pytest.mark.asyncio
async def test_get_edges_from_filtered_by_kind(db_ready):
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    c = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="C")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db_ready, src_id=a, dst_id=c, edge_kind="USES")

    edges = await get_edges_from(db_ready, a, edge_kind="CALLS")
    assert len(edges) == 1
    assert edges[0].dst_id == b


@pytest.mark.asyncio
async def test_get_edges_to_returns_incoming(db_ready):
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    c = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="C")
    await insert_edge(db_ready, src_id=b, dst_id=a, edge_kind="CALLS")
    await insert_edge(db_ready, src_id=c, dst_id=a, edge_kind="CALLS")

    edges = await get_edges_to(db_ready, a)
    assert len(edges) == 2


@pytest.mark.asyncio
async def test_get_neighbors_out_direction(db_ready):
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    c = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="C")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db_ready, src_id=c, dst_id=a, edge_kind="CALLS")  # incoming

    nbrs = await get_neighbors(db_ready, a, direction="out")
    names = {n.qualified_name for n in nbrs}
    assert names == {"B"}


@pytest.mark.asyncio
async def test_get_neighbors_both_directions(db_ready):
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    c = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="C")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db_ready, src_id=c, dst_id=a, edge_kind="CALLS")

    nbrs = await get_neighbors(db_ready, a, direction="both")
    names = {n.qualified_name for n in nbrs}
    assert names == {"B", "C"}


@pytest.mark.asyncio
async def test_get_neighbors_invalid_direction(db_ready):
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    with pytest.raises(GraphStorageError):
        await get_neighbors(db_ready, a, direction="diagonal")


# ---------- traverse_bfs ----------


@pytest.mark.asyncio
async def test_traverse_bfs_depth_1(db_ready):
    """A → B → C, traverse from A depth=1 → [A(0), B(1)]."""
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    c = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="C")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db_ready, src_id=b, dst_id=c, edge_kind="CALLS")

    hits = await traverse_bfs(db_ready, a, max_depth=1)
    depths = sorted([h.depth for h in hits])
    names = {h.node.qualified_name for h in hits}
    assert depths == [0, 1]
    assert names == {"A", "B"}


@pytest.mark.asyncio
async def test_traverse_bfs_depth_full(db_ready):
    """Глубина 5 покрывает всю цепочку."""
    ids = []
    for n in "ABCDE":
        ids.append(await insert_node(
            db_ready, channel_id="c", node_kind="Method", qualified_name=n,
        ))
    for i in range(4):
        await insert_edge(db_ready, src_id=ids[i], dst_id=ids[i + 1], edge_kind="CALLS")

    hits = await traverse_bfs(db_ready, ids[0], max_depth=5)
    assert len(hits) == 5


@pytest.mark.asyncio
async def test_traverse_bfs_cycle_protection(db_ready):
    """A → B → A не вешает BFS — depth limit + dedup."""
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db_ready, src_id=b, dst_id=a, edge_kind="CALLS")

    hits = await traverse_bfs(db_ready, a, max_depth=5)
    # A появляется один раз (depth=0), B один раз (depth=1)
    seen = {h.node.qualified_name for h in hits}
    assert seen == {"A", "B"}


@pytest.mark.asyncio
async def test_traverse_bfs_edge_kind_filter(db_ready):
    """Фильтр edge_kind не идёт по USES если запрошен CALLS."""
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    c = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="C")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db_ready, src_id=a, dst_id=c, edge_kind="USES")

    hits = await traverse_bfs(db_ready, a, max_depth=2, edge_kind="CALLS")
    names = {h.node.qualified_name for h in hits}
    assert names == {"A", "B"}


@pytest.mark.asyncio
async def test_traverse_bfs_in_direction(db_ready):
    """reverse traversal: 'кто вызывает A'."""
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    c = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="C")
    await insert_edge(db_ready, src_id=b, dst_id=a, edge_kind="CALLS")
    await insert_edge(db_ready, src_id=c, dst_id=b, edge_kind="CALLS")

    hits = await traverse_bfs(db_ready, a, max_depth=2, direction="in")
    names = {h.node.qualified_name for h in hits}
    assert names == {"A", "B", "C"}


@pytest.mark.asyncio
async def test_traverse_bfs_path_kinds_populated(db_ready):
    """Каждый hit должен содержать path_kinds — sequence edge_kind'ов."""
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")

    hits = await traverse_bfs(db_ready, a, max_depth=1)
    a_hit = next(h for h in hits if h.node.qualified_name == "A")
    b_hit = next(h for h in hits if h.node.qualified_name == "B")
    assert a_hit.path_kinds == ()
    assert b_hit.path_kinds == ("CALLS",)


@pytest.mark.asyncio
async def test_traverse_bfs_validates_max_depth(db_ready):
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    with pytest.raises(GraphStorageError, match="max_depth"):
        await traverse_bfs(db_ready, a, max_depth=0)
    with pytest.raises(GraphStorageError):
        await traverse_bfs(db_ready, a, max_depth=MAX_TRAVERSAL_DEPTH + 1)


# ---------- get_subgraph ----------


@pytest.mark.asyncio
async def test_get_subgraph_basic(db_ready):
    """A→B→C, A→D. Подграф от A depth=2 → 4 узла + 3 индуцированных ребра."""
    ids = {}
    for n in "ABCD":
        ids[n] = await insert_node(
            db_ready, channel_id="c", node_kind="Method", qualified_name=n,
        )
    await insert_edge(db_ready, src_id=ids["A"], dst_id=ids["B"], edge_kind="CALLS")
    await insert_edge(db_ready, src_id=ids["B"], dst_id=ids["C"], edge_kind="CALLS")
    await insert_edge(db_ready, src_id=ids["A"], dst_id=ids["D"], edge_kind="CALLS")

    sg = await get_subgraph(db_ready, channel_id="c", start_qname="A", max_depth=2)
    assert isinstance(sg, Subgraph)
    assert sg.center is not None and sg.center.qualified_name == "A"
    names = {h.node.qualified_name for h in sg.hits}
    assert names == {"A", "B", "C", "D"}
    edge_pairs = {(e.src_id, e.dst_id) for e in sg.edges}
    assert edge_pairs == {
        (ids["A"], ids["B"]),
        (ids["B"], ids["C"]),
        (ids["A"], ids["D"]),
    }
    assert sg.truncated is False
    assert sg.total_reached == 4


@pytest.mark.asyncio
async def test_get_subgraph_induced_edges_only(db_ready):
    """max_depth=1: C вне набора → ребро B→C НЕ попадает в подграф."""
    ids = {}
    for n in "ABC":
        ids[n] = await insert_node(
            db_ready, channel_id="c", node_kind="Method", qualified_name=n,
        )
    await insert_edge(db_ready, src_id=ids["A"], dst_id=ids["B"], edge_kind="CALLS")
    await insert_edge(db_ready, src_id=ids["B"], dst_id=ids["C"], edge_kind="CALLS")

    sg = await get_subgraph(db_ready, channel_id="c", start_qname="A", max_depth=1)
    names = {h.node.qualified_name for h in sg.hits}
    assert names == {"A", "B"}
    edge_pairs = {(e.src_id, e.dst_id) for e in sg.edges}
    assert edge_pairs == {(ids["A"], ids["B"])}  # B→C исключено (C не отображается)


@pytest.mark.asyncio
async def test_get_subgraph_truncated(db_ready):
    """max_nodes cap → truncated=True, hits урезаны, total_reached полный."""
    root = await insert_node(
        db_ready, channel_id="c", node_kind="Method", qualified_name="ROOT",
    )
    for i in range(5):
        child = await insert_node(
            db_ready, channel_id="c", node_kind="Method", qualified_name=f"N{i}",
        )
        await insert_edge(db_ready, src_id=root, dst_id=child, edge_kind="CALLS")

    sg = await get_subgraph(
        db_ready, channel_id="c", start_qname="ROOT", max_depth=1, max_nodes=3,
    )
    assert sg.truncated is True
    assert len(sg.hits) == 3
    assert sg.total_reached == 6  # ROOT + 5 детей


@pytest.mark.asyncio
async def test_get_subgraph_not_found(db_ready):
    sg = await get_subgraph(db_ready, channel_id="c", start_qname="НетТакого", max_depth=2)
    assert sg.center is None
    assert sg.hits == ()
    assert sg.edges == ()
    assert sg.total_reached == 0


@pytest.mark.asyncio
async def test_get_subgraph_edge_kind_filter(db_ready):
    """edge_kind='CALLS' → ребро USES не учитывается ни в traversal, ни в edges."""
    ids = {}
    for n in "ABC":
        ids[n] = await insert_node(
            db_ready, channel_id="c", node_kind="Method", qualified_name=n,
        )
    await insert_edge(db_ready, src_id=ids["A"], dst_id=ids["B"], edge_kind="CALLS")
    await insert_edge(db_ready, src_id=ids["A"], dst_id=ids["C"], edge_kind="USES")

    sg = await get_subgraph(
        db_ready, channel_id="c", start_qname="A", max_depth=2, edge_kind="CALLS",
    )
    names = {h.node.qualified_name for h in sg.hits}
    assert names == {"A", "B"}
    assert all(e.edge_kind == "CALLS" for e in sg.edges)


@pytest.mark.asyncio
async def test_get_subgraph_to_dict_shape(db_ready):
    """to_dict — React-Flow-friendly: nodes с depth, edges с src/dst/kind."""
    a = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="c", node_kind="Method", qualified_name="B")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")

    d = (await get_subgraph(db_ready, channel_id="c", start_qname="A", max_depth=1)).to_dict()
    assert set(d) == {"center", "nodes", "edges", "total_reached", "truncated"}
    assert d["center"]["qualified_name"] == "A"
    assert all("depth" in n for n in d["nodes"])
    assert d["edges"][0]["edge_kind"] == "CALLS"


# ---------- Counts ----------


@pytest.mark.asyncio
async def test_count_nodes(db_ready):
    await insert_node(db_ready, channel_id="ch-A", node_kind="Method", qualified_name="A")
    await insert_node(db_ready, channel_id="ch-A", node_kind="Method", qualified_name="B")
    await insert_node(db_ready, channel_id="ch-B", node_kind="Method", qualified_name="C")

    assert await count_nodes(db_ready) == 3
    assert await count_nodes(db_ready, "ch-A") == 2
    assert await count_nodes(db_ready, "ch-B") == 1


@pytest.mark.asyncio
async def test_count_edges_per_channel(db_ready):
    a = await insert_node(db_ready, channel_id="ch-A", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="ch-A", node_kind="Method", qualified_name="B")
    c = await insert_node(db_ready, channel_id="ch-B", node_kind="Method", qualified_name="C")
    d = await insert_node(db_ready, channel_id="ch-B", node_kind="Method", qualified_name="D")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")
    await insert_edge(db_ready, src_id=c, dst_id=d, edge_kind="CALLS")

    assert await count_edges(db_ready) == 2
    assert await count_edges(db_ready, "ch-A") == 1
    assert await count_edges(db_ready, "ch-B") == 1


@pytest.mark.asyncio
async def test_count_by_kind_breakdown(db_ready):
    await insert_node(db_ready, channel_id="ch", node_kind="Method", qualified_name="M1")
    await insert_node(db_ready, channel_id="ch", node_kind="Method", qualified_name="M2")
    await insert_node(db_ready, channel_id="ch", node_kind="Module", qualified_name="Mod1")

    breakdown = await count_by_kind(db_ready, "ch")
    assert breakdown == {"Method": 2, "Module": 1}


# ---------- delete_channel_graph (cascade) ----------


@pytest.mark.asyncio
async def test_delete_channel_graph_cascade(db_ready):
    a = await insert_node(db_ready, channel_id="ch-A", node_kind="Method", qualified_name="A")
    b = await insert_node(db_ready, channel_id="ch-A", node_kind="Method", qualified_name="B")
    c = await insert_node(db_ready, channel_id="ch-B", node_kind="Method", qualified_name="C")
    await insert_edge(db_ready, src_id=a, dst_id=b, edge_kind="CALLS")

    count = await delete_channel_graph(db_ready, "ch-A")
    assert count == 2

    # ch-B нетронут
    assert await count_nodes(db_ready, "ch-A") == 0
    assert await count_nodes(db_ready, "ch-B") == 1
    # Edges канала ch-A тоже удалены
    assert await count_edges(db_ready) == 0


@pytest.mark.asyncio
async def test_delete_channel_graph_unknown_returns_zero(db_ready):
    count = await delete_channel_graph(db_ready, "no-such-channel")
    assert count == 0


# ---------- Enum coverage ----------


def test_node_kind_enum_values():
    assert NodeKind.MODULE.value == "Module"
    assert NodeKind.METHOD.value == "Method"
    assert NodeKind.METADATA_OBJECT.value == "MetadataObject"


def test_edge_kind_enum_values():
    assert EdgeKind.CALLS.value == "CALLS"
    assert EdgeKind.CONTAINS.value == "CONTAINS"
    assert EdgeKind.USES.value == "USES"


def test_traversal_hit_dataclass():
    """TraversalHit — frozen, equal by value."""
    n = GraphNode(
        id=1, channel_id="c", node_kind="Method", qualified_name="X",
        source_path=None, attributes={},
    )
    h1 = TraversalHit(node=n, depth=2, path_kinds=("CALLS", "USES"))
    h2 = TraversalHit(node=n, depth=2, path_kinds=("CALLS", "USES"))
    assert h1 == h2


def test_graph_node_to_dict():
    n = GraphNode(
        id=1, channel_id="c", node_kind="Method", qualified_name="X",
        source_path="p", attributes={"a": 1},
    )
    d = n.to_dict()
    assert d == {
        "id": 1,
        "channel_id": "c",
        "node_kind": "Method",
        "qualified_name": "X",
        "source_path": "p",
        "attributes": {"a": 1},
    }


def test_graph_edge_to_dict():
    e = GraphEdge(id=1, src_id=1, dst_id=2, edge_kind="CALLS", attributes={})
    d = e.to_dict()
    assert d["edge_kind"] == "CALLS"
    assert d["src_id"] == 1
