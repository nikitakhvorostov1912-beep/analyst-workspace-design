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
    RoleRight,
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


def _read_xml_robust(path: Path) -> ET.Element:
    """Как _read_xml, но устойчив к рассогласованию кодировки.

    1С иногда пишет Rights.xml в cp1251 при declaration UTF-8 →
    ET.fromstring(bytes) падает на декодировании. Фоллбэк: декодируем
    cp1251/utf-8 вручную, срезаем XML-декларацию (ET не принимает её в str),
    парсим из строки.
    """
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return ET.fromstring(raw)
    except (ET.ParseError, UnicodeDecodeError, ValueError):
        for enc in ("cp1251", "utf-8"):
            try:
                text = raw.decode(enc)
            except UnicodeDecodeError:
                continue
            stripped = text.lstrip()
            if stripped.startswith("<?xml"):
                text = stripped[stripped.index("?>") + 2:]
            return ET.fromstring(text)
        raise


def parse_rights_xml(path: str | Path) -> list[RoleRight]:
    """Парсит Roles/<Role>/Ext/Rights.xml → список RoleRight (право + RLS-условие).

    Namespace http://v8.1c.ru/8.2/roles снимается через _local_name. Структура:
      <Rights><object><name>Document.X</name>
        <right><name>Read</name><value>true</value>
          [<restrictionByCondition><condition>...</condition></restrictionByCondition>]
        </right>...</object>...</Rights>
    Возвращает по одному RoleRight на пару (object, right).
    """
    p = Path(path)
    root = _read_xml_robust(p)
    rights: list[RoleRight] = []
    for obj in _find_all_local(root, "object"):
        object_name = _text_of_local(obj, "name")
        if not object_name:
            continue
        for right in _find_all_local(obj, "right"):
            right_name = _text_of_local(right, "name")
            if not right_name:
                continue
            value = _bool_text(_text_of_local(right, "value", "false"))
            condition: str | None = None
            rbc = _find_local(right, "restrictionByCondition")
            if rbc is not None:
                cond = _text_of_local(rbc, "condition").strip()
                condition = cond or None
            rights.append(RoleRight(
                object_name=object_name,
                right_name=right_name,
                value=value,
                condition=condition,
            ))
    return rights


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
    """Сканирует Ext/ + Forms/*/Ext/Form/ + Commands/*/Ext/ объекта.

    M-K2.5.audit (2026-05-26): расширено — раньше `_discover_modules`
    собирал только object-level Ext/*.bsl, теряя ~50% реальных модулей
    (FormModule + CommandModule под формами / командами). Теперь
    обходит все известные локации.

    Включает:
    - `Ext/ObjectModule.bsl` / `ManagerModule.bsl` / `Module.bsl` / ...
    - **`Forms/<FormName>/Ext/Form/Module.bsl`** (FormModule) — для
      обработчиков форм (ПриОткрытии, КомандаНажатие, ...)
    - **`Forms/<FormName>/Ext/CommandModule.bsl`** — для команд формы
    - **`Commands/<CmdName>/Ext/CommandModule.bsl`** — для object commands
    - **`Templates/<TplName>/Ext/Template/Help.html` НЕ берём** — это
      справка, не BSL
    """
    if object_dir is None or not object_dir.is_dir():
        return []

    modules: list[MetadataModule] = []
    parent_root = (
        object_dir.parent.parent if object_dir.parent.parent.exists() else None
    )

    def _emit(f: Path, kind: ModuleKind) -> None:
        if not f.is_file():
            return
        try:
            line_count = len(f.read_text(encoding="utf-8").splitlines())
        except UnicodeDecodeError:
            line_count = len(f.read_text(encoding="cp1251").splitlines())
        modules.append(
            MetadataModule(
                kind=kind.value,
                relative_path=str(f.relative_to(parent_root)) if parent_root else str(f),
                line_count=line_count,
            )
        )

    # 1. Object-level Ext/*.bsl
    ext_dir = object_dir / "Ext"
    if ext_dir.is_dir():
        module_files = {
            "ObjectModule.bsl": ModuleKind.OBJECT_MODULE,
            "ManagerModule.bsl": ModuleKind.MANAGER_MODULE,
            "Module.bsl": ModuleKind.COMMON_MODULE_BODY,
            "RecordSetModule.bsl": ModuleKind.RECORD_SET_MODULE,
            "ValueManagerModule.bsl": ModuleKind.VALUE_MANAGER_MODULE,
            "CommandModule.bsl": ModuleKind.COMMAND_MODULE,
        }
        for file_name, kind in module_files.items():
            _emit(ext_dir / file_name, kind)

    # 2. Form modules: Forms/<Name>/Ext/Form/Module.bsl + CommandModule.bsl
    forms_dir = object_dir / "Forms"
    if forms_dir.is_dir():
        for form_path in sorted(forms_dir.iterdir()):
            if not form_path.is_dir():
                continue
            _emit(form_path / "Ext" / "Form" / "Module.bsl", ModuleKind.FORM_MODULE)
            _emit(form_path / "Ext" / "CommandModule.bsl", ModuleKind.COMMAND_MODULE)

    # 3. Object commands: Commands/<Name>/Ext/CommandModule.bsl
    commands_dir = object_dir / "Commands"
    if commands_dir.is_dir():
        for cmd_path in sorted(commands_dir.iterdir()):
            if not cmd_path.is_dir():
                continue
            _emit(cmd_path / "Ext" / "CommandModule.bsl", ModuleKind.COMMAND_MODULE)

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
