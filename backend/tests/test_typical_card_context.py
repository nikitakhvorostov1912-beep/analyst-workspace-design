"""Тесты для card_context (M-K2.5.5)."""

from __future__ import annotations

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.graph_storage import insert_edge, insert_node, EdgeKind, NodeKind
from app.knowledge.typical.card_context import (
    CardContext,
    CardContextAttribute,
    CardContextMethod,
    CardContextRegisterRead,
    CardContextTabularSection,
    MAX_ATTRIBUTES,
    MAX_TOP_CALLS,
    _HANDLER_METHOD_NAMES,
    build_card_context,
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


# ─── CardContext models ──────────────────────────────────────────────


class TestCardContextAttribute:
    def test_to_dict(self):
        a = CardContextAttribute(
            name="Контрагент",
            type_definition="СправочникСсылка.Контрагенты",
            indexed=True,
            references=("Catalog.Контрагенты",),
        )
        d = a.to_dict()
        assert d["name"] == "Контрагент"
        assert d["indexed"] is True
        assert d["references"] == ["Catalog.Контрагенты"]


class TestCardContext:
    def test_to_compact_json(self):
        ctx = CardContext(
            object_qualified_name="Document.X",
            object_kind="Document",
            object_name="X",
            object_uuid=None,
            object_comment="",
            object_source_path=None,
        )
        j = ctx.to_compact_json()
        assert "Document.X" in j
        assert "\\n" not in j  # компактный, без перевода строк
        assert isinstance(ctx.compute_source_hash(), str)
        assert len(ctx.compute_source_hash()) == 64  # SHA-256

    def test_source_hash_deterministic(self):
        ctx1 = CardContext(
            object_qualified_name="Document.X",
            object_kind="Document",
            object_name="X",
            object_uuid=None,
            object_comment="",
            object_source_path=None,
        )
        ctx2 = CardContext(
            object_qualified_name="Document.X",
            object_kind="Document",
            object_name="X",
            object_uuid=None,
            object_comment="",
            object_source_path=None,
        )
        assert ctx1.compute_source_hash() == ctx2.compute_source_hash()

    def test_source_hash_changes_on_different_data(self):
        ctx1 = CardContext(
            object_qualified_name="Document.X",
            object_kind="Document",
            object_name="X",
            object_uuid=None,
            object_comment="",
            object_source_path=None,
        )
        ctx2 = CardContext(
            object_qualified_name="Document.Y",
            object_kind="Document",
            object_name="Y",
            object_uuid=None,
            object_comment="",
            object_source_path=None,
        )
        assert ctx1.compute_source_hash() != ctx2.compute_source_hash()


class TestHandlerMethodNames:
    def test_known_handlers_present(self):
        assert "ОбработкаПроведения" in _HANDLER_METHOD_NAMES
        assert "ПередЗаписью" in _HANDLER_METHOD_NAMES
        assert "ПриСозданииНаСервере" in _HANDLER_METHOD_NAMES
        # English варианты тоже
        assert "Posting" in _HANDLER_METHOD_NAMES


# ─── build_card_context на синтетическом графе ────────────────────────


async def _seed_graph(db: aiosqlite.Connection, channel_id: str = "_t_"):
    """Создаёт синтетический граф: документ Заказ с реквизитом, ТЧ,
    модулем и методом ОбработкаПроведения который пишет в регистр."""
    # MetadataObject Document.Заказ
    doc_id = await insert_node(
        db, channel_id=channel_id, node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="Document.Заказ", source_path="Documents/Заказ.xml",
        attributes={"name": "Заказ", "kind": "Document", "comment": "Документ заказа"},
    )
    # Catalog target — Справочник.Контрагенты
    cat_id = await insert_node(
        db, channel_id=channel_id, node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="Catalog.Контрагенты",
        attributes={"name": "Контрагенты", "kind": "Catalog"},
    )
    # Register target
    reg_id = await insert_node(
        db, channel_id=channel_id, node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name="AccumulationRegister.ТоварыНаСкладах",
        attributes={"name": "ТоварыНаСкладах", "kind": "AccumulationRegister"},
    )
    # Атрибут «Контрагент»
    attr_id = await insert_node(
        db, channel_id=channel_id, node_kind=NodeKind.ATTRIBUTE.value,
        qualified_name="Document.Заказ.Реквизит.Контрагент",
        attributes={"name": "Контрагент", "type_definition": "СправочникСсылка.Контрагенты", "fill_check": True},
    )
    await insert_edge(db, src_id=doc_id, dst_id=attr_id, edge_kind=EdgeKind.CONTAINS.value)
    await insert_edge(db, src_id=attr_id, dst_id=cat_id, edge_kind=EdgeKind.REFERENCES.value)

    # ТЧ Товары с реквизитом Количество
    ts_id = await insert_node(
        db, channel_id=channel_id, node_kind=NodeKind.TABULAR_SECTION.value,
        qualified_name="Document.Заказ.ТабличнаяЧасть.Товары",
        attributes={"name": "Товары"},
    )
    await insert_edge(db, src_id=doc_id, dst_id=ts_id, edge_kind=EdgeKind.CONTAINS.value)
    ts_attr_id = await insert_node(
        db, channel_id=channel_id, node_kind=NodeKind.ATTRIBUTE.value,
        qualified_name="Document.Заказ.ТабличнаяЧасть.Товары.Реквизит.Количество",
        attributes={"name": "Количество", "type_definition": "Число"},
    )
    await insert_edge(db, src_id=ts_id, dst_id=ts_attr_id, edge_kind=EdgeKind.CONTAINS.value)

    # Модуль ObjectModule + метод ОбработкаПроведения
    mod_id = await insert_node(
        db, channel_id=channel_id, node_kind=NodeKind.MODULE.value,
        qualified_name="Document.Заказ.ObjectModule",
        attributes={"module_kind": "ObjectModule"},
    )
    await insert_edge(db, src_id=doc_id, dst_id=mod_id, edge_kind=EdgeKind.CONTAINS.value)

    method_id = await insert_node(
        db, channel_id=channel_id, node_kind=NodeKind.METHOD.value,
        qualified_name="Document.Заказ.ObjectModule.ОбработкаПроведения",
        attributes={"name": "ОбработкаПроведения", "is_exported": False},
    )
    await insert_edge(db, src_id=mod_id, dst_id=method_id, edge_kind=EdgeKind.CONTAINS.value)

    # Метод пишет в регистр
    await insert_edge(db, src_id=method_id, dst_id=reg_id, edge_kind=EdgeKind.WRITES_TO.value)
    # Читает из регистра (виртуальная таблица Остатки)
    await insert_edge(
        db, src_id=method_id, dst_id=reg_id,
        edge_kind=EdgeKind.READS_FROM.value,
        attributes={"via": "virtual_table", "virtual_kind": "Остатки"},
    )

    return doc_id


@pytest.mark.asyncio
async def test_build_context_for_missing_object_returns_none(db_ready):
    ctx = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Document.NotExist",
    )
    assert ctx is None


