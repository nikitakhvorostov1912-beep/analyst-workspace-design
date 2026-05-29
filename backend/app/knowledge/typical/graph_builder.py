"""Semantic Graph Builder для типовых конфигураций 1С (M-K2.5.4).

Берёт распарсенную конфигурацию (xml_parser) + BSL модули (bsl_ast) +
запросы (query_parser) и строит 6 типов ребёр поверх graph_storage:

1. **CONTAINS** — структурные связи:
   - MetadataObject (Документ.X) → Attribute (Документ.X.Реквизит.Y)
   - MetadataObject → TabularSection
   - TabularSection → Attribute (вложенный реквизит ТЧ)
   - MetadataObject → Module (ObjectModule / ManagerModule / FormModule / ...)
   - Module → Method

2. **CALLS** — вызовы из BSL телах методов:
   - Method → Method (same-module по чистому имени)
   - Method → Method (cross-module через CommonModule.Имя.Метод)

3. **USES** — упоминания типов метаданных в коде:
   - Method → MetadataObject (через `Документы.X`, `Справочники.Y`,
     `РегистрыНакопления.Z` и т.д.)

4. **WRITES_TO** — движения регистров:
   - Method → AccumulationRegister/InformationRegister/AccountingRegister/
     CalculationRegister (через `Движения.X.Записать()` / `Добавить()`)

5. **READS_FROM** — чтение через запросы:
   - Method → MetadataObject (для физических таблиц из `ИЗ` / `СОЕДИНЕНИЕ`)
   - Method → Register* (для виртуальных таблиц с virtual_kind в attributes)

6. **REFERENCES** — типизированные ссылки реквизитов:
   - Attribute → MetadataObject (`СправочникСсылка.X`, `ДокументСсылка.Y`,
     и т.д.) — резолв по type_definition реквизита

## Архитектура

```
build_typical_graph(channel_id, snapshot_root)
   │
   ├─► Phase A: parse XML tree → MetadataConfiguration
   │
   ├─► Phase B: insert MetadataObject + Attribute + TabularSection +
   │            Module nodes (структурный CONTAINS)
   │           — собирает индексы: qualified_name → node_id,
   │             common_module_names, register_short_names,
   │             metadata_short_names_by_kind
   │
   ├─► Phase C: REFERENCES edges из type_definition реквизитов
   │
   └─► Phase D: для каждого .bsl модуля:
                  - parse_file → BSLModule
                  - insert Method nodes (CONTAINS)
                  - per-method: CALLS / USES / WRITES_TO / READS_FROM
```

## Идемпотентность

`insert_node` / `insert_edge` в graph_storage используют ON CONFLICT
upsert — повторный запуск builder'а на той же snapshot не создаёт
дубликатов. Это важно для resumable indexing'а в Phase 8.

## Производительность

На КА 2.5.25.92 (15k объектов, 24k модулей, 652k методов) ожидаемое
время полного билда: 10-20 минут (доминирует BSL parse). Для пилота
доступен `bsl_file_limit` чтобы оборвать раньше.

## Ограничения текущей версии

- CALLS резолвится только для same-module + CommonModule.Метод
  (Documents.X.Метод / Catalogs.X.Метод требуют менеджерных модулей —
  отложено в M-K2.5.5).
- USES игнорирует строковые литералы — может найти ложные срабатывания
  внутри комментариев / строк (низкий шум, ~1-2% по эмпирике пилота).
- READS_FROM считает каждую виртуальную таблицу регистра одним edge
  с attributes.virtual_kind (без separate edges по `Остатки` vs `Обороты`).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import aiosqlite

from app.knowledge.graph_storage import EdgeKind, NodeKind
from app.knowledge.graph_storage import insert_edge as _gs_insert_edge
from app.knowledge.graph_storage import insert_node as _gs_insert_node


# Bulk-wrapper'ы: commit=False для performance (на КА 2 с 600k операций
# per-op commit добавлял ~10-20 минут). Builder делает explicit
# `await db.commit()` на границах фаз и каждые N объектов в цикле.
async def insert_node(db, **kwargs):
    """Wrapper: insert_node без per-op commit. Используется только builder'ом."""
    return await _gs_insert_node(db, commit=False, **kwargs)


async def insert_edge(db, **kwargs):
    """Wrapper: insert_edge без per-op commit. Используется только builder'ом."""
    return await _gs_insert_edge(db, commit=False, **kwargs)


# Каждые N структурных объектов делаем flush — чтобы не держать большие
# WAL транзакции в памяти и иметь recoverable state при прерывании.
_BATCH_COMMIT_OBJECTS = 500
_BATCH_COMMIT_BSL_FILES = 50
from app.knowledge.typical.bsl_ast import parse_file
from app.knowledge.typical.bsl_models import BSLMethod, BSLModule
from app.knowledge.typical.query_parser import extract_queries_from_method
from app.knowledge.typical.xml_models import (
    MetadataConfiguration,
    MetadataKind,
    MetadataObject,
)
from app.knowledge.typical.xml_parser import (
    parse_configuration_tree,
    parse_rights_xml,
)

logger = logging.getLogger(__name__)


# ── Регулярки для извлечения ─────────────────────────────────────────


# Тип ссылки в реквизите: `СправочникСсылка.Контрагенты`,
# `ДокументСсылка.РеализацияТоваровУслуг`, и т.д.
# Захватываем суффикс (Catalog / Document / ...) + короткое имя.
_REFERENCE_TYPE_RE = re.compile(
    r"\b(СправочникСсылка|ДокументСсылка|ПеречислениеСсылка|"
    r"ПланВидовХарактеристикСсылка|ПланСчетовСсылка|ПланВидовРасчетаСсылка|"
    r"БизнесПроцессСсылка|ЗадачаСсылка|"
    r"CatalogRef|DocumentRef|EnumRef|"
    r"ChartOfCharacteristicTypesRef|ChartOfAccountsRef|ChartOfCalculationTypesRef|"
    r"BusinessProcessRef|TaskRef)"
    r"\.([А-Яа-яA-Za-z0-9_]+)"
)


