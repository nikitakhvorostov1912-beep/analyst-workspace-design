"""Тесты для backend/app/knowledge/typical/graph_builder.py (Phase M-K2.5.4).

Покрытие:
- Регулярки: _REFERENCE_TYPE_RE / _USES_RE / _DVIZHENIYA_RE /
  _SAME_MODULE_CALL_RE / _CROSS_MODULE_CALL_RE / _BSL_KEYWORDS
- Phase B: структурные nodes + CONTAINS edges (через прямой вызов на
  in-memory aiosqlite + миграция v17)
- Phase C: REFERENCES edges из type_definition
- Phase D: CALLS/USES/WRITES_TO/READS_FROM из BSL телах методов
- End-to-end: build_typical_graph на синтетическом snapshot_root
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.graph_storage import (
    EdgeKind,
    NodeKind,
    count_edges,
    count_nodes,
    find_node,
    get_edges_from,
)
from app.knowledge.typical.bsl_models import (
    BSLMethod,
    BSLMethodKind,
    BSLModule,
)
from app.knowledge.typical.graph_builder import (
    _BSL_KEYWORDS,
    _CROSS_MODULE_CALL_RE,
    _DVIZHENIYA_RE,
    _REFERENCE_TYPE_RE,
    _SAME_MODULE_CALL_RE,
    _USES_RE,
    GraphBuildStats,
    _build_bsl_edges,
    _build_references_edges,
    _emit_method_behavior_edges,
    _insert_structural_nodes,
    build_typical_graph,
)
from app.knowledge.typical.xml_models import (
    MetadataAttribute,
    MetadataConfiguration,
    MetadataForm,
    MetadataKind,
    MetadataModule,
    MetadataObject,
    MetadataTabularSection,
    ModuleKind,
)
from app.storage.migrations import apply_migrations


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_ready():
    """In-memory SQLite с прим. миграции v17."""
    conn = await aiosqlite.connect(":memory:")
    try:
        await conn.execute("PRAGMA foreign_keys = ON")
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


def _make_config(
    *objects: MetadataObject, name: str = "TestConfig", version: str = "1.0.0"
) -> MetadataConfiguration:
    return MetadataConfiguration(
        name=name,
        version=version,
        metadata_objects=tuple(objects),
    )


def _doc(
    name: str,
    *,
    attributes: tuple[MetadataAttribute, ...] = (),
    tabular_sections: tuple[MetadataTabularSection, ...] = (),
    modules: tuple[MetadataModule, ...] = (),
) -> MetadataObject:
    return MetadataObject(
        name=name,
        kind=MetadataKind.DOCUMENT.value,
        source_path=f"Documents/{name}.xml",
        attributes=attributes,
        tabular_sections=tabular_sections,
        modules=modules,
    )


def _catalog(name: str, *, attributes: tuple[MetadataAttribute, ...] = ()) -> MetadataObject:
    return MetadataObject(
        name=name,
        kind=MetadataKind.CATALOG.value,
        source_path=f"Catalogs/{name}.xml",
        attributes=attributes,
    )


def _register(name: str, *, kind: MetadataKind = MetadataKind.ACCUMULATION_REGISTER) -> MetadataObject:
    return MetadataObject(
        name=name,
        kind=kind.value,
        source_path=f"{kind.value}s/{name}.xml",
    )


def _common_module(name: str, *, modules: tuple[MetadataModule, ...] = ()) -> MetadataObject:
    return MetadataObject(
        name=name,
        kind=MetadataKind.COMMON_MODULE.value,
        source_path=f"CommonModules/{name}.xml",
        modules=modules,
    )


def _method(
    name: str,
    body: str,
    *,
    line_start: int = 1,
    line_end: int = 1,
    is_exported: bool = False,
) -> BSLMethod:
    return BSLMethod(
        name=name,
        kind=BSLMethodKind.PROCEDURE.value,
        parameters=(),
        is_exported=is_exported,
        doc_comment=None,
        compile_directive=None,
        region=None,
        line_start=line_start,
        line_end=line_end,
        body_source=body,
    )


# ─── Regex unit tests ─────────────────────────────────────────────────


class TestReferenceTypeRegex:
    def test_catalog_ref(self):
        m = _REFERENCE_TYPE_RE.search("СправочникСсылка.Контрагенты")
        assert m is not None
        assert m.group(1) == "СправочникСсылка"
        assert m.group(2) == "Контрагенты"

    def test_document_ref(self):
        m = _REFERENCE_TYPE_RE.search("ДокументСсылка.РеализацияТоваровУслуг")
        assert m is not None
        assert m.group(2) == "РеализацияТоваровУслуг"

    def test_enum_ref(self):
        m = _REFERENCE_TYPE_RE.search("ПеречислениеСсылка.ВидыКонтрагентов")
        assert m is not None
        assert m.group(1) == "ПеречислениеСсылка"

    def test_chart_of_accounts(self):
        m = _REFERENCE_TYPE_RE.search("ПланСчетовСсылка.Хозрасчетный")
        assert m is not None
        assert m.group(2) == "Хозрасчетный"

    def test_english_catalog_ref(self):
        m = _REFERENCE_TYPE_RE.search("CatalogRef.Counterparties")
        assert m is not None
        assert m.group(1) == "CatalogRef"

    def test_no_match_for_plain_type(self):
        assert _REFERENCE_TYPE_RE.search("Строка") is None
        assert _REFERENCE_TYPE_RE.search("Число") is None
        assert _REFERENCE_TYPE_RE.search("Дата") is None

    def test_multiple_matches(self):
        text = "СправочникСсылка.Контрагенты, ДокументСсылка.Заказ"
        matches = list(_REFERENCE_TYPE_RE.finditer(text))
        assert len(matches) == 2


class TestUsesRegex:
    def test_documents_collection(self):
        m = _USES_RE.search("Документы.РеализацияТоваровУслуг")
        assert m is not None
        assert m.group(1) == "Документы"

    def test_catalogs_collection(self):
        m = _USES_RE.search("Справочники.Контрагенты.НайтиПоКоду")
        assert m is not None
        assert m.group(1) == "Справочники"
        assert m.group(2) == "Контрагенты"

    def test_accumulation_registers(self):
        m = _USES_RE.search("РегистрыНакопления.ТоварыНаСкладах.СоздатьНаборЗаписей()")
        assert m is not None
        assert m.group(1) == "РегистрыНакопления"
        assert m.group(2) == "ТоварыНаСкладах"

    def test_common_modules(self):
        m = _USES_RE.search("ОбщиеМодули.ОбщегоНазначения")
        assert m is not None

    def test_no_match_for_singular_form(self):
        # `Документ.X` без `ы` — это типизация, не коллекция → нет матча USES
        assert _USES_RE.search("Документ.РеализацияТоваровУслуг") is None
        # Но `Документ.X` в качестве table name работает в query parser отдельно.

    def test_english_collections(self):
        m = _USES_RE.search("Documents.Sales")
        assert m is not None


class TestDvizheniyaRegex:
    def test_basic(self):
        m = _DVIZHENIYA_RE.search("Движения.ТоварыНаСкладах.Записать()")
        assert m is not None
        assert m.group(1) == "ТоварыНаСкладах"

    def test_with_add(self):
        m = _DVIZHENIYA_RE.search("Движения.Взаиморасчеты.Добавить()")
        assert m is not None

    def test_no_match_for_dvizhenie_singular(self):
        # `Движение` (без `я` на конце) — это другое (одна запись регистра)
        assert _DVIZHENIYA_RE.search("Движение.ТоварыНаСкладах") is None

    def test_multiple(self):
        text = "Движения.X.Записать(); Движения.Y.Добавить()"
        matches = list(_DVIZHENIYA_RE.finditer(text))
        assert len(matches) == 2
        assert matches[0].group(1) == "X"
        assert matches[1].group(1) == "Y"


class TestSameModuleCallRegex:
    def test_finds_method_call(self):
        body = "    Результат = ВычислитьСумму(Параметр);"
        matches = list(_SAME_MODULE_CALL_RE.finditer(body))
        assert any(m.group(1) == "ВычислитьСумму" for m in matches)

    def test_does_not_match_attribute_call(self):
        # `Объект.ВычислитьСумму(...)` — это cross-module, не same-module
        body = "    Результат = Объект.ВычислитьСумму(Параметр);"
        names = [m.group(1) for m in _SAME_MODULE_CALL_RE.finditer(body)]
        assert "ВычислитьСумму" not in names

    def test_catches_keywords_filter_separately(self):
        # Регулярка ловит даже `Если(`, но keyword filter должен отсеять.
        body = "    Если Истина Тогда КонецЕсли;"
        matches = [m.group(1) for m in _SAME_MODULE_CALL_RE.finditer(body)]
        # Регулярка не ловит `Если` без `(` после
        # `Истина` тоже не ловит — нет скобки

    def test_camelcase_required(self):
        # Lowercase'ные имена (переменные) не ловятся
        body = "    переменная(Аргумент);"
        matches = [m.group(1) for m in _SAME_MODULE_CALL_RE.finditer(body)]
        assert "переменная" not in matches


class TestCrossModuleCallRegex:
    def test_finds_cross_call(self):
        body = "ОбщегоНазначения.ЗначениеРеквизитаОбъекта(Ссылка, \"ИНН\")"
        m = _CROSS_MODULE_CALL_RE.search(body)
        assert m is not None
        assert m.group(1) == "ОбщегоНазначения"
        assert m.group(2) == "ЗначениеРеквизитаОбъекта"

    def test_camelcase_required_for_module(self):
        # Lowercase'ные prefix не считаются модулями
        assert _CROSS_MODULE_CALL_RE.search("переменная.метод(а)") is None


class TestBSLKeywords:
    def test_basic_keywords_present(self):
        assert "Если" in _BSL_KEYWORDS
        assert "Цикл" in _BSL_KEYWORDS
        assert "Возврат" in _BSL_KEYWORDS
        assert "Истина" in _BSL_KEYWORDS

    def test_english_keywords_present(self):
        assert "If" in _BSL_KEYWORDS
        assert "Return" in _BSL_KEYWORDS

    def test_method_names_not_keywords(self):
        assert "МойМетод" not in _BSL_KEYWORDS
        assert "ОбщегоНазначения" not in _BSL_KEYWORDS


# ─── GraphBuildStats ───────────────────────────────────────────────────


class TestGraphBuildStats:
    def test_empty_stats(self):
        s = GraphBuildStats()
        assert s.nodes_inserted == 0
        assert s.edges_inserted == 0
        assert s.by_node_kind == {}

    def test_bump_node(self):
        s = GraphBuildStats()
        s._bump_node(NodeKind.METHOD.value)
        s._bump_node(NodeKind.METHOD.value)
        assert s.nodes_inserted == 2
        assert s.by_node_kind[NodeKind.METHOD.value] == 2

    def test_bump_edge(self):
        s = GraphBuildStats()
        s._bump_edge(EdgeKind.CALLS.value)
        s._bump_edge(EdgeKind.USES.value)
        assert s.edges_inserted == 2
        assert s.by_edge_kind == {EdgeKind.CALLS.value: 1, EdgeKind.USES.value: 1}

    def test_to_dict(self):
        s = GraphBuildStats()
        s._bump_node(NodeKind.METADATA_OBJECT.value)
        d = s.to_dict()
        assert d["nodes_inserted"] == 1
        assert d["by_node_kind"] == {NodeKind.METADATA_OBJECT.value: 1}
        assert "duration_seconds" in d


# ─── Phase B: структура (CONTAINS) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_structural_inserts_metadata_object(db_ready):
    config = _make_config(_doc("Заказ"))
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    assert "Document.Заказ" in index.metadata_by_qname
    assert stats.by_node_kind[NodeKind.METADATA_OBJECT.value] == 1


@pytest.mark.asyncio
async def test_structural_inserts_attributes_with_contains(db_ready):
    doc = _doc(
        "Заказ",
        attributes=(
            MetadataAttribute(name="Контрагент", type_definition="СправочникСсылка.Контрагенты"),
            MetadataAttribute(name="Сумма", type_definition="Число", length=15, precision=2),
        ),
    )
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=_make_config(doc), stats=stats, progress_callback=None,
    )
    assert stats.by_node_kind[NodeKind.ATTRIBUTE.value] == 2
    # CONTAINS: doc → attr × 2
    assert stats.by_edge_kind[EdgeKind.CONTAINS.value] == 2
    assert "Document.Заказ.Реквизит.Контрагент" in index.metadata_by_qname


@pytest.mark.asyncio
async def test_structural_inserts_tabular_section_with_nested_attrs(db_ready):
    ts = MetadataTabularSection(
        name="Товары",
        attributes=(
            MetadataAttribute(name="Номенклатура", type_definition="СправочникСсылка.Номенклатура"),
            MetadataAttribute(name="Количество", type_definition="Число"),
        ),
    )
    doc = _doc("Заказ", tabular_sections=(ts,))
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=_make_config(doc), stats=stats, progress_callback=None,
    )
    assert stats.by_node_kind[NodeKind.TABULAR_SECTION.value] == 1
    assert stats.by_node_kind[NodeKind.ATTRIBUTE.value] == 2
    # CONTAINS: doc→ts, ts→attr×2
    assert stats.by_edge_kind[EdgeKind.CONTAINS.value] == 3
    assert "Document.Заказ.ТабличнаяЧасть.Товары.Реквизит.Номенклатура" in index.metadata_by_qname


@pytest.mark.asyncio
async def test_structural_inserts_modules_with_contains(db_ready):
    doc = _doc(
        "Заказ",
        modules=(
            MetadataModule(kind=ModuleKind.OBJECT_MODULE.value, relative_path="Documents/Заказ/Ext/ObjectModule.bsl"),
            MetadataModule(kind=ModuleKind.MANAGER_MODULE.value, relative_path="Documents/Заказ/Ext/ManagerModule.bsl"),
        ),
    )
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=_make_config(doc), stats=stats, progress_callback=None,
    )
    assert stats.by_node_kind[NodeKind.MODULE.value] == 2
    assert "Document.Заказ.ObjectModule" in index.metadata_by_qname
    assert "Document.Заказ.ManagerModule" in index.metadata_by_qname


@pytest.mark.asyncio
async def test_structural_index_register_short_names(db_ready):
    reg_a = _register("ТоварыНаСкладах", kind=MetadataKind.ACCUMULATION_REGISTER)
    reg_b = _register("ЦеныНоменклатуры", kind=MetadataKind.INFORMATION_REGISTER)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=_make_config(reg_a, reg_b), stats=stats, progress_callback=None,
    )
    assert index.register_short_to_qname["ТоварыНаСкладах"] == "AccumulationRegister.ТоварыНаСкладах"
    assert index.register_short_to_qname["ЦеныНоменклатуры"] == "InformationRegister.ЦеныНоменклатуры"
    assert index.register_short_conflicts == []


@pytest.mark.asyncio
async def test_structural_register_short_name_collision(db_ready):
    # Один и тот же short_name в двух разных видах регистров
    reg_a = _register("Курсы", kind=MetadataKind.ACCUMULATION_REGISTER)
    reg_b = _register("Курсы", kind=MetadataKind.INFORMATION_REGISTER)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=_make_config(reg_a, reg_b), stats=stats, progress_callback=None,
    )
    assert "Курсы" in index.register_short_conflicts
    # Первый встреченный
    assert index.register_short_to_qname["Курсы"] == "AccumulationRegister.Курсы"


@pytest.mark.asyncio
async def test_structural_common_module_index(db_ready):
    cm = _common_module(
        "ОбщегоНазначения",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/ОбщегоНазначения/Ext/Module.bsl"),),
    )
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=_make_config(cm), stats=stats, progress_callback=None,
    )
    assert "ОбщегоНазначения" in index.common_module_body_module


# ─── Phase C: REFERENCES edges ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_references_from_type_definition(db_ready):
    catalog = _catalog("Контрагенты")
    doc = _doc(
        "Заказ",
        attributes=(
            MetadataAttribute(name="Контрагент", type_definition="СправочникСсылка.Контрагенты"),
        ),
    )
    config = _make_config(catalog, doc)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    await _build_references_edges(
        db_ready, channel_id="_test_", config=config, index=index, stats=stats, progress_callback=None,
    )
    assert stats.by_edge_kind.get(EdgeKind.REFERENCES.value, 0) == 1


@pytest.mark.asyncio
async def test_references_skips_unresolved_target(db_ready):
    # Тип ссылается на справочник `Контрагенты`, но самого справочника нет
    # в конфигурации → edge не создаётся
    doc = _doc(
        "Заказ",
        attributes=(
            MetadataAttribute(name="Контрагент", type_definition="СправочникСсылка.Контрагенты"),
        ),
    )
    config = _make_config(doc)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    await _build_references_edges(
        db_ready, channel_id="_test_", config=config, index=index, stats=stats, progress_callback=None,
    )
    assert stats.by_edge_kind.get(EdgeKind.REFERENCES.value, 0) == 0


@pytest.mark.asyncio
async def test_references_from_tabular_section_attribute(db_ready):
    catalog = _catalog("Номенклатура")
    ts = MetadataTabularSection(
        name="Товары",
        attributes=(
            MetadataAttribute(name="Номенклатура", type_definition="СправочникСсылка.Номенклатура"),
        ),
    )
    doc = _doc("Заказ", tabular_sections=(ts,))
    config = _make_config(catalog, doc)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    await _build_references_edges(
        db_ready, channel_id="_test_", config=config, index=index, stats=stats, progress_callback=None,
    )
    assert stats.by_edge_kind.get(EdgeKind.REFERENCES.value, 0) == 1


@pytest.mark.asyncio
async def test_references_dedup_within_attribute(db_ready):
    # Реквизит составной: один и тот же справочник упомянут дважды
    catalog = _catalog("Контрагенты")
    doc = _doc(
        "Заказ",
        attributes=(
            MetadataAttribute(
                name="Получатель",
                # Дублирование одного и того же ссылочного типа — частая в составных типах
                type_definition="СправочникСсылка.Контрагенты, СправочникСсылка.Контрагенты",
            ),
        ),
    )
    config = _make_config(catalog, doc)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    await _build_references_edges(
        db_ready, channel_id="_test_", config=config, index=index, stats=stats, progress_callback=None,
    )
    assert stats.by_edge_kind.get(EdgeKind.REFERENCES.value, 0) == 1


# ─── Phase D: BSL поведенческие edges ──────────────────────────────────


@pytest.mark.asyncio
async def test_emit_calls_same_module(db_ready):
    cm = _common_module(
        "ОбщегоНазначения",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/ОбщегоНазначения/Ext/Module.bsl"),),
    )
    config = _make_config(cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )

    # Имитируем 2 метода в одном модуле: ВнутреннийМетод вызывает Хелпер
    mod_qname = "CommonModule.ОбщегоНазначения.CommonModuleBody"
    mod_node_id = index.metadata_by_qname[mod_qname]
    from app.knowledge.graph_storage import insert_node as _ins_node

    helper_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name=f"{mod_qname}.Хелпер",
    )
    caller_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name=f"{mod_qname}.ВнутреннийМетод",
    )
    method_ids = {"Хелпер": helper_id, "ВнутреннийМетод": caller_id}

    method = _method("ВнутреннийМетод", "    Результат = Хелпер(Параметр);")
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=caller_id,
        method_node_ids_same_module=method_ids,
        common_module_names={"ОбщегоНазначения"}, index=index, stats=stats,
    )
    assert stats.by_edge_kind.get(EdgeKind.CALLS.value, 0) == 1


@pytest.mark.asyncio
async def test_emit_collects_cross_module_calls(db_ready):
    """Регресс 2026-05-29: cross-module вызовы `Модуль.Метод()` должны
    попадать в cross_calls. Раньше терялись → граф был ТОЛЬКО внутримодульным
    (impact-анализ давал ложное «ничего не сломается»)."""
    cm = _common_module(
        "ПроведениеДокументов",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/ПроведениеДокументов/Ext/Module.bsl"),),
    )
    config = _make_config(cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    from app.knowledge.graph_storage import insert_node as _ins_node

    caller_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name="Document.Реализация.ObjectModule.ОбработкаПроведения",
    )
    method = _method(
        "ОбработкаПроведения",
        "    ПроведениеДокументов.ОбработкаПроведенияДокумента(ЭтотОбъект, Отказ);",
    )
    cross_calls: list[tuple[int, str]] = []
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=caller_id,
        method_node_ids_same_module={"ОбработкаПроведения": caller_id},
        common_module_names={"ПроведениеДокументов"}, index=index, stats=stats,
        cross_calls=cross_calls,
    )
    assert cross_calls == [
        (caller_id, "CommonModule.ПроведениеДокументов.CommonModuleBody.ОбработкаПроведенияДокумента")
    ]


@pytest.mark.asyncio
async def test_emit_cross_module_without_collector_is_noop(db_ready):
    """Без cross_calls (optional) cross-module вызовы просто пропускаются, без падения."""
    cm = _common_module(
        "ПроведениеДокументов",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/ПроведениеДокументов/Ext/Module.bsl"),),
    )
    config = _make_config(cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    from app.knowledge.graph_storage import insert_node as _ins_node

    caller_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name="Document.Реализация.ObjectModule.М",
    )
    method = _method("М", "    ПроведениеДокументов.Метод();")
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=caller_id,
        method_node_ids_same_module={"М": caller_id},
        common_module_names={"ПроведениеДокументов"}, index=index, stats=stats,
    )  # cross_calls не передан → no-op, без исключений


@pytest.mark.asyncio
async def test_emit_collects_manager_calls(db_ready):
    """Phase 2: вызов метода менеджера `Документы.X.Метод()` -> ManagerModule.
    Раньше терялся (3-сегментный вызов вне CommonModule)."""
    cm = _common_module(
        "Х",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/Х/Ext/Module.bsl"),),
    )
    config = _make_config(cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    from app.knowledge.graph_storage import insert_node as _ins_node

    caller_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name="Document.Реализация.ObjectModule.ОбработкаПроведения",
    )
    method = _method(
        "ОбработкаПроведения",
        "    П = Документы.РеализацияТоваровУслуг.ПараметрыРегистрации(ЭтотОбъект);",
    )
    cross_calls: list[tuple[int, str]] = []
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=caller_id,
        method_node_ids_same_module={"ОбработкаПроведения": caller_id},
        common_module_names=set(), index=index, stats=stats, cross_calls=cross_calls,
    )
    assert cross_calls == [
        (caller_id, "Document.РеализацияТоваровУслуг.ManagerModule.ПараметрыРегистрации")
    ]


@pytest.mark.asyncio
async def test_emit_calls_keyword_filtered(db_ready):
    cm = _common_module(
        "Х",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/Х/Ext/Module.bsl"),),
    )
    config = _make_config(cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )

    mod_qname = "CommonModule.Х.CommonModuleBody"
    from app.knowledge.graph_storage import insert_node as _ins_node
    caller_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name=f"{mod_qname}.А",
    )
    method = _method("А", "Если Истина Тогда КонецЕсли;")  # ключевых слов нет с (
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=caller_id,
        method_node_ids_same_module={"А": caller_id}, common_module_names=set(),
        index=index, stats=stats,
    )
    assert stats.by_edge_kind.get(EdgeKind.CALLS.value, 0) == 0


@pytest.mark.asyncio
async def test_emit_uses_documents_collection(db_ready):
    doc_target = _doc("РеализацияТоваровУслуг")
    cm = _common_module(
        "Утилиты",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/Утилиты/Ext/Module.bsl"),),
    )
    config = _make_config(doc_target, cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )

    mod_qname = "CommonModule.Утилиты.CommonModuleBody"
    from app.knowledge.graph_storage import insert_node as _ins_node
    method_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name=f"{mod_qname}.Метод",
    )
    method = _method("Метод", "Заказ = Документы.РеализацияТоваровУслуг.СоздатьДокумент();")
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=method_id,
        method_node_ids_same_module={"Метод": method_id}, common_module_names=set(),
        index=index, stats=stats,
    )
    assert stats.by_edge_kind.get(EdgeKind.USES.value, 0) == 1


@pytest.mark.asyncio
async def test_emit_writes_to_register(db_ready):
    reg = _register("ТоварыНаСкладах", kind=MetadataKind.ACCUMULATION_REGISTER)
    cm = _common_module(
        "М",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/М/Ext/Module.bsl"),),
    )
    config = _make_config(reg, cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    mod_qname = "CommonModule.М.CommonModuleBody"
    from app.knowledge.graph_storage import insert_node as _ins_node
    method_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name=f"{mod_qname}.Поведение",
    )
    method = _method("Поведение", "    Движения.ТоварыНаСкладах.Записать();")
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=method_id,
        method_node_ids_same_module={"Поведение": method_id}, common_module_names=set(),
        index=index, stats=stats,
    )
    assert stats.by_edge_kind.get(EdgeKind.WRITES_TO.value, 0) == 1


@pytest.mark.asyncio
async def test_emit_writes_to_unknown_register_skipped(db_ready):
    cm = _common_module(
        "М",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/М/Ext/Module.bsl"),),
    )
    config = _make_config(cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    mod_qname = "CommonModule.М.CommonModuleBody"
    from app.knowledge.graph_storage import insert_node as _ins_node
    method_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name=f"{mod_qname}.Поведение",
    )
    method = _method("Поведение", "    Движения.НесуществующийРегистр.Записать();")
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=method_id,
        method_node_ids_same_module={"Поведение": method_id}, common_module_names=set(),
        index=index, stats=stats,
    )
    assert stats.by_edge_kind.get(EdgeKind.WRITES_TO.value, 0) == 0


@pytest.mark.asyncio
async def test_emit_reads_from_physical_table(db_ready):
    doc_target = _doc("Заказ")
    cm = _common_module(
        "Q",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/Q/Ext/Module.bsl"),),
    )
    config = _make_config(doc_target, cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    mod_qname = "CommonModule.Q.CommonModuleBody"
    from app.knowledge.graph_storage import insert_node as _ins_node
    method_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name=f"{mod_qname}.Отчет",
    )
    body = """
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ Ссылка ИЗ Документ.Заказ КАК З ГДЕ З.Проведен = Истина";
    """
    method = _method("Отчет", body)
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=method_id,
        method_node_ids_same_module={"Отчет": method_id}, common_module_names=set(),
        index=index, stats=stats,
    )
    assert stats.by_edge_kind.get(EdgeKind.READS_FROM.value, 0) == 1


@pytest.mark.asyncio
async def test_emit_reads_from_virtual_table(db_ready):
    reg = _register("ТоварыНаСкладах", kind=MetadataKind.ACCUMULATION_REGISTER)
    cm = _common_module(
        "Q",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/Q/Ext/Module.bsl"),),
    )
    config = _make_config(reg, cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    mod_qname = "CommonModule.Q.CommonModuleBody"
    from app.knowledge.graph_storage import insert_node as _ins_node
    method_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name=f"{mod_qname}.Отчет",
    )
    body = """
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ Количество ИЗ РегистрНакопления.ТоварыНаСкладах.Остатки() КАК Остатки";
    """
    method = _method("Отчет", body)
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=method_id,
        method_node_ids_same_module={"Отчет": method_id}, common_module_names=set(),
        index=index, stats=stats,
    )
    assert stats.by_edge_kind.get(EdgeKind.READS_FROM.value, 0) == 1
    # Проверим что edge имеет attributes.via=virtual_table
    edges = await get_edges_from(db_ready, method_id, edge_kind=EdgeKind.READS_FROM.value)
    assert len(edges) == 1
    assert edges[0].attributes.get("via") == "virtual_table"
    assert edges[0].attributes.get("virtual_kind") == "Остатки"


@pytest.mark.asyncio
async def test_emit_dedups_within_method(db_ready):
    # В одном теле метода тот же CALLS встречается дважды → 1 edge
    cm = _common_module(
        "Х",
        modules=(MetadataModule(kind=ModuleKind.COMMON_MODULE_BODY.value, relative_path="CommonModules/Х/Ext/Module.bsl"),),
    )
    config = _make_config(cm)
    stats = GraphBuildStats()
    index = await _insert_structural_nodes(
        db_ready, channel_id="_test_", config=config, stats=stats, progress_callback=None,
    )
    mod_qname = "CommonModule.Х.CommonModuleBody"
    from app.knowledge.graph_storage import insert_node as _ins_node
    helper_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name=f"{mod_qname}.Хелпер",
    )
    caller_id = await _ins_node(
        db_ready, channel_id="_test_", node_kind=NodeKind.METHOD.value,
        qualified_name=f"{mod_qname}.А",
    )
    method = _method("А", "Хелпер(); Хелпер(); Хелпер();")
    await _emit_method_behavior_edges(
        db_ready, channel_id="_test_", method=method, method_node_id=caller_id,
        method_node_ids_same_module={"Хелпер": helper_id, "А": caller_id},
        common_module_names=set(), index=index, stats=stats,
    )
    assert stats.by_edge_kind.get(EdgeKind.CALLS.value, 0) == 1


# ─── End-to-end build_typical_graph на синтетическом snapshot ─────────


def _write_synthetic_snapshot(tmp_path: Path) -> Path:
    """Создаёт минимальный snapshot_root с Configuration.xml + 1 документ + 1 модуль."""
    root = tmp_path / "snapshot"
    root.mkdir()

    (root / "Configuration.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">\n'
        '  <Configuration>\n'
        '    <Properties>\n'
        '      <Name>TestConfig</Name>\n'
        '      <Version>1.0.0</Version>\n'
        '    </Properties>\n'
        '    <ChildObjects>\n'
        '      <CommonModule>ОбщегоНазначения</CommonModule>\n'
        '    </ChildObjects>\n'
        '  </Configuration>\n'
        '</MetaDataObject>\n',
        encoding="utf-8",
    )

    cm_dir = root / "CommonModules" / "ОбщегоНазначения"
    cm_dir.mkdir(parents=True)
    (cm_dir.with_suffix(".xml")).write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">\n'
        '  <CommonModule>\n'
        '    <Properties>\n'
        '      <Name>ОбщегоНазначения</Name>\n'
        '    </Properties>\n'
        '  </CommonModule>\n'
        '</MetaDataObject>\n',
        encoding="utf-8",
    )

    ext = cm_dir / "Ext"
    ext.mkdir()
    (ext / "Module.bsl").write_text(
        "Процедура Хелпер()\n"
        "    Возврат;\n"
        "КонецПроцедуры\n"
        "\n"
        "Процедура Главная() Экспорт\n"
        "    Хелпер();\n"
        "КонецПроцедуры\n",
        encoding="utf-8",
    )
    return root


@pytest.mark.asyncio
async def test_build_typical_graph_end_to_end(db_ready, tmp_path):
    root = _write_synthetic_snapshot(tmp_path)
    stats = await build_typical_graph(
        db_ready, channel_id="_synth_", snapshot_root=root,
    )
    # Должны быть: 1 CommonModule, 1 Module, 2 Method, 1 CONTAINS module→methods × 2,
    # 1 CONTAINS object→module, 1 CALLS Главная→Хелпер
    assert stats.metadata_objects == 1
    assert stats.methods_extracted == 2
    assert stats.by_edge_kind.get(EdgeKind.CALLS.value, 0) == 1
    # CONTAINS: object→module + module→method×2
    assert stats.by_edge_kind.get(EdgeKind.CONTAINS.value, 0) == 3


@pytest.mark.asyncio
async def test_build_typical_graph_missing_root_raises(db_ready, tmp_path):
    with pytest.raises(FileNotFoundError):
        await build_typical_graph(
            db_ready, channel_id="_synth_", snapshot_root=tmp_path / "nonexistent",
        )


@pytest.mark.asyncio
async def test_build_typical_graph_missing_configuration_xml(db_ready, tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(FileNotFoundError):
        await build_typical_graph(
            db_ready, channel_id="_synth_", snapshot_root=root,
        )


@pytest.mark.asyncio
async def test_build_typical_graph_idempotent(db_ready, tmp_path):
    """Повторный build на той же snapshot не дублирует nodes/edges."""
    root = _write_synthetic_snapshot(tmp_path)
    s1 = await build_typical_graph(
        db_ready, channel_id="_idem_", snapshot_root=root,
    )
    nodes1 = await count_nodes(db_ready, "_idem_")
    edges1 = await count_edges(db_ready, "_idem_")

    s2 = await build_typical_graph(
        db_ready, channel_id="_idem_", snapshot_root=root,
    )
    nodes2 = await count_nodes(db_ready, "_idem_")
    edges2 = await count_edges(db_ready, "_idem_")

    assert nodes2 == nodes1
    assert edges2 == edges1


@pytest.mark.asyncio
async def test_build_typical_graph_bsl_file_limit(db_ready, tmp_path):
    """bsl_file_limit=0 пропускает все BSL → 0 методов."""
    root = _write_synthetic_snapshot(tmp_path)
    stats = await build_typical_graph(
        db_ready, channel_id="_lim_", snapshot_root=root, bsl_file_limit=0,
    )
    assert stats.methods_extracted == 0
    # Но структурные nodes должны быть
    assert stats.metadata_objects == 1
    assert stats.by_node_kind.get(NodeKind.MODULE.value, 0) == 1


# ─── Проверка attributes конкретных edges ─────────────────────────────


@pytest.mark.asyncio
async def test_calls_attributes_distinguish_resolution(db_ready, tmp_path):
    """CALLS edge атрибут resolution=same_module vs common_module."""
    root = _write_synthetic_snapshot(tmp_path)
    await build_typical_graph(
        db_ready, channel_id="_attrs_", snapshot_root=root,
    )
    # Главная вызывает Хелпер — same_module
    main_method = await find_node(
        db_ready, channel_id="_attrs_",
        qualified_name="CommonModule.ОбщегоНазначения.CommonModuleBody.Главная",
        node_kind=NodeKind.METHOD.value,
    )
    assert main_method is not None
    edges = await get_edges_from(db_ready, main_method.id, edge_kind=EdgeKind.CALLS.value)
    assert len(edges) == 1
    assert edges[0].attributes.get("resolution") == "same_module"
