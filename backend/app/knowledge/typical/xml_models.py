"""Метаданные конфигурации 1С — модели для XML парсера.

Соответствует структуре выгрузки `DumpConfigToFiles` из конфигуратора:
```
src/
├── Configuration.xml          — корень с метаданными конфигурации
├── Documents/
│   ├── <Имя>.xml             — описание документа
│   └── <Имя>/Ext/...         — модули и формы документа
├── Catalogs/<Имя>.xml
├── AccumulationRegisters/<Имя>.xml
├── CommonModules/<Имя>.xml
├── ...
```

## Что моделируем

| Концепт 1С | Класс |
|---|---|
| Конфигурация целиком | `MetadataConfiguration` |
| Любой объект метаданных | `MetadataObject` (с kind enum) |
| Реквизит / измерение / ресурс | `MetadataAttribute` |
| Табличная часть | `MetadataTabularSection` |
| Форма | `MetadataForm` |
| Модуль (Object/Manager/Form) | `MetadataModule` |

## Что НЕ моделируем (отложено)

- XDTO-схемы / СКД (Phase 3.5)
- Шаблоны (макеты MXL) — Phase 3.5
- Командный интерфейс / интерфейсные элементы — Phase 4 graph
- Поля СКД отчётов внутри XML — Phase 4 graph
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MetadataKind(str, Enum):
    """Тип объекта метаданных. Соответствует папке в выгрузке.

    Не все типы 1С есть в этом списке — добавляем по мере появления
    задач. Для редких типов (BusinessProcess, Task, и т.д.) ставим
    UNKNOWN и сохраняем имя в attributes.
    """

    DOCUMENT = "Document"
    CATALOG = "Catalog"
    ACCUMULATION_REGISTER = "AccumulationRegister"
    INFORMATION_REGISTER = "InformationRegister"
    ACCOUNTING_REGISTER = "AccountingRegister"
    CALCULATION_REGISTER = "CalculationRegister"
    REPORT = "Report"
    DATA_PROCESSOR = "DataProcessor"
    CONSTANT = "Constant"
    ENUM = "Enum"
    COMMON_MODULE = "CommonModule"
    CHART_OF_CHARACTERISTIC_TYPES = "ChartOfCharacteristicTypes"
    CHART_OF_ACCOUNTS = "ChartOfAccounts"
    CHART_OF_CALCULATION_TYPES = "ChartOfCalculationTypes"
    SUBSCRIPTION = "EventSubscription"
    SCHEDULED_JOB = "ScheduledJob"
    ROLE = "Role"
    SUBSYSTEM = "Subsystem"
    EXCHANGE_PLAN = "ExchangePlan"
    BUSINESS_PROCESS = "BusinessProcess"
    TASK = "Task"
    SEQUENCE = "Sequence"
    DOCUMENT_JOURNAL = "DocumentJournal"
    FUNCTIONAL_OPTION = "FunctionalOption"
    FUNCTIONAL_OPTIONS_PARAMETER = "FunctionalOptionsParameter"
    SETTINGS_STORAGE = "SettingsStorage"
    SESSION_PARAMETER = "SessionParameter"
    DEFINED_TYPE = "DefinedType"
    COMMON_FORM = "CommonForm"
    COMMON_COMMAND = "CommonCommand"
    COMMAND_GROUP = "CommandGroup"
    COMMON_TEMPLATE = "CommonTemplate"
    COMMON_PICTURE = "CommonPicture"
    COMMON_ATTRIBUTE = "CommonAttribute"
    UNKNOWN = "Unknown"


# Маппинг папки в выгрузке → MetadataKind. Используется при обходе
# `parse_configuration(root)` для классификации объектов.
DIRECTORY_TO_KIND: dict[str, MetadataKind] = {
    "Documents": MetadataKind.DOCUMENT,
    "Catalogs": MetadataKind.CATALOG,
    "AccumulationRegisters": MetadataKind.ACCUMULATION_REGISTER,
    "InformationRegisters": MetadataKind.INFORMATION_REGISTER,
    "AccountingRegisters": MetadataKind.ACCOUNTING_REGISTER,
    "CalculationRegisters": MetadataKind.CALCULATION_REGISTER,
    "Reports": MetadataKind.REPORT,
    "DataProcessors": MetadataKind.DATA_PROCESSOR,
    "Constants": MetadataKind.CONSTANT,
    "Enums": MetadataKind.ENUM,
    "CommonModules": MetadataKind.COMMON_MODULE,
    "ChartsOfCharacteristicTypes": MetadataKind.CHART_OF_CHARACTERISTIC_TYPES,
    "ChartsOfAccounts": MetadataKind.CHART_OF_ACCOUNTS,
    "ChartsOfCalculationTypes": MetadataKind.CHART_OF_CALCULATION_TYPES,
    "EventSubscriptions": MetadataKind.SUBSCRIPTION,
    "ScheduledJobs": MetadataKind.SCHEDULED_JOB,
    "Roles": MetadataKind.ROLE,
    "Subsystems": MetadataKind.SUBSYSTEM,
    "ExchangePlans": MetadataKind.EXCHANGE_PLAN,
    "BusinessProcesses": MetadataKind.BUSINESS_PROCESS,
    "Tasks": MetadataKind.TASK,
    "Sequences": MetadataKind.SEQUENCE,
    "DocumentJournals": MetadataKind.DOCUMENT_JOURNAL,
    "FunctionalOptions": MetadataKind.FUNCTIONAL_OPTION,
    "FunctionalOptionsParameters": MetadataKind.FUNCTIONAL_OPTIONS_PARAMETER,
    "SettingsStorages": MetadataKind.SETTINGS_STORAGE,
    "SessionParameters": MetadataKind.SESSION_PARAMETER,
    "DefinedTypes": MetadataKind.DEFINED_TYPE,
    "CommonForms": MetadataKind.COMMON_FORM,
    "CommonCommands": MetadataKind.COMMON_COMMAND,
    "CommandGroups": MetadataKind.COMMAND_GROUP,
    "CommonTemplates": MetadataKind.COMMON_TEMPLATE,
    "CommonPictures": MetadataKind.COMMON_PICTURE,
    "CommonAttributes": MetadataKind.COMMON_ATTRIBUTE,
}


class ModuleKind(str, Enum):
    """Тип BSL модуля в составе объекта метаданных."""

    OBJECT_MODULE = "ObjectModule"          # `Ext/ObjectModule.bsl`
    MANAGER_MODULE = "ManagerModule"        # `Ext/ManagerModule.bsl`
    FORM_MODULE = "FormModule"              # `Forms/<Form>/Ext/Form/Module.bsl`
    COMMAND_MODULE = "CommandModule"        # `Commands/<Cmd>/Ext/CommandModule.bsl`
    COMMON_MODULE_BODY = "CommonModuleBody"  # `Ext/Module.bsl` для CommonModule
    RECORD_SET_MODULE = "RecordSetModule"   # `Ext/RecordSetModule.bsl` для регистров
    VALUE_MANAGER_MODULE = "ValueManagerModule"  # для констант


@dataclass(frozen=True, slots=True)
class MetadataAttribute:
    """Реквизит / измерение / ресурс.

    `type_definition` — сырое описание типа из XML (`TypeSet` блок).
    Парсинг конкретных типов (`СправочникСсылка.Контрагенты`, ...) —
    Phase 4 graph builder для REFERENCES edges.
    """

    name: str
    type_definition: str = ""
    length: int | None = None
    precision: int | None = None
    comment: str = ""
    indexed: bool = False
    fill_check: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type_definition": self.type_definition,
            "length": self.length,
            "precision": self.precision,
            "comment": self.comment,
            "indexed": self.indexed,
            "fill_check": self.fill_check,
        }


@dataclass(frozen=True, slots=True)
class MetadataTabularSection:
    """Табличная часть документа / справочника / отчёта."""

    name: str
    comment: str = ""
    attributes: tuple[MetadataAttribute, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "comment": self.comment,
            "attributes": [a.to_dict() for a in self.attributes],
        }


@dataclass(frozen=True, slots=True)
class MetadataForm:
    """Форма объекта (или общая форма).

    `form_type` — DocumentForm / ListForm / ChoiceForm / ItemForm /
    RecordForm / etc — определяется по подпапке Forms/<Имя>.
    """

    name: str
    form_type: str = ""
    module_relative_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "form_type": self.form_type,
            "module_relative_path": self.module_relative_path,
        }


@dataclass(frozen=True, slots=True)
class MetadataModule:
    """BSL модуль, ассоциированный с объектом."""

    kind: str  # ModuleKind.value
    relative_path: str
    line_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "relative_path": self.relative_path,
            "line_count": self.line_count,
        }


@dataclass(frozen=True, slots=True)
class MetadataObject:
    """Один объект метаданных: документ / справочник / регистр / отчёт / etc.

    Унифицированная структура — `kind` enum определяет «что это»,
    а конкретные поля заполняются по релевантности (CommonModule имеет
    modules но не attributes, AccumulationRegister имеет measurements
    + resources + attributes, и т.д.).
    """

    name: str
    kind: str  # MetadataKind.value
    uuid: str | None = None
    comment: str = ""
    source_path: str | None = None
    attributes: tuple[MetadataAttribute, ...] = field(default_factory=tuple)
    dimensions: tuple[MetadataAttribute, ...] = field(default_factory=tuple)
    resources: tuple[MetadataAttribute, ...] = field(default_factory=tuple)
    tabular_sections: tuple[MetadataTabularSection, ...] = field(default_factory=tuple)
    forms: tuple[MetadataForm, ...] = field(default_factory=tuple)
    modules: tuple[MetadataModule, ...] = field(default_factory=tuple)
    commands: tuple[str, ...] = field(default_factory=tuple)
    templates: tuple[str, ...] = field(default_factory=tuple)
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        """Полное имя в стиле 1С: `Документ.РеализацияТоваровУслуг`."""
        return f"{self.kind}.{self.name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "qualified_name": self.qualified_name,
            "uuid": self.uuid,
            "comment": self.comment,
            "source_path": self.source_path,
            "attributes": [a.to_dict() for a in self.attributes],
            "dimensions": [a.to_dict() for a in self.dimensions],
            "resources": [a.to_dict() for a in self.resources],
            "tabular_sections": [t.to_dict() for t in self.tabular_sections],
            "forms": [f.to_dict() for f in self.forms],
            "modules": [m.to_dict() for m in self.modules],
            "commands": list(self.commands),
            "templates": list(self.templates),
            "extras": self.extras,
        }


@dataclass(frozen=True, slots=True)
class RoleRight:
    """Право роли на объект из Roles/<Role>/Ext/Rights.xml (M-K3.17.2 RLS).

    `object_name` — имя в стиле выгрузки («Document.X», «Catalog.Y»,
    «Subsystem.A.Subsystem.B»). `right_name` — «Read»/«Update»/«View»/...
    `condition` — текст RLS-ограничения (restrictionByCondition), если есть,
    например «ВладелецДокумента = &ТекущийПользователь». Источник RLS-условий —
    ТОЛЬКО снапшот: живой MCP get_access_rights текст условия не возвращает.
    """

    object_name: str
    right_name: str
    value: bool
    condition: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_name": self.object_name,
            "right_name": self.right_name,
            "value": self.value,
            "condition": self.condition,
        }


@dataclass(frozen=True, slots=True)
class MetadataConfiguration:
    """Корень конфигурации — `Configuration.xml`.

    `name` — внутреннее имя конфигурации (`УправлениеТорговлей`).
    `version` — версия из XML (`<Version>11.5.18.193</Version>`).
    `vendor` — поставщик (`Фирма \"1С\"`).
    `compatibility_mode` — `Версия8_3_27`.
    """

    name: str
    version: str = ""
    vendor: str = ""
    compatibility_mode: str = ""
    default_run_mode: str = ""
    detailed_information: str = ""
    metadata_objects: tuple[MetadataObject, ...] = field(default_factory=tuple)

    @property
    def total_objects(self) -> int:
        return len(self.metadata_objects)

    def objects_by_kind(self, kind: MetadataKind) -> tuple[MetadataObject, ...]:
        return tuple(o for o in self.metadata_objects if o.kind == kind.value)

    def count_by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for o in self.metadata_objects:
            counts[o.kind] = counts.get(o.kind, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "vendor": self.vendor,
            "compatibility_mode": self.compatibility_mode,
            "default_run_mode": self.default_run_mode,
            "detailed_information": self.detailed_information,
            "total_objects": self.total_objects,
            "count_by_kind": self.count_by_kind(),
            "metadata_objects": [o.to_dict() for o in self.metadata_objects],
        }