# Маппинг суффиксов типов ссылок → MetadataKind.value.
_REF_TYPE_TO_KIND: dict[str, str] = {
    "СправочникСсылка": MetadataKind.CATALOG.value,
    "ДокументСсылка": MetadataKind.DOCUMENT.value,
    "ПеречислениеСсылка": MetadataKind.ENUM.value,
    "ПланВидовХарактеристикСсылка": MetadataKind.CHART_OF_CHARACTERISTIC_TYPES.value,
    "ПланСчетовСсылка": MetadataKind.CHART_OF_ACCOUNTS.value,
    "ПланВидовРасчетаСсылка": MetadataKind.CHART_OF_CALCULATION_TYPES.value,
    "БизнесПроцессСсылка": MetadataKind.BUSINESS_PROCESS.value,
    "ЗадачаСсылка": MetadataKind.TASK.value,
    "CatalogRef": MetadataKind.CATALOG.value,
    "DocumentRef": MetadataKind.DOCUMENT.value,
    "EnumRef": MetadataKind.ENUM.value,
    "ChartOfCharacteristicTypesRef": MetadataKind.CHART_OF_CHARACTERISTIC_TYPES.value,
    "ChartOfAccountsRef": MetadataKind.CHART_OF_ACCOUNTS.value,
    "ChartOfCalculationTypesRef": MetadataKind.CHART_OF_CALCULATION_TYPES.value,
    "BusinessProcessRef": MetadataKind.BUSINESS_PROCESS.value,
    "TaskRef": MetadataKind.TASK.value,
}


# USES: упоминание метаданных в BSL коде через коллекции.
# Например `Документы.РеализацияТоваровУслуг`, `Справочники.Контрагенты`.
_USES_RE = re.compile(
    r"\b(Документы|Справочники|Перечисления|"
    r"РегистрыНакопления|РегистрыСведений|РегистрыБухгалтерии|РегистрыРасчета|"
    r"ПланыСчетов|ПланыВидовХарактеристик|ПланыВидовРасчета|"
    r"БизнесПроцессы|Задачи|ОбщиеМодули|Отчеты|Обработки|"
    r"Documents|Catalogs|Enums|"
    r"AccumulationRegisters|InformationRegisters|AccountingRegisters|CalculationRegisters|"
    r"ChartsOfAccounts|ChartsOfCharacteristicTypes|ChartsOfCalculationTypes|"
    r"BusinessProcesses|Tasks|CommonModules|Reports|DataProcessors)"
    r"\.([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9_]*)"
)


# Маппинг префикса коллекции → MetadataKind.value.
_USES_PREFIX_TO_KIND: dict[str, str] = {
    "Документы": MetadataKind.DOCUMENT.value,
    "Справочники": MetadataKind.CATALOG.value,
    "Перечисления": MetadataKind.ENUM.value,
    "РегистрыНакопления": MetadataKind.ACCUMULATION_REGISTER.value,
    "РегистрыСведений": MetadataKind.INFORMATION_REGISTER.value,
    "РегистрыБухгалтерии": MetadataKind.ACCOUNTING_REGISTER.value,
    "РегистрыРасчета": MetadataKind.CALCULATION_REGISTER.value,
    "ПланыСчетов": MetadataKind.CHART_OF_ACCOUNTS.value,
    "ПланыВидовХарактеристик": MetadataKind.CHART_OF_CHARACTERISTIC_TYPES.value,
    "ПланыВидовРасчета": MetadataKind.CHART_OF_CALCULATION_TYPES.value,
    "БизнесПроцессы": MetadataKind.BUSINESS_PROCESS.value,
    "Задачи": MetadataKind.TASK.value,
    "ОбщиеМодули": MetadataKind.COMMON_MODULE.value,
    "Отчеты": MetadataKind.REPORT.value,
    "Обработки": MetadataKind.DATA_PROCESSOR.value,
    "Documents": MetadataKind.DOCUMENT.value,
    "Catalogs": MetadataKind.CATALOG.value,
    "Enums": MetadataKind.ENUM.value,
    "AccumulationRegisters": MetadataKind.ACCUMULATION_REGISTER.value,
    "InformationRegisters": MetadataKind.INFORMATION_REGISTER.value,
    "AccountingRegisters": MetadataKind.ACCOUNTING_REGISTER.value,
    "CalculationRegisters": MetadataKind.CALCULATION_REGISTER.value,
    "ChartsOfAccounts": MetadataKind.CHART_OF_ACCOUNTS.value,
    "ChartsOfCharacteristicTypes": MetadataKind.CHART_OF_CHARACTERISTIC_TYPES.value,
    "ChartsOfCalculationTypes": MetadataKind.CHART_OF_CALCULATION_TYPES.value,
    "BusinessProcesses": MetadataKind.BUSINESS_PROCESS.value,
    "Tasks": MetadataKind.TASK.value,
    "CommonModules": MetadataKind.COMMON_MODULE.value,
    "Reports": MetadataKind.REPORT.value,
    "DataProcessors": MetadataKind.DATA_PROCESSOR.value,
}


# WRITES_TO: движения регистров через `Движения.ИмяРегистра`.
_DVIZHENIYA_RE = re.compile(r"\bДвижения\.([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9_]*)")


