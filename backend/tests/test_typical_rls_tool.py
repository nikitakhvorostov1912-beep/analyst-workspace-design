"""Tests for explain_rls_restrictions tool (M-K3.17.2 R3 — RLS-tracer UC)."""

from __future__ import annotations

import aiosqlite
import pytest

from app.knowledge.graph_storage import insert_edge, insert_node
from app.knowledge.typical.tool import dispatch_typical_tool, is_typical_tool
from app.storage.migrations import apply_migrations

_COND = "ВладелецДокумента = &ТекущийПользователь"


@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON")
    await apply_migrations(conn)
    yield conn
    await conn.close()


def test_is_typical_tool_includes_explain_rls():
    assert is_typical_tool("explain_rls_restrictions")


@pytest.mark.asyncio
async def test_explain_rls_returns_restrictions(db):
    doc = await insert_node(
        db, channel_id="_t", node_kind="MetadataObject", qualified_name="Document.ОПП"
    )
    role = await insert_node(
        db, channel_id="_t", node_kind="Role", qualified_name="Role.МенеджерПродаж"
    )
    await insert_edge(
        db, src_id=role, dst_id=doc, edge_kind="RESTRICTS",
        attributes={"right": "Read", "condition": _COND},
    )

    ok, result, err = await dispatch_typical_tool(
        db, "explain_rls_restrictions",
        {"channel_id": "_t", "object_qualified_name": "Document.ОПП"},
    )
    assert ok is True and err is None
    assert result["object"] == "Document.ОПП"
    assert result["total"] == 1
    r = result["restrictions"][0]
    assert r["role"] == "Role.МенеджерПродаж"
    assert r["right"] == "Read"
    assert r["condition"] == _COND
    assert "note" in result


@pytest.mark.asyncio
async def test_explain_rls_no_restrictions(db):
    """Объект есть в графе, но RLS-ограничений нет → пустой список, ok."""
    await insert_node(
        db, channel_id="_t", node_kind="MetadataObject",
        qualified_name="Catalog.Валюты",
    )
    ok, result, err = await dispatch_typical_tool(
        db, "explain_rls_restrictions",
        {"channel_id": "_t", "object_qualified_name": "Catalog.Валюты"},
    )
    assert ok is True
    assert result["total"] == 0
    assert result["restrictions"] == []


@pytest.mark.asyncio
async def test_explain_rls_object_not_found(db):
    ok, result, err = await dispatch_typical_tool(
        db, "explain_rls_restrictions",
        {"channel_id": "_t", "object_qualified_name": "Document.НетТакого"},
    )
    assert ok is False
    assert err is not None and "не найден" in err
