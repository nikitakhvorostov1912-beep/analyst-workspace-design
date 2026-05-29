"""Tests for _build_role_rls_edges (M-K3.17.2 R2) — Role-узлы + RESTRICTS-рёбра."""

from __future__ import annotations

import aiosqlite
import pytest

from app.knowledge.graph_storage import (
    EdgeKind,
    NodeKind,
    find_node,
    get_edges_from,
    insert_node,
)
from app.knowledge.typical.graph_builder import (
    GraphBuildStats,
    _build_role_rls_edges,
    _ConfigIndex,
)
from app.knowledge.typical.xml_models import (
    MetadataConfiguration,
    MetadataKind,
    MetadataObject,
)
from app.storage.migrations import apply_migrations

# Document.ОПП — Read с RLS-условием (→ ребро), Update без условия (→ нет ребра).
# Catalog.Контрагенты — Read без условия (→ нет ребра).
RIGHTS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Rights xmlns="http://v8.1c.ru/8.2/roles" version="2.20">
  <object>
    <name>Document.ОПП</name>
    <right>
      <name>Read</name>
      <value>true</value>
      <restrictionByCondition>
        <condition>ВладелецДокумента = &amp;ТекущийПользователь</condition>
      </restrictionByCondition>
    </right>
    <right><name>Update</name><value>true</value></right>
  </object>
  <object>
    <name>Catalog.Контрагенты</name>
    <right><name>Read</name><value>true</value></right>
  </object>
</Rights>
"""


@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON")
    await apply_migrations(conn)
    yield conn
    await conn.close()


def _role_config(role_name: str) -> MetadataConfiguration:
    return MetadataConfiguration(
        name="X",
        metadata_objects=(MetadataObject(name=role_name, kind=MetadataKind.ROLE.value),),
    )


@pytest.mark.asyncio
async def test_build_role_rls_edges_creates_role_and_restricts(tmp_path, db):
    doc_id = await insert_node(
        db, channel_id="_t", node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="Document.ОПП",
    )
    cat_id = await insert_node(
        db, channel_id="_t", node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="Catalog.Контрагенты",
    )
    index = _ConfigIndex(
        metadata_by_qname={"Document.ОПП": doc_id, "Catalog.Контрагенты": cat_id}
    )
    ext = tmp_path / "Roles" / "МенеджерПродаж" / "Ext"
    ext.mkdir(parents=True)
    (ext / "Rights.xml").write_text(RIGHTS_XML, encoding="utf-8")

    stats = GraphBuildStats()
    await _build_role_rls_edges(
        db, channel_id="_t", config=_role_config("МенеджерПродаж"),
        snapshot_root=tmp_path, index=index, stats=stats,
    )

    role = await find_node(
        db, channel_id="_t", qualified_name="Role.МенеджерПродаж",
        node_kind=NodeKind.ROLE.value,
    )
    assert role is not None
    edges = await get_edges_from(db, role.id, edge_kind=EdgeKind.RESTRICTS.value)
    # Только Read-с-условием на Document.ОПП. Update (без условия) и
    # Catalog.Контрагенты (без условия) рёбер НЕ дают.
    assert len(edges) == 1
    assert edges[0].dst_id == doc_id
    assert edges[0].attributes["right"] == "Read"
    assert edges[0].attributes["condition"] == "ВладелецДокумента = &ТекущийПользователь"
    assert stats.by_edge_kind.get("RESTRICTS") == 1
    assert stats.by_node_kind.get("Role") == 1


@pytest.mark.asyncio
async def test_build_role_rls_edges_no_rights_file(tmp_path, db):
    """Роль без Rights.xml → ничего не падает, рёбер нет."""
    stats = GraphBuildStats()
    await _build_role_rls_edges(
        db, channel_id="_t", config=_role_config("ПустаяРоль"),
        snapshot_root=tmp_path, index=_ConfigIndex(), stats=stats,
    )
    assert stats.edges_inserted == 0
    assert stats.nodes_inserted == 0


@pytest.mark.asyncio
async def test_build_role_rls_edges_skips_target_not_in_index(tmp_path, db):
    """Если объект RLS-условия не в индексе графа — ребро пропускается (без падения)."""
    ext = tmp_path / "Roles" / "Роль" / "Ext"
    ext.mkdir(parents=True)
    (ext / "Rights.xml").write_text(RIGHTS_XML, encoding="utf-8")

    stats = GraphBuildStats()
    await _build_role_rls_edges(
        db, channel_id="_t", config=_role_config("Роль"),
        snapshot_root=tmp_path, index=_ConfigIndex(),  # пустой индекс
        stats=stats,
    )
    # Role-узел создаётся (есть restricted right), но ребро не создаётся (нет target).
    assert stats.by_node_kind.get("Role") == 1
    assert stats.edges_inserted == 0