# Маппинг русский префикс таблицы в BSL Query Language → MetadataKind.value
# (используется при резолве table.name из query_parser в metadata_by_qname,
# где ключи — `Document.Заказ`, а query parser возвращает `Документ.Заказ`).
_QUERY_TABLE_PREFIX_TO_KIND: dict[str, str] = {
    "Документ": MetadataKind.DOCUMENT.value,
    "Справочник": MetadataKind.CATALOG.value,
    "Перечисление": MetadataKind.ENUM.value,
    "РегистрНакопления": MetadataKind.ACCUMULATION_REGISTER.value,
    "РегистрСведений": MetadataKind.INFORMATION_REGISTER.value,
    "РегистрБухгалтерии": MetadataKind.ACCOUNTING_REGISTER.value,
    "РегистрРасчета": MetadataKind.CALCULATION_REGISTER.value,
    "ПланСчетов": MetadataKind.CHART_OF_ACCOUNTS.value,
    "ПланВидовХарактеристик": MetadataKind.CHART_OF_CHARACTERISTIC_TYPES.value,
    "ПланВидовРасчета": MetadataKind.CHART_OF_CALCULATION_TYPES.value,
    "БизнесПроцесс": MetadataKind.BUSINESS_PROCESS.value,
    "Задача": MetadataKind.TASK.value,
    "Отчет": MetadataKind.REPORT.value,
    "Обработка": MetadataKind.DATA_PROCESSOR.value,
    "ЖурналДокументов": MetadataKind.DOCUMENT_JOURNAL.value,
    "Константа": MetadataKind.CONSTANT.value,
    # Английские формы (для конфигураций в English locale)
    "Document": MetadataKind.DOCUMENT.value,
    "Catalog": MetadataKind.CATALOG.value,
    "Enum": MetadataKind.ENUM.value,
    "AccumulationRegister": MetadataKind.ACCUMULATION_REGISTER.value,
    "InformationRegister": MetadataKind.INFORMATION_REGISTER.value,
    "AccountingRegister": MetadataKind.ACCOUNTING_REGISTER.value,
    "CalculationRegister": MetadataKind.CALCULATION_REGISTER.value,
    "ChartOfAccounts": MetadataKind.CHART_OF_ACCOUNTS.value,
    "ChartOfCharacteristicTypes": MetadataKind.CHART_OF_CHARACTERISTIC_TYPES.value,
    "ChartOfCalculationTypes": MetadataKind.CHART_OF_CALCULATION_TYPES.value,
    "BusinessProcess": MetadataKind.BUSINESS_PROCESS.value,
    "Task": MetadataKind.TASK.value,
    "Report": MetadataKind.REPORT.value,
    "DataProcessor": MetadataKind.DATA_PROCESSOR.value,
    "DocumentJournal": MetadataKind.DOCUMENT_JOURNAL.value,
    "Constant": MetadataKind.CONSTANT.value,
}


def _normalize_query_table_qname(raw_qname: str) -> str | None:
    """`Документ.Заказ` → `Document.Заказ`; `Документ.Заказ.Товары` → `Document.Заказ.ТабличнаяЧасть.Товары`.

    Возвращает None если префикс не распознан (например, ВТ_*).
    """
    if not raw_qname or "." not in raw_qname:
        return None
    parts = raw_qname.split(".")
    prefix = parts[0]
    normalized_kind = _QUERY_TABLE_PREFIX_TO_KIND.get(prefix)
    if normalized_kind is None:
        return None
    if len(parts) == 2:
        # `Документ.Заказ` → `Document.Заказ`
        return f"{normalized_kind}.{parts[1]}"
    if len(parts) == 3:
        # `Документ.Заказ.Товары` → `Document.Заказ.ТабличнаяЧасть.Товары`
        return f"{normalized_kind}.{parts[1]}.ТабличнаяЧасть.{parts[2]}"
    # Длинные пути (вложенные ТЧ — не существует в 1С) — игнорируем
    return None


# CALLS — same-module call: голое имя метода + `(`.
# Чтобы не ловить ключевые слова (Если / Тогда / Цикл / ...), требуем
# хотя бы одну букву UPPERCASE в имени (методы 1С пишут CamelCase).
# И исключаем доступ к атрибутам через `.` перед именем.
_SAME_MODULE_CALL_RE = re.compile(
    r"(?<![\w.])([А-ЯA-Z][А-Яа-яA-Za-z0-9_]+)\s*\("
)


# CALLS — cross-module call: `ИмяМодуля.ИмяМетода(`.
_CROSS_MODULE_CALL_RE = re.compile(
    r"\b([А-ЯA-Z][А-Яа-яA-Za-z0-9_]+)\.([А-ЯA-Z][А-Яа-яA-Za-z0-9_]+)\s*\("
)


# Ключевые слова BSL которые не являются вызовами методов
# (фильтр для same-module CALLS).
_BSL_KEYWORDS: frozenset[str] = frozenset(
    [
        # Управляющие конструкции
        "Если", "Иначе", "ИначеЕсли", "Тогда", "КонецЕсли",
        "Для", "Каждого", "Из", "По", "Цикл", "КонецЦикла",
        "Пока", "Прервать", "Продолжить",
        "Попытка", "Исключение", "КонецПопытки", "ВызватьИсключение",
        "Возврат", "Перейти",
        # Объявления
        "Процедура", "Функция", "КонецПроцедуры", "КонецФункции",
        "Перем", "Экспорт", "Знач",
        # Литералы
        "Истина", "Ложь", "Неопределено", "Null", "NULL",
        # Операторы и др.
        "И", "Или", "Не", "Новый",
        "If", "Else", "ElseIf", "Then", "EndIf",
        "For", "Each", "In", "To", "Do", "EndDo",
        "While", "Break", "Continue",
        "Try", "Except", "EndTry", "Raise",
        "Return", "Goto",
        "Procedure", "Function", "EndProcedure", "EndFunction",
        "Var", "Export", "Val",
        "True", "False", "Undefined",
        "And", "Or", "Not", "New",
    ]
)


