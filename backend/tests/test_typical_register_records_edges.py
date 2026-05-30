"""Tests for _build_register_records_edges (Phase F) — WRITES_TO Document→Register.

Источник — `<RegisterRecords>` метаданных документа («Регистры движений»).
Это полный/точный перечень регистров движений, в отличие от BSL-эвристики
`Движения.X`, пропускавшей recordset-паттерн (флагман ТоварыНаСкладах = 0).
"""

from __future__ import annotations

import aiosqlite
import pytest

from app.knowledge.graph_storage import (
    EdgeKind,
    NodeKind,
    get_edges_from,
    insert_node,
)
from app.knowledge.typical.graph_builder import (
    GraphBuildStats,
    _build_register_records_edges,
    _ConfigIndex,
)
from app.knowledge.typical.xml_models import (
    MetadataConfiguration,
    MetadataKind,
    MetadataObject,
)
from app.storage.migrations import apply_migrations

_DOC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"
    xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Document uuid="x">
    <Properties>
      <Name>РеализацияТоваровУслуг</Name>
      <RegisterRecords>
        <xr:Item xsi:type="xr:MDObjectRef">AccumulationRegister.ТоварыНаСкладах</xr:Item>
        <xr:Item xsi:type="xr:MDObjectRef">AccumulationRegister.СебестоимостьТоваров</xr:Item>
      </RegisterRecords>
    </Properties>
  </Document>
</MetaDataObject>
"""


@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON")
    await apply_migrations(conn)
    yield conn
    await conn.close()


def _doc_config(doc_name: str) -> MetadataConfiguration:
    return MetadataConfiguration(
        name="X",
        metadata_objects=(
            MetadataObject(name=doc_name, kind=MetadataKind.DOCUMENT.value),
        ),
    )


@pytest.mark.asyncio
async def test_register_records_emits_document_to_register_writes(tmp_path, db):
    doc_id = await insert_node(
        db, channel_id="_t", node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="Document.РеализацияТоваровУслуг",
    )
    reg1 = await insert_node(
        db, channel_id="_t", node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="AccumulationRegister.ТоварыНаСкладах",
    )
    reg2 = await insert_node(
        db, channel_id="_t", node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="AccumulationRegister.СебестоимостьТоваров",
    )
    index = _ConfigIndex(metadata_by_qname={
        "Document.РеализацияТоваровУслуг": doc_id,
        "AccumulationRegister.ТоварыНаСкладах": reg1,
        "AccumulationRegister.СебестоимостьТоваров": reg2,
    })
    _write_doc_xml(tmp_path, "РеализацияТоваровУслуг", _DOC_XML)

    stats = GraphBuildStats()
    await _build_register_records_edges(
        db, channel_id="_t", config=_doc_config("РеализацияТоваровУслуг"),
        snapshot_root=tmp_path, index=index, stats=stats,
    )

    edges = await get_edges_from(db, doc_id, edge_kind=EdgeKind.WRITES_TO.value)
    targets = {e.dst_id for e in edges}
    assert targets == {reg1, reg2}
    assert all(e.attributes.get("resolution") == "register_records" for e in edges)
    assert stats.by_edge_kind.get(EdgeKind.WRITES_TO.value) == 2


@pytest.mark.asyncio
async def test_register_records_skips_register_not_in_index(tmp_path, db):
    """Регистр из RegisterRecords, которого нет в индексе → ребро пропущено."""
    doc_id = await insert_node(
        db, channel_id="_t", node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="Document.РеализацияТоваровУслуг",
    )
    # В индексе только документ, регистров нет.
    index = _ConfigIndex(metadata_by_qname={"Document.РеализацияТоваровУслуг": doc_id})
    _write_doc_xml(tmp_path, "РеализацияТоваровУслуг", _DOC_XML)

    stats = GraphBuildStats()
    await _build_register_records_edges(
        db, channel_id="_t", config=_doc_config("РеализацияТоваровУслуг"),
        snapshot_root=tmp_path, index=index, stats=stats,
    )
    edges = await get_edges_from(db, doc_id, edge_kind=EdgeKind.WRITES_TO.value)
    assert edges == []


@pytest.mark.asyncio
async def test_register_records_no_xml_file_noop(tmp_path, db):
    """Документ без XML-файла → не падает, рёбер нет."""
    doc_id = await insert_node(
        db, channel_id="_t", node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="Document.БезФайла",
    )
    index = _ConfigIndex(metadata_by_qname={"Document.БезФайла": doc_id})
    stats = GraphBuildStats()
    await _build_register_records_edges(
        db, channel_id="_t", config=_doc_config("БезФайла"),
        snapshot_root=tmp_path, index=index, stats=stats,
    )
    assert stats.edges_inserted == 0


def _write_doc_xml(tmp_path, name: str, content: str) -> None:
    docs = tmp_path / "Documents"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / f"{name}.xml").write_text(content, encoding="utf-8")
