"""Тесты для backend/app/knowledge/typical/xml_parser.py (M-K2.5.3).

Покрытие:
- _local_name: namespace stripping
- parse_configuration_xml: name / version / vendor / compatibility
- parse_metadata_file: Document / Catalog / Register с реквизитами и ТЧ
- AccumulationRegister с Dimensions + Resources
- CommonModule с modules через _discover_modules()
- Form discovery через _discover_forms()
- BOM в XML
- Без Configuration root — graceful
- Unknown kind → MetadataKind.UNKNOWN
- discover_metadata_files: маппинг папок
- parse_configuration_tree: полный обход + skip_kinds
- Утечки исключений при битом XML
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.knowledge.typical.xml_models import (
    DIRECTORY_TO_KIND,
    MetadataConfiguration,
    MetadataKind,
    MetadataObject,
    ModuleKind,
)
from app.knowledge.typical.xml_parser import (
    _local_name,
    discover_metadata_files,
    parse_configuration_tree,
    parse_configuration_xml,
    parse_metadata_file,
)


# ── XML fixtures helpers ─────────────────────────────────────────────


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


CONFIG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Configuration uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee">
    <Properties>
      <Name>УправлениеТорговлей</Name>
      <Version>11.5.18.193</Version>
      <Vendor>Фирма "1С"</Vendor>
      <CompatibilityMode>Версия8_3_27</CompatibilityMode>
      <DefaultRunMode>ManagedApplication</DefaultRunMode>
      <DetailedInformation>УТ 11.5 типовая</DetailedInformation>
    </Properties>
  </Configuration>
</MetaDataObject>
"""

DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Document uuid="11111111-1111-1111-1111-111111111111">
    <Properties>
      <Name>РеализацияТоваровУслуг</Name>
      <Comment>Реализация товаров покупателям</Comment>
    </Properties>
    <ChildObjects>
      <Attribute uuid="22222222-2222-2222-2222-222222222222">
        <Properties>
          <Name>Контрагент</Name>
          <Comment>Получатель товаров</Comment>
          <Indexing>Index</Indexing>
          <Type>
            <Type>cfg:CatalogRef.Контрагенты</Type>
          </Type>
        </Properties>
      </Attribute>
      <Attribute>
        <Properties>
          <Name>СуммаДокумента</Name>
          <Indexing>DontIndex</Indexing>
          <Type>
            <Type>xs:decimal</Type>
            <NumberQualifiers>
              <Precision>15</Precision>
            </NumberQualifiers>
          </Type>
        </Properties>
      </Attribute>
      <TabularSection>
        <Properties>
          <Name>Товары</Name>
          <Comment>Состав документа</Comment>
        </Properties>
        <ChildObjects>
          <Attribute>
            <Properties>
              <Name>Номенклатура</Name>
              <Type><Type>cfg:CatalogRef.Номенклатура</Type></Type>
            </Properties>
          </Attribute>
          <Attribute>
            <Properties>
              <Name>Количество</Name>
              <Type><Type>xs:decimal</Type></Type>
            </Properties>
          </Attribute>
        </ChildObjects>
      </TabularSection>
      <Command>
        <Properties>
          <Name>СоздатьВозврат</Name>
        </Properties>
      </Command>
    </ChildObjects>
  </Document>
</MetaDataObject>
"""

CATALOG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Catalog uuid="33333333-3333-3333-3333-333333333333">
    <Properties>
      <Name>Контрагенты</Name>
    </Properties>
    <ChildObjects>
      <Attribute>
        <Properties>
          <Name>ИНН</Name>
          <Type>
            <Type>xs:string</Type>
            <StringQualifiers><Length>12</Length></StringQualifiers>
          </Type>
        </Properties>
      </Attribute>
    </ChildObjects>
  </Catalog>
</MetaDataObject>
"""

ACCUM_REGISTER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <AccumulationRegister uuid="44444444-4444-4444-4444-444444444444">
    <Properties>
      <Name>ТоварыНаСкладах</Name>
    </Properties>
    <ChildObjects>
      <Dimension>
        <Properties>
          <Name>Склад</Name>
          <Type><Type>cfg:CatalogRef.Склады</Type></Type>
        </Properties>
      </Dimension>
      <Dimension>
        <Properties>
          <Name>Номенклатура</Name>
          <Type><Type>cfg:CatalogRef.Номенклатура</Type></Type>
        </Properties>
      </Dimension>
      <Resource>
        <Properties>
          <Name>Количество</Name>
          <Type><Type>xs:decimal</Type></Type>
        </Properties>
      </Resource>
    </ChildObjects>
  </AccumulationRegister>