# ── Stats ────────────────────────────────────────────────────────────


@dataclass
class GraphBuildStats:
    """Аккумулятор метрик прогона builder'а."""

    nodes_inserted: int = 0
    edges_inserted: int = 0
    by_node_kind: dict[str, int] = field(default_factory=dict)
    by_edge_kind: dict[str, int] = field(default_factory=dict)
    metadata_objects: int = 0
    bsl_files_parsed: int = 0
    bsl_files_failed: int = 0
    bsl_files_skipped: int = 0
    methods_extracted: int = 0
    queries_extracted: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes_inserted": self.nodes_inserted,
            "edges_inserted": self.edges_inserted,
            "by_node_kind": dict(self.by_node_kind),
            "by_edge_kind": dict(self.by_edge_kind),
            "metadata_objects": self.metadata_objects,
            "bsl_files_parsed": self.bsl_files_parsed,
            "bsl_files_failed": self.bsl_files_failed,
            "bsl_files_skipped": self.bsl_files_skipped,
            "methods_extracted": self.methods_extracted,
            "queries_extracted": self.queries_extracted,
            "duration_seconds": round(self.duration_seconds, 3),
        }

    def _bump_node(self, kind: str) -> None:
        self.nodes_inserted += 1
        self.by_node_kind[kind] = self.by_node_kind.get(kind, 0) + 1

    def _bump_edge(self, kind: str) -> None:
        self.edges_inserted += 1
        self.by_edge_kind[kind] = self.by_edge_kind.get(kind, 0) + 1


# ── Индексы (резолверы) ──────────────────────────────────────────────


@dataclass
class _ConfigIndex:
    """Кеш быстрого резолва qualified_name / коротких имён → node_id.

    Заполняется в Phase B одновременно со вставкой структурных nodes.
    Используется в Phase C/D для построения edges без повторного
    SELECT'а из БД (это критично для производительности — 1М рёбер на
    КА 2 через find_node = ~10 минут лишних).
    """

    # qualified_name (Документ.X / CommonModule.Y) → node_id
    metadata_by_qname: dict[str, int] = field(default_factory=dict)
    # CommonModule.Y → node_id of body module (для CALLS резолва)
    common_module_body_module: dict[str, int] = field(default_factory=dict)
    # short_name регистра → qualified_name (для WRITES_TO резолва).
    # Если есть коллизия (один и тот же short_name в РегистрНакопления +
    # РегистрСведений) — берём первый встреченный, остальные в conflicts.
    register_short_to_qname: dict[str, str] = field(default_factory=dict)
    register_short_conflicts: list[str] = field(default_factory=list)


# ── Public API ───────────────────────────────────────────────────────


