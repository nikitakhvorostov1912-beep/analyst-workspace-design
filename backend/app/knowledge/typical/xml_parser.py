"""XML парсер выгрузки конфигурации 1С (`DumpConfigToFiles`).

Разбирает дерево XML, выгруженное DESIGNER'ом командой:
`1cv8.exe DESIGNER /DumpConfigToFiles <path>`. Возвращает
`MetadataConfiguration` со списком всех `MetadataObject`.

## Поддерживаемые форматы выгрузки

- **DESIGNER (стандартный)** — основной use case. Каждый объект — XML
  + папка `Ext/` с модулями и формами.
- **EDT** — частично. EDT использует `*.mdo` (YAML-like) и `Form.form`
  вместо `Form.xml`. Этот парсер ориентирован на DESIGNER формат —
  EDT поддержка в Phase 8 если потребуется.

## Что парсим

| Поле | Источник в XML |
|---|---|
| Configuration.name | `Configuration/Properties/Name` |
| Configuration.version | `Configuration/Properties/Version` |
| Configuration.vendor | `Configuration/Properties/Vendor` |
| Configuration.compatibility_mode | `Configuration/Properties/CompatibilityMode` |
| MetadataObject.name | `Document/Properties/Name` (и аналоги) |
| MetadataObject.comment | `Document/Properties/Comment` |
| Attributes | `ChildObjects/Attribute` |
| TabularSections | `ChildObjects/TabularSection` |
| Dimensions / Resources (для регистров) | `ChildObjects/Dimension`, `Resource` |
| Forms | `ChildObjects/Form` + папка `Forms/<имя>/` |

## Namespace XML

1С использует:
- `xmlns="http://v8.1c.ru/8.3/MDClasses"` для основных тегов
- `xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"` для readable объектов
- `xmlns:xs="http://www.w3.org/2001/XMLSchema"` для типов

Парсер использует `iterparse` с автоматической отрезкой namespace
через `_local_name()`.

## Что НЕ парсит (отложено)

- Содержимое типов (TypeSet) — Phase 4 graph builder выделит ссылки
  на справочники / документы / перечисления
- СКД отчётов (Form.xml + DCS) — Phase 3.5 если потребуется
- Шаблоны MXL — Phase 3.5
- Права на роли (Rights/<RoleName>.xml) — Phase 4 RLS analysis
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from app.knowledge.typical.xml_models import (
    DIRECTORY_TO_KIND,
    MetadataAttribute,
    MetadataConfiguration,
    MetadataForm,
    MetadataKind,
    MetadataModule,
    MetadataObject,
    MetadataTabularSection,
    ModuleKind,
)

logger = logging.getLogger(__name__)


# ── Namespace helpers ────────────────────────────────────────────────


_NS_RE = re.compile(r"^\{[^}]+\}")


def _local_name(tag: str) -> str:
    """Убирает namespace-префикс из тега XML.

    >>> _local_name("{http://v8.1c.ru/8.3/MDClasses}Properties")
    'Properties'
    >>> _local_name("Name")
    'Name'
    """
    return _NS_RE.sub("", tag)


def _find_local(parent: ET.Element, local_tag: str) -> ET.Element | None:
    """Первый child с указанным local-tag (игнорирует namespace)."""
    for child in parent:
        if _local_name(child.tag) == local_tag:
            return child
    return None


def _find_all_local(parent: ET.Element, local_tag: str) -> list[ET.Element]:
    return [c for c in parent if _local_name(c.tag) == local_tag]


def _text_of_local(parent: ET.Element, local_tag: str, default: str = "") -> str:
    elem = _find_local(parent, local_tag)
    if elem is None:
        return default
    return (elem.text or "").strip()


def _bool_text(text: str) -> bool:
    return text.strip().lower() in ("true", "1", "yes")


# ── Configuration.xml ────────────────────────────────────────────────


def _read_xml(path: Path) -> ET.Element:
    """Читает XML файл устойчиво к BOM / отсутствию declaration."""
    raw = path.read_bytes()
    # 1С пишет BOM в XML файлы по умолчанию — ElementTree обычно справляется,
    # но на edge case подстрахуемся.
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return ET.fromstring(raw)


def parse_configuration_xml(path: str | Path) -> MetadataConfiguration:
    """Парсит только корневой `Configuration.xml` — без обхода объектов.

    Используется когда нужны метаданные конфигурации (name / version /
    vendor) быстро, без полной индексации. Полный обход — через
    `parse_configuration_tree()`.
    """
    p = Path(path)
    root = _read_xml(p)
    config = _find_local(root, "Configuration")
    if config is None:
        # Возможно корень сам Configuration (без MetaDataObject wrapper)
        if _local_name(root.tag) == "Configuration":
            config = root
        else:
            raise ValueError(
                f"{p}: не найден элемент Configuration. Корень: {root.tag}"
            )

    props = _find_local(config, "Properties") or config
    name = _text_of_local(props, "Name", default=p.stem)
    version = _text_of_local(props, "Version")
    vendor = _text_of_local(props, "Vendor")
    compatibility_mode = _text_of_local(props, "CompatibilityMode")
    default_run_mode = _text_of_local(props, "DefaultRunMode")
    detailed_information = _text_of_local(props, "DetailedInformation")

    return MetadataConfiguration(
        name=name,
        version=version,
        vendor=vendor,
        compatibility_mode=compatibility_mode,
        default_run_mode=default_run_mode,
        detailed_information=detailed_information,
        metadata_objects=(),
    )


# ── Один MetadataObject ──────────────────────────────────────────────


def _parse_attribute(attr_elem: ET.Element) -> MetadataAttribute:
    """Реквизит / измерение / ресурс из `<Attribute>` / `<Dimension>` / `<Resource>`."""
    props = _find_local(attr_elem, "Properties")
    if props is None:
        return MetadataAttribute(name="")

    name = _text_of_local(props, "Name")
    comment = _text_of_local(props, "Comment")
    indexed_text = _text_of_local(props, "Indexing")
    indexed = indexed_text.strip().lower() in ("index", "indexandadditional")
    fill_check = _bool_text(_text_of_local(props, "FillChecking", "DontCheck") != "DontCheck" and "true" or "false")

    type_elem = _find_local(props, "Type")
    type_definition = ""
    if type_elem is not None:
        # Сохраняем сырой текст типов через iter() — там TypeSet с
        # перечисленными базовыми типами
        types_text: list[str] = []
        for child in type_elem.iter():
            local = _local_name(child.tag)
            if local == "Type" and (child.text or "").strip():
                types_text.append(child.text.strip())
        type_definition = ", ".join(types_text)

    length: int | None = None
    precision: int | None = None
    # Длина строки / точность числа лежат в Type/StringQualifiers/Length etc.
    if type_elem is not None:
        for q in type_elem.iter():
            local = _local_name(q.tag)
            if local == "Length" and (q.text or "").strip().isdigit():
                length = int(q.text.strip())
            elif local == "Precision" and (q.text or "").strip().isdigit():
                precision = int(q.text.strip())

    return MetadataAttribute(
        name=name,
        type_definition=type_definition,
        length=length,
        precision=precision,
        comment=comment,
        indexed=indexed,
        fill_check=fill_check,
    )


def _parse_tabular_section(ts_elem: ET.Element) -> MetadataTabularSection:
    props = _find_local(ts_elem, "Properties")
    name = _text_of_local(props, "Name") if props is not None else ""
    comment = _text_of_local(props, "Comment") if props is not None else ""

    children = _find_local(ts_elem, "ChildObjects")
    attrs: list[MetadataAttribute] = []
    if children is not None:
        for child in _find_all_local(children, "Attribute"):
            attrs.append(_parse_attribute(child))

    return MetadataTabularSection(
        name=name,
        comment=comment,
        attributes=tuple(attrs),
    )


def _discover_modules(object_dir: Path | None) -> list[MetadataModule]:
    """Сканирует Ext/ папку объекта и собирает список модулей."""
    if object_dir is None or not object_dir.is_dir():
        return []

    modules: list[MetadataModule] = []
    ext_dir = object_dir / "Ext"
    if not ext_dir.is_dir():
        return []

    module_files = {
        "ObjectModule.bsl": ModuleKind.OBJECT_MODULE,
        "ManagerModule.bsl": ModuleKind.MANAGER_MODULE,
        "Module.bsl": ModuleKind.COMMON_MODULE_BODY,  # для CommonModule
        "RecordSetModule.bsl": ModuleKind.RECORD_SET_MODULE,
        "ValueManagerModule.bsl": ModuleKind.VALUE_MANAGER_MODULE,
        "CommandModule.bsl": ModuleKind.COMMAND_MODULE,
    }

    for file_name, kind in module_files.items():
        f = ext_dir / file_name
        if f.is_file():
            try:
                line_count = len(f.read_text(encoding="utf-8").splitlines())
            except UnicodeDecodeError:
                line_count = len(f.read_text(encoding="cp1251").splitlines())
            modules.append(
                MetadataModule(
                    kind=kind.value,
                    relative_path=str(f.relative_to(object_dir.parent.parent))
                    if object_dir.parent.parent.exists()
                    else str(f),
                    line_count=line_count,
                )
            )

    return modules


def _discover_forms(object_dir: Path | None) -> list[MetadataForm]:
    """Сканирует папку Forms/ объекта и собирает список форм."""
    if object_dir is None or not object_dir.is_dir():
        return []

    forms_dir = object_dir / "Forms"
    if not forms_dir.is_dir():
        return []

    forms: list[MetadataForm] = []
    for form_path in sorted(forms_dir.iterdir()):
        if not form_path.is_dir():
            continue
        form_name = form_path.name
        # Тип формы можно вытащить из <FormType> в Forms/<Name>.xml,
        # но обычно это видно по имени (ФормаДокумента / ФормаСписка / ...).
        # Для Phase 3 этого достаточно.
        module_path = form_path / "Ext" / "Form" / "Module.bsl"
        relative_module = (
            str(module_path.relative_to(object_dir.parent.parent))
            if module_path.is_file() and object_dir.parent.parent.exists()
            else None
        )
        forms.append(
            MetadataForm(
                name=form_name,
                form_type="",  # детальный type — в Phase 4 если нужно
                module_relative_path=relative_module,
            )
        )
    return forms


def parse_metadata_file(
    path: str | Path,
    kind: MetadataKind | str | None = None,
) -> MetadataObject:
    """Парсит один XML файл объекта в `MetadataObject`.

    `kind` — если None, пытаемся определить по корневому тегу
    (`<Document>` → DOCUMENT, `<Catalog>` → CATALOG, и т.д.).
    `path` указывает на сам XML (`Documents/X.xml`), но мы ищем рядом
    папку `Documents/X/` для модулей и форм.
    """
    p = Path(path)
    root = _read_xml(p)

    # Корневая структура: <MetaDataObject><Document>...</Document></MetaDataObject>
    # или прямо <Document>... </Document>
    object_elem: ET.Element | None = None
    if _local_name(root.tag) == "MetaDataObject":
        # Берём первый child
        if len(root) > 0:
            object_elem = root[0]
    else:
        object_elem = root

    if object_elem is None:
        raise ValueError(f"{p}: пустой XML без MetaDataObject")

    if kind is None:
        # Auto-detect по local tag
        try:
            kind = MetadataKind(_local_name(object_elem.tag))
        except ValueError:
            kind = MetadataKind.UNKNOWN

    kind_value = kind.value if isinstance(kind, MetadataKind) else str(kind)

    uuid = object_elem.attrib.get("uuid")

    props = _find_local(object_elem, "Properties")
    name = _text_of_local(props, "Name", default=p.stem) if props is not None else p.stem
    comment = _text_of_local(props, "Comment") if props is not None else ""

    children = _find_local(object_elem, "ChildObjects")
    attributes: list[MetadataAttribute] = []
    dimensions: list[MetadataAttribute] = []
    resources: list[MetadataAttribute] = []
    tabular_sections: list[MetadataTabularSection] = []
    commands: list[str] = []
    templates: list[str] = []

    if children is not None:
        for child in children:
            local = _local_name(child.tag)
            if local == "Attribute":
                attributes.append(_parse_attribute(child))
            elif local in ("Dimension", "TaskAddressing"):
                dimensions.append(_parse_attribute(child))
            elif local == "Resource":
                resources.append(_parse_attribute(child))
            elif local == "TabularSection":
                tabular_sections.append(_parse_tabular_section(child))
            elif local in ("Command", "CommonCommand"):
                cmd_props = _find_local(child, "Properties")
                if cmd_props is not None:
                    commands.append(_text_of_local(cmd_props, "Name"))
            elif local == "Template":
                t_props = _find_local(child, "Properties")
                if t_props is not None:
                    templates.append(_text_of_local(t_props, "Name"))

    # Discover modules + forms (только если рядом есть папка объекта)
    object_dir = p.parent / p.stem
    modules = _discover_modules(object_dir if object_dir.is_dir() else None)
    forms = _discover_forms(object_dir if object_dir.is_dir() else None)

    return MetadataObject(
        name=name,
        kind=kind_value,
        uuid=uuid,
        comment=comment,
        source_path=str(p),
        attributes=tuple(attributes),
        dimensions=tuple(dimensions),
        resources=tuple(resources),
        tabular_sections=tuple(tabular_sections),
        forms=tuple(forms),
        modules=tuple(modules),
        commands=tuple(commands),
        templates=tuple(templates),
    )


# ── Полный обход выгрузки ────────────────────────────────────────────


def discover_metadata_files(
    root_dir: str | Path,
) -> dict[MetadataKind, list[Path]]:
    """Возвращает маппинг kind → список XML файлов объектов.

    Сканирует стандартные подпапки DESIGNER выгрузки (Documents/,
    Catalogs/, AccumulationRegisters/, и т.д.). Неизвестные папки —
    игнорируются (логируется warning).
    """
    root = Path(root_dir)
    if not root.is_dir():
        raise ValueError(f"{root}: не директория")

    result: dict[MetadataKind, list[Path]] = {}
    for sub_dir in sorted(root.iterdir()):
        if not sub_dir.is_dir():
            continue
        kind = DIRECTORY_TO_KIND.get(sub_dir.name)
        if kind is None:
            continue
        xml_files = sorted(sub_dir.glob("*.xml"))
        if xml_files:
            result[kind] = xml_files
    return result


def parse_configuration_tree(
    root_dir: str | Path,
    *,
    skip_kinds: set[MetadataKind] | None = None,
) -> MetadataConfiguration:
    """Полный обход выгрузки: Configuration.xml + все объекты.

    `skip_kinds` — типы объектов которые НЕ парсить (для быстрой
    индексации только нужного). Например `{ROLE, COMMON_PICTURE}` если
    роли и картинки не нужны.

    Возвращает `MetadataConfiguration` с заполненным `metadata_objects`.
    """
    root = Path(root_dir)
    config_xml = root / "Configuration.xml"
    if not config_xml.is_file():
        raise ValueError(f"{root}: нет Configuration.xml")

    config = parse_configuration_xml(config_xml)

    skip = skip_kinds or set()
    files = discover_metadata_files(root)

    objects: list[MetadataObject] = []
    for kind, xml_files in files.items():
        if kind in skip:
            continue
        for xml_file in xml_files:
            try:
                obj = parse_metadata_file(xml_file, kind=kind)
                objects.append(obj)
            except Exception as exc:
                logger.warning(
                    f"Не удалось распарсить {xml_file}: {exc!r}"
                )

    return MetadataConfiguration(
        name=config.name,
        version=config.version,
        vendor=config.vendor,
        compatibility_mode=config.compatibility_mode,
        default_run_mode=config.default_run_mode,
        detailed_information=config.detailed_information,
        metadata_objects=tuple(objects),
    )