</MetaDataObject>
"""

COMMON_MODULE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <CommonModule uuid="55555555-5555-5555-5555-555555555555">
    <Properties>
      <Name>ОбщегоНазначения</Name>
    </Properties>
  </CommonModule>
</MetaDataObject>
"""


# ── _local_name ──────────────────────────────────────────────────────


def test_local_name_strips_namespace():
    assert _local_name("{http://v8.1c.ru/8.3/MDClasses}Properties") == "Properties"


def test_local_name_no_namespace():
    assert _local_name("Name") == "Name"


def test_local_name_empty():
    assert _local_name("") == ""


# ── parse_configuration_xml ──────────────────────────────────────────


def test_parse_configuration_xml(tmp_path):
    cfg_file = _write(tmp_path / "Configuration.xml", CONFIG_XML)
    config = parse_configuration_xml(cfg_file)
    assert config.name == "УправлениеТорговлей"
    assert config.version == "11.5.18.193"
    assert config.vendor == 'Фирма "1С"'
    assert config.compatibility_mode == "Версия8_3_27"
    assert config.default_run_mode == "ManagedApplication"


def test_parse_configuration_xml_handles_bom(tmp_path):
    """1С пишет BOM в XML — парсер должен переварить."""
    cfg_file = tmp_path / "Configuration.xml"
    cfg_file.write_bytes(b"\xef\xbb\xbf" + CONFIG_XML.encode("utf-8"))
    config = parse_configuration_xml(cfg_file)
    assert config.name == "УправлениеТорговлей"


def test_parse_configuration_xml_missing_required(tmp_path):
    """Configuration.xml без Configuration корня → ValueError."""
    bad = _write(
        tmp_path / "Bad.xml",
        '<?xml version="1.0"?><MetaDataObject xmlns="x"><Document/></MetaDataObject>',
    )
    with pytest.raises(ValueError, match="не найден элемент Configuration"):
        parse_configuration_xml(bad)


# ── parse_metadata_file Document ─────────────────────────────────────


def test_parse_document(tmp_path):
    doc = _write(tmp_path / "РеализацияТоваровУслуг.xml", DOCUMENT_XML)
    obj = parse_metadata_file(doc, kind=MetadataKind.DOCUMENT)
    assert obj.name == "РеализацияТоваровУслуг"
    assert obj.kind == "Document"
    assert obj.qualified_name == "Document.РеализацияТоваровУслуг"
    assert obj.comment == "Реализация товаров покупателям"
    assert obj.uuid == "11111111-1111-1111-1111-111111111111"


def test_document_attributes_parsed(tmp_path):
    doc = _write(tmp_path / "Реализация.xml", DOCUMENT_XML)
    obj = parse_metadata_file(doc, kind=MetadataKind.DOCUMENT)
    assert len(obj.attributes) == 2
    a1 = obj.attributes[0]
    assert a1.name == "Контрагент"
    assert a1.indexed is True
    assert "CatalogRef.Контрагенты" in a1.type_definition
    a2 = obj.attributes[1]
    assert a2.name == "СуммаДокумента"
    assert a2.indexed is False
    assert a2.precision == 15


def test_document_tabular_sections_parsed(tmp_path):
    doc = _write(tmp_path / "Реализация.xml", DOCUMENT_XML)
    obj = parse_metadata_file(doc, kind=MetadataKind.DOCUMENT)
    assert len(obj.tabular_sections) == 1
    ts = obj.tabular_sections[0]
    assert ts.name == "Товары"
    assert ts.comment == "Состав документа"
    assert len(ts.attributes) == 2
    assert ts.attributes[0].name == "Номенклатура"
    assert ts.attributes[1].name == "Количество"


def test_document_commands_parsed(tmp_path):
    doc = _write(tmp_path / "Реализация.xml", DOCUMENT_XML)
    obj = parse_metadata_file(doc, kind=MetadataKind.DOCUMENT)
    assert "СоздатьВозврат" in obj.commands


# ── parse_metadata_file Catalog / Register ───────────────────────────


def test_parse_catalog(tmp_path):
    cat = _write(tmp_path / "Контрагенты.xml", CATALOG_XML)
    obj = parse_metadata_file(cat, kind=MetadataKind.CATALOG)
    assert obj.kind == "Catalog"
    assert obj.name == "Контрагенты"
    assert obj.attributes[0].name == "ИНН"
    assert obj.attributes[0].length == 12