@pytest.mark.asyncio
async def test_build_context_basic_object(db_ready):
    await _seed_graph(db_ready)
    ctx = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Document.Заказ",
    )
    assert ctx is not None
    assert ctx.object_name == "Заказ"
    assert ctx.object_kind == "Document"
    assert ctx.object_comment == "Документ заказа"


@pytest.mark.asyncio
async def test_build_context_collects_attributes(db_ready):
    await _seed_graph(db_ready)
    ctx = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Document.Заказ",
    )
    assert len(ctx.attributes) == 1
    attr = ctx.attributes[0]
    assert attr.name == "Контрагент"
    assert attr.references == ("Catalog.Контрагенты",)
    assert attr.fill_check is True


@pytest.mark.asyncio
async def test_build_context_collects_tabular_sections(db_ready):
    await _seed_graph(db_ready)
    ctx = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Document.Заказ",
    )
    assert len(ctx.tabular_sections) == 1
    ts = ctx.tabular_sections[0]
    assert ts.name == "Товары"
    assert len(ts.attributes) == 1
    assert ts.attributes[0].name == "Количество"


@pytest.mark.asyncio
async def test_build_context_collects_methods_with_handler_flag(db_ready):
    await _seed_graph(db_ready)
    ctx = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Document.Заказ",
    )
    assert len(ctx.methods) == 1
    m = ctx.methods[0]
    assert m.name == "ОбработкаПроведения"
    assert m.is_handler is True


@pytest.mark.asyncio
async def test_build_context_writes_to(db_ready):
    await _seed_graph(db_ready)
    ctx = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Document.Заказ",
    )
    assert ctx.writes_to == ("AccumulationRegister.ТоварыНаСкладах",)


@pytest.mark.asyncio
async def test_build_context_reads_from_with_virtual_kind(db_ready):
    await _seed_graph(db_ready)
    ctx = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Document.Заказ",
    )
    assert len(ctx.reads_from) == 1
    rf = ctx.reads_from[0]
    assert rf.register_qname == "AccumulationRegister.ТоварыНаСкладах"
    assert rf.via == "virtual_table"
    assert rf.virtual_kind == "Остатки"


@pytest.mark.asyncio
async def test_build_context_for_catalog_referenced_by(db_ready):
    """Catalog.Контрагенты должен видеть Document.Заказ в referenced_by."""
    await _seed_graph(db_ready)
    ctx = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Catalog.Контрагенты",
    )
    assert ctx is not None
    # Catalog ссылку получает от атрибута документа
    assert "Document.Заказ.Реквизит.Контрагент" in ctx.referenced_by


@pytest.mark.asyncio
async def test_build_context_top_calls_aggregation(db_ready):
    """top_calls собирает CALLS со всех методов объекта."""
    await _seed_graph(db_ready)

    # Добавим второй метод который вызывает первый
    mod_id = (await (
        await db_ready.execute(
            "SELECT id FROM graph_nodes WHERE channel_id=? AND qualified_name=?",
            ("_t_", "Document.Заказ.ObjectModule"),
        )
    ).fetchone())[0]

    helper_id = await insert_node(
        db_ready, channel_id="_t_", node_kind=NodeKind.METHOD.value,
        qualified_name="CommonModule.X.CommonModuleBody.Хелпер",
    )
    second_method_id = await insert_node(
        db_ready, channel_id="_t_", node_kind=NodeKind.METHOD.value,
        qualified_name="Document.Заказ.ObjectModule.Второй",
        attributes={"name": "Второй"},
    )
    await insert_edge(db_ready, src_id=mod_id, dst_id=second_method_id, edge_kind=EdgeKind.CONTAINS.value)
    await insert_edge(db_ready, src_id=second_method_id, dst_id=helper_id, edge_kind=EdgeKind.CALLS.value)

    ctx = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Document.Заказ",
    )
    assert "CommonModule.X.CommonModuleBody.Хелпер" in ctx.top_calls


@pytest.mark.asyncio
async def test_build_context_idempotent_hash(db_ready):
    """Два build_card_context подряд дают одинаковый hash."""
    await _seed_graph(db_ready)
    ctx1 = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Document.Заказ",
    )
    ctx2 = await build_card_context(
        db_ready, channel_id="_t_", object_qualified_name="Document.Заказ",
    )
    assert ctx1.compute_source_hash() == ctx2.compute_source_hash()