async def _build_role_rls_edges(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    config: MetadataConfiguration,
    snapshot_root: Path,
    index: _ConfigIndex,
    stats: GraphBuildStats,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> None:
    """Phase E (M-K3.17.2): Role-узлы + RESTRICTS-рёбра из Rights.xml.

    Кладём ТОЛЬКО права с RLS-условием (restrictionByCondition) — это
    «интересные» ограничения для RLS-tracer («почему Иванов не видит X»).
    Плоские грантты (Read=true без условия) пропускаем: их ~149/роль →
    взрыв графа, а «кто имеет доступ» лучше отвечает живой MCP
    get_access_rights. Ребро: Role -RESTRICTS-> MetadataObject,
    attrs={right, condition}.
    """
    roles = [o for o in config.metadata_objects if o.kind == "Role"]
    total = len(roles)
    if progress_callback:
        progress_callback("roles_rls", 0, total)

    for i, role in enumerate(roles, start=1):
        rights_path = snapshot_root / "Roles" / role.name / "Ext" / "Rights.xml"
        if not rights_path.is_file():
            continue
        try:
            role_rights = parse_rights_xml(rights_path)
        except Exception:  # noqa: BLE001 — битый Rights.xml не валит весь билд
            logger.debug("Rights.xml parse failed для роли %s", role.name, exc_info=True)
            continue

        restricted = [r for r in role_rights if r.condition]
        if not restricted:
            continue

        try:
            rel_src = str(rights_path.relative_to(snapshot_root))
        except ValueError:
            rel_src = None
        role_id = await _gs_insert_node(
            db,
            channel_id=channel_id,
            node_kind=NodeKind.ROLE.value,
            qualified_name=f"Role.{role.name}",
            source_path=rel_src,
            commit=False,
        )
        stats._bump_node(NodeKind.ROLE.value)

        for rr in restricted:
            target_id = index.metadata_by_qname.get(rr.object_name)
            if target_id is None:
                continue  # объект вне индекса (Subsystem.*, вложенный) — пропуск
            await _gs_insert_edge(
                db,
                src_id=role_id,
                dst_id=target_id,
                edge_kind=EdgeKind.RESTRICTS.value,
                attributes={"right": rr.right_name, "condition": rr.condition},
                commit=False,
            )
            stats._bump_edge(EdgeKind.RESTRICTS.value)

        if progress_callback:
            progress_callback("roles_rls", i, total)

    await db.commit()


async def build_typical_graph(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    snapshot_root: str | Path,
    skip_kinds: set[MetadataKind] | None = None,
    bsl_file_limit: int | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> GraphBuildStats:
    """Полный pipeline построения графа поверх типовой.

    Args:
        db: async aiosqlite connection (БД уже с применённой миграцией v17).
        channel_id: namespace типовой (например `_ka2_25_92`).
        snapshot_root: путь к корню выгрузки `DumpConfigToFiles` (там
            должен быть `Configuration.xml`).
        skip_kinds: типы метаданных которые пропускаем (для отладки).
        bsl_file_limit: ограничение количества .bsl модулей (для пилотов).
            None = парсим все.
        progress_callback: опциональный callback `(phase, current, total)`
            для прогресс-бара / логирования.

    Returns:
        GraphBuildStats с агрегатами.

    Raises:
        FileNotFoundError если snapshot_root не существует или Configuration.xml нет.
    """
    snapshot_root = Path(snapshot_root)
    if not snapshot_root.exists():
        raise FileNotFoundError(f"snapshot_root не существует: {snapshot_root}")
    config_xml = snapshot_root / "Configuration.xml"
    if not config_xml.exists():
        raise FileNotFoundError(f"Configuration.xml не найден в {snapshot_root}")

    stats = GraphBuildStats()
    t0 = time.monotonic()

    # Phase A: parse XML tree
    if progress_callback:
        progress_callback("parse_xml", 0, 1)
    config = parse_configuration_tree(snapshot_root, skip_kinds=skip_kinds)
    stats.metadata_objects = len(config.metadata_objects)
    if progress_callback:
        progress_callback("parse_xml", 1, 1)

    # Phase B: структурные nodes + CONTAINS edges (XML)
    index = await _insert_structural_nodes(
        db, channel_id=channel_id, config=config, stats=stats,
        progress_callback=progress_callback,
    )

    # Phase C: REFERENCES edges из типов реквизитов
    await _build_references_edges(
        db, channel_id=channel_id, config=config, index=index, stats=stats,
        progress_callback=progress_callback,
    )

    # Phase D: BSL модули → Method nodes + CALLS/USES/WRITES_TO/READS_FROM
    await _build_bsl_edges(
        db,
        channel_id=channel_id,
        config=config,
        snapshot_root=snapshot_root,
        index=index,
        stats=stats,
        bsl_file_limit=bsl_file_limit,
        progress_callback=progress_callback,
    )

    # Phase E: Role nodes + RESTRICTS edges из Rights.xml (RLS, M-K3.17.2)
    await _build_role_rls_edges(
        db,
        channel_id=channel_id,
        config=config,
        snapshot_root=snapshot_root,
        index=index,
        stats=stats,
        progress_callback=progress_callback,
    )

    stats.duration_seconds = time.monotonic() - t0
    logger.info(
        "graph build done: %d nodes, %d edges, %d files parsed, duration=%.1fs",
        stats.nodes_inserted, stats.edges_inserted,
        stats.bsl_files_parsed, stats.duration_seconds,
    )
    return stats


# ── Phase B: структура (CONTAINS) ────────────────────────────────────


async def _insert_structural_nodes(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    config: MetadataConfiguration,
    stats: GraphBuildStats,
    progress_callback: Callable[[str, int, int], None] | None,
) -> _ConfigIndex:
    """Вставляет MetadataObject + Attribute + TabularSection + Module nodes.

    Возвращает индекс для последующих фаз.
    """
    index = _ConfigIndex()
    total = len(config.metadata_objects)

    register_kinds = {
        MetadataKind.ACCUMULATION_REGISTER.value,
        MetadataKind.INFORMATION_REGISTER.value,
        MetadataKind.ACCOUNTING_REGISTER.value,
        MetadataKind.CALCULATION_REGISTER.value,
    }

    for i, obj in enumerate(config.metadata_objects, start=1):
        # MetadataObject node
        obj_qname = obj.qualified_name
        obj_node_id = await insert_node(
            db,
            channel_id=channel_id,
            node_kind=NodeKind.METADATA_OBJECT.value,
            qualified_name=obj_qname,
            source_path=obj.source_path,
            attributes={
                "name": obj.name,
                "kind": obj.kind,
                "uuid": obj.uuid,
                "comment": obj.comment,
            },
        )
        stats._bump_node(NodeKind.METADATA_OBJECT.value)
        index.metadata_by_qname[obj_qname] = obj_node_id

        # Регистры — для WRITES_TO резолва нужно знать short_name → qname
        if obj.kind in register_kinds:
            if obj.name in index.register_short_to_qname:
                # Коллизия (один short_name в нескольких типах регистров).
                # Сохраняем первый встреченный, отмечаем конфликт.
                if obj.name not in index.register_short_conflicts:
                    index.register_short_conflicts.append(obj.name)
            else:
                index.register_short_to_qname[obj.name] = obj_qname

        # Атрибуты / измерения / ресурсы (на уровне объекта)
        for attr in (*obj.attributes, *obj.dimensions, *obj.resources):
            attr_qname = f"{obj_qname}.Реквизит.{attr.name}"
            attr_node_id = await insert_node(
                db,
                channel_id=channel_id,
                node_kind=NodeKind.ATTRIBUTE.value,
                qualified_name=attr_qname,
                source_path=obj.source_path,
                attributes={
                    "name": attr.name,
                    "type_definition": attr.type_definition,
                    "length": attr.length,
                    "precision": attr.precision,
                    "indexed": attr.indexed,
                    "fill_check": attr.fill_check,
                },
            )
            stats._bump_node(NodeKind.ATTRIBUTE.value)
            index.metadata_by_qname[attr_qname] = attr_node_id

            await insert_edge(
                db,
                src_id=obj_node_id,
                dst_id=attr_node_id,
                edge_kind=EdgeKind.CONTAINS.value,
            )
            stats._bump_edge(EdgeKind.CONTAINS.value)

        # Табличные части + их реквизиты
        for ts in obj.tabular_sections:
            ts_qname = f"{obj_qname}.ТабличнаяЧасть.{ts.name}"
            ts_node_id = await insert_node(
                db,
                channel_id=channel_id,
                node_kind=NodeKind.TABULAR_SECTION.value,
                qualified_name=ts_qname,
                source_path=obj.source_path,
                attributes={"name": ts.name, "comment": ts.comment},
            )
            stats._bump_node(NodeKind.TABULAR_SECTION.value)
            index.metadata_by_qname[ts_qname] = ts_node_id

            await insert_edge(
                db,
                src_id=obj_node_id,
                dst_id=ts_node_id,
                edge_kind=EdgeKind.CONTAINS.value,
            )
            stats._bump_edge(EdgeKind.CONTAINS.value)

            for attr in ts.attributes:
                attr_qname = f"{ts_qname}.Реквизит.{attr.name}"
                attr_node_id = await insert_node(
                    db,
                    channel_id=channel_id,
                    node_kind=NodeKind.ATTRIBUTE.value,
                    qualified_name=attr_qname,
                    source_path=obj.source_path,
                    attributes={
                        "name": attr.name,
                        "type_definition": attr.type_definition,
                        "length": attr.length,
                        "precision": attr.precision,
                    },
                )
                stats._bump_node(NodeKind.ATTRIBUTE.value)
                index.metadata_by_qname[attr_qname] = attr_node_id

                await insert_edge(
                    db,
                    src_id=ts_node_id,
                    dst_id=attr_node_id,
                    edge_kind=EdgeKind.CONTAINS.value,
                )
                stats._bump_edge(EdgeKind.CONTAINS.value)

        # BSL модули. Уникальность qualified_name: object-level модули
        # (ObjectModule/ManagerModule/CommonModuleBody) — `{obj}.{kind}`,
        # форменные/командные — `{obj}.Forms.<FormName>.{kind}` /
        # `{obj}.Commands.<CmdName>.{kind}` — иначе при 5 формах с
        # FormModule все 5 nodes сворачиваются в одну через UNIQUE.
        for mod in obj.modules:
            mod_qname = _module_qualified_name(obj_qname, mod)
            mod_node_id = await insert_node(
                db,
                channel_id=channel_id,
                node_kind=NodeKind.MODULE.value,
                qualified_name=mod_qname,
                source_path=mod.relative_path,
                attributes={
                    "module_kind": mod.kind,
                    "line_count": mod.line_count,
                },
            )
            stats._bump_node(NodeKind.MODULE.value)
            index.metadata_by_qname[mod_qname] = mod_node_id

            await insert_edge(
                db,
                src_id=obj_node_id,
                dst_id=mod_node_id,
                edge_kind=EdgeKind.CONTAINS.value,
            )
            stats._bump_edge(EdgeKind.CONTAINS.value)

            # CommonModule имеет один модуль — `CommonModuleBody`.
            # Сохраняем его node_id для резолва cross-module CALLS.
            if obj.kind == MetadataKind.COMMON_MODULE.value:
                index.common_module_body_module[obj.name] = mod_node_id

        if progress_callback and (i % 100 == 0 or i == total):
            progress_callback("structural", i, total)

        # Batch commit каждые N объектов чтобы не держать огромную
        # незакрытую транзакцию (WAL grows).
        if i % _BATCH_COMMIT_OBJECTS == 0:
            await db.commit()

    await db.commit()  # финальный flush Phase B
    return index


# ── Phase C: REFERENCES edges (типы реквизитов) ──────────────────────


async def _build_references_edges(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    config: MetadataConfiguration,
    index: _ConfigIndex,
    stats: GraphBuildStats,
    progress_callback: Callable[[str, int, int], None] | None,
) -> None:
    """REFERENCES edges из type_definition реквизитов.

    Пример: `Реквизит Контрагент` с типом `СправочникСсылка.Контрагенты` →
    edge Attribute(Контрагент) REFERENCES MetadataObject(Справочник.Контрагенты).
    """
    total = len(config.metadata_objects)

    for i, obj in enumerate(config.metadata_objects, start=1):
        obj_qname = obj.qualified_name

        # Атрибуты / измерения / ресурсы объекта
        for attr in (*obj.attributes, *obj.dimensions, *obj.resources):
            attr_qname = f"{obj_qname}.Реквизит.{attr.name}"
            await _emit_references_from_type_def(
                db, channel_id=channel_id, src_attr_qname=attr_qname,
                type_definition=attr.type_definition, index=index, stats=stats,
            )

        # Реквизиты ТЧ
        for ts in obj.tabular_sections:
            ts_qname = f"{obj_qname}.ТабличнаяЧасть.{ts.name}"
            for attr in ts.attributes:
                attr_qname = f"{ts_qname}.Реквизит.{attr.name}"
                await _emit_references_from_type_def(
                    db, channel_id=channel_id, src_attr_qname=attr_qname,
                    type_definition=attr.type_definition, index=index, stats=stats,
                )

        if progress_callback and (i % 200 == 0 or i == total):
            progress_callback("references", i, total)

        if i % _BATCH_COMMIT_OBJECTS == 0:
            await db.commit()

    await db.commit()  # финальный flush Phase C


async def _emit_references_from_type_def(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    src_attr_qname: str,
    type_definition: str,
    index: _ConfigIndex,
    stats: GraphBuildStats,
) -> None:
    """Парсит type_definition и эмитит REFERENCES edges."""
    if not type_definition:
        return

    src_node_id = index.metadata_by_qname.get(src_attr_qname)
    if src_node_id is None:
        return

    seen: set[tuple[int, int]] = set()
    for match in _REFERENCE_TYPE_RE.finditer(type_definition):
        ref_type, target_short_name = match.group(1), match.group(2)
        target_kind = _REF_TYPE_TO_KIND.get(ref_type)
        if target_kind is None:
            continue
        target_qname = f"{target_kind}.{target_short_name}"
        target_node_id = index.metadata_by_qname.get(target_qname)
        if target_node_id is None:
            continue
        if src_node_id == target_node_id:
            # self-loop — пропускаем (insert_edge тоже бросит ошибку)
            continue
        pair = (src_node_id, target_node_id)
        if pair in seen:
            continue
        seen.add(pair)
        await insert_edge(
            db,
            src_id=src_node_id,
            dst_id=target_node_id,
            edge_kind=EdgeKind.REFERENCES.value,
        )
        stats._bump_edge(EdgeKind.REFERENCES.value)


# ── Phase D: BSL модули → Method nodes + поведенческие edges ─────────


async def _build_bsl_edges(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    config: MetadataConfiguration,
    snapshot_root: Path,
    index: _ConfigIndex,
    stats: GraphBuildStats,
    bsl_file_limit: int | None,
    progress_callback: Callable[[str, int, int], None] | None,
) -> None:
    """Для каждого .bsl модуля: парсим методы, эмитим CONTAINS + поведенческие edges."""
    # Собираем список модулей сразу — для прогресс-бара и лимита.
    bsl_tasks: list[tuple[MetadataObject, str, str]] = []  # (obj, module_kind, mod_qname)
    for obj in config.metadata_objects:
        for mod in obj.modules:
            mod_qname = _module_qualified_name(obj.qualified_name, mod)
            bsl_tasks.append((obj, mod.relative_path, mod_qname))

    total = len(bsl_tasks)
    if bsl_file_limit is not None:
        total = min(total, bsl_file_limit)

    # Set имён common modules для cross-module CALLS резолва
    common_module_names: set[str] = set(index.common_module_body_module.keys())

    for i, (obj, mod_relpath, mod_qname) in enumerate(bsl_tasks, start=1):
        if bsl_file_limit is not None and i > bsl_file_limit:
            break

        mod_node_id = index.metadata_by_qname.get(mod_qname)
        if mod_node_id is None:
            # Структурный node не создался (баг?) — пропускаем
            stats.bsl_files_skipped += 1
            continue

        full_path = snapshot_root / mod_relpath
        if not full_path.exists():
            stats.bsl_files_skipped += 1
            continue

        try:
            bsl_module = parse_file(full_path)
        except Exception as exc:  # noqa: BLE001
            logger.debug("BSL parse failed: %s — %s", full_path, exc)
            stats.bsl_files_failed += 1
            continue

        stats.bsl_files_parsed += 1

        # CONTAINS Method
        method_node_ids: dict[str, int] = {}
        for method in bsl_module.methods:
            method_qname = f"{mod_qname}.{method.name}"
            method_node_id = await insert_node(
                db,
                channel_id=channel_id,
                node_kind=NodeKind.METHOD.value,
                qualified_name=method_qname,
                source_path=mod_relpath,
                attributes={
                    "name": method.name,
                    "kind": method.kind,
                    "is_exported": method.is_exported,
                    "compile_directive": method.compile_directive,
                    "param_count": len(method.parameters),
                    "line_start": method.line_start,
                    "line_end": method.line_end,
                    "customization_marker": method.customization_marker,
                },
            )
            stats._bump_node(NodeKind.METHOD.value)
            stats.methods_extracted += 1
            method_node_ids[method.name] = method_node_id

            await insert_edge(
                db,
                src_id=mod_node_id,
                dst_id=method_node_id,
                edge_kind=EdgeKind.CONTAINS.value,
            )
            stats._bump_edge(EdgeKind.CONTAINS.value)

        # Для каждого метода: CALLS / USES / WRITES_TO / READS_FROM
        for method in bsl_module.methods:
            method_node_id = method_node_ids.get(method.name)
            if method_node_id is None:
                continue
            await _emit_method_behavior_edges(
                db,
                channel_id=channel_id,
                method=method,
                method_node_id=method_node_id,
                method_node_ids_same_module=method_node_ids,
                common_module_names=common_module_names,
                index=index,
                stats=stats,
            )

        if progress_callback and (i % 50 == 0 or i == total):
            progress_callback("bsl", i, total)

        if i % _BATCH_COMMIT_BSL_FILES == 0:
            await db.commit()

    await db.commit()  # финальный flush Phase D


async def _emit_method_behavior_edges(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    method: BSLMethod,
    method_node_id: int,
    method_node_ids_same_module: dict[str, int],
    common_module_names: set[str],
    index: _ConfigIndex,
    stats: GraphBuildStats,
) -> None:
    """Эмитит CALLS / USES / WRITES_TO / READS_FROM для одного метода."""
    body = method.body_source
    if not body:
        return

    # Дедуп per-method — один edge на пару (method, target), даже если в
    # коде несколько вызовов.
    emitted_calls: set[int] = set()
    emitted_uses: set[int] = set()
    emitted_writes: set[int] = set()
    emitted_reads: set[int] = set()

    # ── CALLS: same-module ─────────────────────────────────────────
    for match in _SAME_MODULE_CALL_RE.finditer(body):
        callee = match.group(1)
        if callee in _BSL_KEYWORDS:
            continue
        target_node_id = method_node_ids_same_module.get(callee)
        if target_node_id is None or target_node_id == method_node_id:
            continue
        if target_node_id in emitted_calls:
            continue
        emitted_calls.add(target_node_id)
        await insert_edge(
            db,
            src_id=method_node_id,
            dst_id=target_node_id,
            edge_kind=EdgeKind.CALLS.value,
            attributes={"resolution": "same_module"},
        )
        stats._bump_edge(EdgeKind.CALLS.value)

    # ── CALLS: cross-module через CommonModule ─────────────────────
    for match in _CROSS_MODULE_CALL_RE.finditer(body):
        module_name, callee = match.group(1), match.group(2)
        if module_name not in common_module_names:
            continue
        # Резолв target method node
        target_module_qname = (
            f"{MetadataKind.COMMON_MODULE.value}.{module_name}"
            f".{_common_module_kind_name()}"
        )
        target_method_qname = f"{target_module_qname}.{callee}"
        target_node_id = index.metadata_by_qname.get(target_method_qname)
        if target_node_id is None or target_node_id == method_node_id:
            continue
        if target_node_id in emitted_calls:
            continue
        emitted_calls.add(target_node_id)
        await insert_edge(
            db,
            src_id=method_node_id,
            dst_id=target_node_id,
            edge_kind=EdgeKind.CALLS.value,
            attributes={"resolution": "common_module"},
        )
        stats._bump_edge(EdgeKind.CALLS.value)

    # ── USES: метаданные через коллекции ──────────────────────────
    for match in _USES_RE.finditer(body):
        prefix, target_short_name = match.group(1), match.group(2)
        target_kind = _USES_PREFIX_TO_KIND.get(prefix)
        if target_kind is None:
            continue
        target_qname = f"{target_kind}.{target_short_name}"
        target_node_id = index.metadata_by_qname.get(target_qname)
        if target_node_id is None or target_node_id == method_node_id:
            continue
        if target_node_id in emitted_uses:
            continue
        emitted_uses.add(target_node_id)
        await insert_edge(
            db,
            src_id=method_node_id,
            dst_id=target_node_id,
            edge_kind=EdgeKind.USES.value,
        )
        stats._bump_edge(EdgeKind.USES.value)

    # ── WRITES_TO: движения регистров ─────────────────────────────
    for match in _DVIZHENIYA_RE.finditer(body):
        register_short_name = match.group(1)
        target_qname = index.register_short_to_qname.get(register_short_name)
        if target_qname is None:
            continue
        target_node_id = index.metadata_by_qname.get(target_qname)
        if target_node_id is None or target_node_id == method_node_id:
            continue
        if target_node_id in emitted_writes:
            continue
        emitted_writes.add(target_node_id)
        await insert_edge(
            db,
            src_id=method_node_id,
            dst_id=target_node_id,
            edge_kind=EdgeKind.WRITES_TO.value,
            attributes={"resolution": "dvizheniya"},
        )
        stats._bump_edge(EdgeKind.WRITES_TO.value)

    # ── READS_FROM: запросы через query_parser ────────────────────
    queries = extract_queries_from_method(
        body,
        source_method=method.name,
        method_line_offset=max(method.line_start - 1, 0),
    )
    stats.queries_extracted += len(queries)

    for query in queries:
        # Физические таблицы. query_parser возвращает имена как они
        # написаны в запросе — `Документ.X` (русский синглуляр), но
        # index.metadata_by_qname использует `Document.X` (английский
        # MetadataKind value). Нормализуем перед lookup.
        for table in query.tables:
            if table.is_temp_table:
                continue
            normalized = _normalize_query_table_qname(table.name)
            if normalized is None:
                continue
            target_node_id = index.metadata_by_qname.get(normalized)
            if target_node_id is None or target_node_id == method_node_id:
                continue
            if target_node_id in emitted_reads:
                continue
            emitted_reads.add(target_node_id)
            await insert_edge(
                db,
                src_id=method_node_id,
                dst_id=target_node_id,
                edge_kind=EdgeKind.READS_FROM.value,
                attributes={"via": "physical_table"},
            )
            stats._bump_edge(EdgeKind.READS_FROM.value)

        # Виртуальные таблицы регистров. Тот же нормализатор —
        # vt.qualified_name это `РегистрНакопления.X`, нужно `AccumulationRegister.X`.
        for vt in query.virtual_tables:
            normalized = _normalize_query_table_qname(vt.qualified_name)
            if normalized is None:
                continue
            target_node_id = index.metadata_by_qname.get(normalized)
            if target_node_id is None or target_node_id == method_node_id:
                continue
            if target_node_id in emitted_reads:
                continue
            emitted_reads.add(target_node_id)
            await insert_edge(
                db,
                src_id=method_node_id,
                dst_id=target_node_id,
                edge_kind=EdgeKind.READS_FROM.value,
                attributes={"via": "virtual_table", "virtual_kind": vt.virtual_kind},
            )
            stats._bump_edge(EdgeKind.READS_FROM.value)


def _common_module_kind_name() -> str:
    """Возвращает строку `ModuleKind.COMMON_MODULE_BODY.value` без import cycle."""
    return "CommonModuleBody"


def _module_qualified_name(obj_qname: str, mod) -> str:
    """Уникальный qname модуля с учётом форм и команд.

    relative_path вида:
    - `Documents/X/Ext/ObjectModule.bsl` → `Document.X.ObjectModule`
    - `Documents/X/Forms/Ф/Ext/Form/Module.bsl` → `Document.X.Forms.Ф.FormModule`
    - `Documents/X/Forms/Ф/Ext/CommandModule.bsl` → `Document.X.Forms.Ф.CommandModule`
    - `Documents/X/Commands/К/Ext/CommandModule.bsl` → `Document.X.Commands.К.CommandModule`
    """
    rel = (mod.relative_path or "").replace("\\", "/")
    parts = rel.split("/")
    # Найдём Forms/<Name> или Commands/<Name> в пути
    for marker, prefix in (("Forms", "Forms"), ("Commands", "Commands")):
        if marker in parts:
            idx = parts.index(marker)
            if idx + 1 < len(parts):
                name = parts[idx + 1]
                return f"{obj_qname}.{prefix}.{name}.{mod.kind}"
    # Object-level
    return f"{obj_qname}.{mod.kind}"