def test_parse_accumulation_register(tmp_path):
    reg = _write(tmp_path / "ТоварыНаСкладах.xml", ACCUM_REGISTER_XML)
    obj = parse_metadata_file(reg, kind=MetadataKind.ACCUMULATION_REGISTER)
    assert obj.kind == "AccumulationRegister"
    assert obj.name == "ТоварыНаСкладах"
    assert len(obj.dimensions) == 2
    assert {d.name for d in obj.dimensions} == {"Склад", "Номенклатура"}
    assert len(obj.resources) == 1
    assert obj.resources[0].name == "Количество"


def test_parse_common_module(tmp_path):
    mod_xml = _write(tmp_path / "ОбщегоНазначения.xml", COMMON_MODULE_XML)
    obj = parse_metadata_file(mod_xml, kind=MetadataKind.COMMON_MODULE)
    assert obj.kind == "CommonModule"
    assert obj.name == "ОбщегоНазначения"


# ── Auto-detect kind ─────────────────────────────────────────────────


def test_kind_autodetected_from_root_tag(tmp_path):
    doc = _write(tmp_path / "Реализация.xml", DOCUMENT_XML)
    obj = parse_metadata_file(doc, kind=None)
    assert obj.kind == "Document"


def test_unknown_kind_returns_unknown(tmp_path):
    """Тег которого нет в MetadataKind → UNKNOWN."""
    bad = _write(
        tmp_path / "Странный.xml",
        '<?xml version="1.0"?><MetaDataObject xmlns="x"><СтранныйТип>'
        '<Properties><Name>Х</Name></Properties></СтранныйТип></MetaDataObject>',
    )
    obj = parse_metadata_file(bad, kind=None)
    assert obj.kind == "Unknown"


# ── Modules / Forms discovery ────────────────────────────────────────


def test_discover_modules(tmp_path):
    """Если рядом с XML лежит папка Ext/ — модули собираются."""
    doc_xml = _write(tmp_path / "Реализация.xml", DOCUMENT_XML)
    object_dir = tmp_path / "Реализация"
    object_dir.mkdir()
    ext = object_dir / "Ext"
    ext.mkdir()
    (ext / "ObjectModule.bsl").write_text(
        "Процедура ОбработкаПроведения()\nКонецПроцедуры\n", encoding="utf-8"
    )
    (ext / "ManagerModule.bsl").write_text(
        "Функция Описание() Экспорт\nКонецФункции\n", encoding="utf-8"
    )

    obj = parse_metadata_file(doc_xml, kind=MetadataKind.DOCUMENT)
    module_kinds = {m.kind for m in obj.modules}
    assert ModuleKind.OBJECT_MODULE.value in module_kinds
    assert ModuleKind.MANAGER_MODULE.value in module_kinds


def test_discover_forms(tmp_path):
    """Папка Forms/ → MetadataForm[]."""
    doc_xml = _write(tmp_path / "Реализация.xml", DOCUMENT_XML)
    object_dir = tmp_path / "Реализация"
    forms_dir = object_dir / "Forms"
    form1_dir = forms_dir / "ФормаДокумента"
    form_module = form1_dir / "Ext" / "Form" / "Module.bsl"
    form_module.parent.mkdir(parents=True)
    form_module.write_text("// Модуль формы\n", encoding="utf-8")

    form2_dir = forms_dir / "ФормаСписка"
    form2_dir.mkdir(parents=True)

    obj = parse_metadata_file(doc_xml, kind=MetadataKind.DOCUMENT)
    form_names = {f.name for f in obj.forms}
    assert form_names == {"ФормаДокумента", "ФормаСписка"}


def test_modules_empty_if_no_ext_dir(tmp_path):
    doc_xml = _write(tmp_path / "Реализация.xml", DOCUMENT_XML)
    obj = parse_metadata_file(doc_xml, kind=MetadataKind.DOCUMENT)
    assert obj.modules == ()


# ── discover_metadata_files + parse_configuration_tree ───────────────


def _build_synthetic_tree(root: Path) -> None:
    """Создаёт синтетическую выгрузку конфигурации."""
    _write(root / "Configuration.xml", CONFIG_XML)
    _write(root / "Documents" / "РеализацияТоваровУслуг.xml", DOCUMENT_XML)
    _write(root / "Catalogs" / "Контрагенты.xml", CATALOG_XML)
    _write(
        root / "AccumulationRegisters" / "ТоварыНаСкладах.xml",
        ACCUM_REGISTER_XML,
    )
    _write(root / "CommonModules" / "ОбщегоНазначения.xml", COMMON_MODULE_XML)


def test_discover_metadata_files(tmp_path):
    _build_synthetic_tree(tmp_path)
    files = discover_metadata_files(tmp_path)
    assert MetadataKind.DOCUMENT in files
    assert MetadataKind.CATALOG in files
    assert MetadataKind.ACCUMULATION_REGISTER in files
    assert MetadataKind.COMMON_MODULE in files
    assert len(files[MetadataKind.DOCUMENT]) == 1


def test_discover_metadata_files_missing_dir_raises():
    with pytest.raises(ValueError, match="не директория"):
        discover_metadata_files("/non/existent/path/zzz")


def test_parse_configuration_tree_full(tmp_path):
    _build_synthetic_tree(tmp_path)
    config = parse_configuration_tree(tmp_path)
    assert config.name == "УправлениеТорговлей"
    assert config.version == "11.5.18.193"
    assert config.total_objects == 4
    counts = config.count_by_kind()
    assert counts["Document"] == 1
    assert counts["Catalog"] == 1
    assert counts["AccumulationRegister"] == 1
    assert counts["CommonModule"] == 1


def test_parse_configuration_tree_skip_kinds(tmp_path):
    _build_synthetic_tree(tmp_path)
    config = parse_configuration_tree(
        tmp_path, skip_kinds={MetadataKind.COMMON_MODULE}
    )
    counts = config.count_by_kind()
    assert "CommonModule" not in counts
    assert config.total_objects == 3


def test_parse_configuration_tree_missing_root_xml(tmp_path):
    with pytest.raises(ValueError, match="нет Configuration.xml"):
        parse_configuration_tree(tmp_path)


def test_objects_by_kind(tmp_path):
    _build_synthetic_tree(tmp_path)
    config = parse_configuration_tree(tmp_path)
    docs = config.objects_by_kind(MetadataKind.DOCUMENT)
    assert len(docs) == 1
    assert docs[0].name == "РеализацияТоваровУслуг"


def test_parse_configuration_tree_skips_unknown_dirs(tmp_path):
    """Папки не из DIRECTORY_TO_KIND игнорируются (без падения)."""
    _build_synthetic_tree(tmp_path)
    weird_dir = tmp_path / "SomeWeirdFolder"
    weird_dir.mkdir()
    (weird_dir / "x.xml").write_text("<x/>", encoding="utf-8")
    config = parse_configuration_tree(tmp_path)
    assert config.total_objects == 4  # weird не учтена


# ── MetadataConfiguration helpers ────────────────────────────────────


def test_count_by_kind_empty():
    config = MetadataConfiguration(name="X")
    assert config.count_by_kind() == {}
    assert config.total_objects == 0


def test_to_dict_contains_keys(tmp_path):
    _build_synthetic_tree(tmp_path)
    config = parse_configuration_tree(tmp_path)
    d = config.to_dict()
    expected = {
        "name", "version", "vendor", "compatibility_mode",
        "default_run_mode", "detailed_information",
        "total_objects", "count_by_kind", "metadata_objects",
    }
    assert expected <= set(d.keys())


def test_metadata_object_to_dict_keys(tmp_path):
    doc = _write(tmp_path / "Реализация.xml", DOCUMENT_XML)
    obj = parse_metadata_file(doc, kind=MetadataKind.DOCUMENT)
    d = obj.to_dict()
    expected = {
        "name", "kind", "qualified_name", "uuid", "comment", "source_path",
        "attributes", "dimensions", "resources", "tabular_sections",
        "forms", "modules", "commands", "templates", "extras",
    }
    assert expected <= set(d.keys())


# ── DIRECTORY_TO_KIND completeness ──────────────────────────────────


def test_directory_to_kind_mapping_complete():
    """Каждая запись маппинга соответствует валидному MetadataKind."""
    for kind in DIRECTORY_TO_KIND.values():
        assert isinstance(kind, MetadataKind)
        # И обратно — kind с config_kind value
        assert MetadataKind(kind.value) == kind


def test_directory_to_kind_includes_main_types():
    """Главные типы 1С присутствуют в маппинге."""
    expected_dirs = {
        "Documents", "Catalogs", "AccumulationRegisters",
        "InformationRegisters", "Reports", "DataProcessors",
        "Constants", "Enums", "CommonModules", "Roles", "Subsystems",
    }
    assert expected_dirs <= set(DIRECTORY_TO_KIND.keys())
