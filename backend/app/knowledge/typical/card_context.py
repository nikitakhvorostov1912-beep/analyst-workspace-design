"""Card Context Builder (M-K2.5.5).

Собирает компактный контекст для LLM-промпта по одному
MetadataObject из уже построенного графа:

- основные атрибуты (с типами ссылок)
- табличные части
- модули + ключевые методы (по handler-именам)
- WRITES_TO / READS_FROM движения регистров
- top-N CALLS из методов
- reverse REFERENCES — кто ссылается обратно

Контекст должен укладываться в ~3-4 тыс токенов (~10-12 кБ JSON).
Для этого:
- атрибуты ограничены 30 шт (приоритет: REFERENCES → fill_check → остальное)
- ТЧ ограничены 10 шт, внутри них — 20 атрибутов max
- методы ограничены 25 шт (приоритет: handler events → exported → остальное)
- top-N CALLS = 30 на весь объект

## Контекст для LLM (формат)

```python
CardContext(
    object_qualified_name="Document.РеализацияТоваровУслуг",
    object_kind="Document",
    object_attributes={"name": ..., "comment": ..., "uuid": ...},
    attributes=[CardContextAttribute(...), ...],
    tabular_sections=[CardContextTabularSection(...)],
    handler_methods=["ОбработкаПроведения", "ПередЗаписью", ...],
    writes_to=["AccumulationRegister.X", ...],
    reads_from=[("AccumulationRegister.X", "Остатки"), ...],
    top_calls=["CommonModule.Y.Метод1", ...],
    referenced_by=["Document.Z (Реквизит)", ...],
)
```

## Идемпотентность

Все запросы идут через graph_storage / card_storage без побочных
эффектов. Builder — pure function от (db, channel_id, qname).
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import aiosqlite

from app.knowledge.graph_storage import EdgeKind, NodeKind

logger = logging.getLogger(__name__)


# ── Конфиг компактности ──────────────────────────────────────────────


MAX_ATTRIBUTES = 30
MAX_TABULAR_SECTIONS = 10
MAX_TS_ATTRIBUTES = 20
MAX_METHODS = 25
MAX_TOP_CALLS = 30
MAX_REVERSE_REFS = 25


# Имена «handler»-методов, приоритетных для документов / регистров /
# справочников. При сборке методов сначала ищем по этим именам, потом
# добираем остальное.
_HANDLER_METHOD_NAMES: frozenset[str] = frozenset(
    [
        # Document / Catalog объектные
        "ПередЗаписью", "ПриЗаписи", "ОбработкаЗаполнения",
        "ОбработкаПроверкиЗаполнения", "ПриКопировании", "ПередУдалением",
        "ОбработкаПроведения", "ОбработкаУдаленияПроведения",
        # Менеджерные
        "ПолучитьФормуВыбора", "ПолучитьФорму", "ПечатьДокументов",
        # Формы
        "ПриСозданииНаСервере", "ПриОткрытии", "ПередЗакрытием",
        "ПередЗаписьюНаСервере", "ПриЗаписиНаСервере",
        # Запись регистра
        "ПередЗаписьюНабораЗаписей", "ПриЗаписиНабораЗаписей",
        # English варианты для EDT-конфигураций
        "OnWrite", "BeforeWrite", "Filling", "FillCheckProcessing",
        "Posting", "UndoPosting",
        "OnCreateAtServer", "OnOpen", "BeforeClose",
    ]
)


# ── Dataclasses ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CardContextAttribute:
    name: str
    type_definition: str = ""
    indexed: bool = False
    fill_check: bool = False
    references: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type_definition": self.type_definition,
            "indexed": self.indexed,
            "fill_check": self.fill_check,
            "references": list(self.references),
        }


@dataclass(frozen=True, slots=True)
class CardContextTabularSection:
    name: str
    attributes: tuple[CardContextAttribute, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "attributes": [a.to_dict() for a in self.attributes],
        }


@dataclass(frozen=True, slots=True)
class CardContextMethod:
    name: str
    module_kind: str
    is_exported: bool
    is_handler: bool
    compile_directive: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "module_kind": self.module_kind,
            "is_exported": self.is_exported,
            "is_handler": self.is_handler,
            "compile_directive": self.compile_directive,
        }


@dataclass(frozen=True, slots=True)
class CardContextRegisterRead:
    register_qname: str
    via: str  # "virtual_table" | "physical_table"
    virtual_kind: str | None = None  # для virtual_table

    def to_dict(self) -> dict[str, Any]:
        return {
            "register": self.register_qname,
            "via": self.via,
            "virtual_kind": self.virtual_kind,
        }


@dataclass(frozen=True, slots=True)
class CardContext:
    """Полный контекст одного объекта для LLM."""

    object_qualified_name: str
    object_kind: str
    object_name: str
    object_uuid: str | None
    object_comment: str
    object_source_path: str | None

    attributes: tuple[CardContextAttribute, ...] = field(default_factory=tuple)
    tabular_sections: tuple[CardContextTabularSection, ...] = field(default_factory=tuple)
    methods: tuple[CardContextMethod, ...] = field(default_factory=tuple)
    writes_to: tuple[str, ...] = field(default_factory=tuple)
    reads_from: tuple[CardContextRegisterRead, ...] = field(default_factory=tuple)
    top_calls: tuple[str, ...] = field(default_factory=tuple)
    referenced_by: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_qualified_name": self.object_qualified_name,
            "object_kind": self.object_kind,
            "object_name": self.object_name,
            "object_uuid": self.object_uuid,
            "object_comment": self.object_comment,
            "object_source_path": self.object_source_path,
            "attributes": [a.to_dict() for a in self.attributes],
            "tabular_sections": [t.to_dict() for t in self.tabular_sections],
            "methods": [m.to_dict() for m in self.methods],
            "writes_to": list(self.writes_to),
            "reads_from": [r.to_dict() for r in self.reads_from],
            "top_calls": list(self.top_calls),
            "referenced_by": list(self.referenced_by),
        }

    def to_compact_json(self) -> str:
        """Компактный JSON для передачи в LLM."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    def compute_source_hash(self) -> str:
        """SHA-256 от компактного контекста.

        Используется для skip-если-неизменился в card_storage.
        """
        return hashlib.sha256(self.to_compact_json().encode("utf-8")).hexdigest()


# ── Public API ───────────────────────────────────────────────────────


async def build_card_context(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    object_qualified_name: str,
) -> CardContext | None:
    """Собирает контекст для одного MetadataObject.

    Возвращает None если объект не найден в графе.
    """
    # 1. Найти сам MetadataObject
    obj_row = await _fetch_one(
        db,
        """
        SELECT id, qualified_name, source_path, attributes
        FROM graph_nodes
        WHERE channel_id = ? AND qualified_name = ? AND node_kind = ?
        """,
        (channel_id, object_qualified_name, NodeKind.METADATA_OBJECT.value),
    )
    if obj_row is None:
        return None

    obj_id = int(obj_row[0])
    obj_attrs = _json_loads(obj_row[3])
    object_name = obj_attrs.get("name", "")
    object_uuid = obj_attrs.get("uuid")
    object_comment = obj_attrs.get("comment", "") or ""
    object_kind = obj_attrs.get("kind", "")

    # 2. Прямые children — Attribute / TabularSection / Module
    children = await _fetch_all(
        db,
        """
        SELECT n.id, n.node_kind, n.qualified_name, n.attributes
        FROM graph_nodes n
        JOIN graph_edges e ON e.dst_id = n.id
        WHERE e.src_id = ? AND e.edge_kind = ?
        """,
        (obj_id, EdgeKind.CONTAINS.value),
    )

    attribute_rows: list[tuple] = []
    ts_rows: list[tuple] = []
    module_rows: list[tuple] = []

    for cid, ckind, cqname, cattrs in children:
        if ckind == NodeKind.ATTRIBUTE.value:
            attribute_rows.append((cid, cqname, cattrs))
        elif ckind == NodeKind.TABULAR_SECTION.value:
            ts_rows.append((cid, cqname, cattrs))
        elif ckind == NodeKind.MODULE.value:
            module_rows.append((cid, cqname, cattrs))

    # 3. Атрибуты + их REFERENCES
    attributes = await _build_attribute_context(db, attribute_rows, limit=MAX_ATTRIBUTES)

    # 4. ТЧ + их атрибуты
    tabular_sections = await _build_tabular_section_context(db, ts_rows)

    # 5. Методы модулей + WRITES_TO / READS_FROM / CALLS / USES
    methods: list[CardContextMethod] = []
    writes_to: set[str] = set()
    reads_from_list: list[CardContextRegisterRead] = []
    reads_from_seen: set[tuple[str, str]] = set()
    top_calls_counter: dict[str, int] = {}

    for mod_id, mod_qname, mod_attrs_raw in module_rows:
        mod_attrs = _json_loads(mod_attrs_raw)
        module_kind = mod_attrs.get("module_kind", "")

        method_children = await _fetch_all(
            db,
            """
            SELECT n.id, n.qualified_name, n.attributes
            FROM graph_nodes n
            JOIN graph_edges e ON e.dst_id = n.id
            WHERE e.src_id = ? AND e.edge_kind = ?
            """,
            (mod_id, EdgeKind.CONTAINS.value),
        )

        for method_id, method_qname, method_attrs_raw in method_children:
            method_attrs = _json_loads(method_attrs_raw)
            method_name = method_attrs.get("name", "")
            is_handler = method_name in _HANDLER_METHOD_NAMES
            methods.append(
                CardContextMethod(
                    name=method_name,
                    module_kind=module_kind,
                    is_exported=bool(method_attrs.get("is_exported")),
                    is_handler=is_handler,
                    compile_directive=method_attrs.get("compile_directive"),
                )
            )

            # WRITES_TO от этого метода
            wt_targets = await _fetch_all(
                db,
                """
                SELECT n.qualified_name FROM graph_nodes n
                JOIN graph_edges e ON e.dst_id = n.id
                WHERE e.src_id = ? AND e.edge_kind = ?
                """,
                (method_id, EdgeKind.WRITES_TO.value),
            )
            for (target_qname,) in wt_targets:
                writes_to.add(target_qname)

            # READS_FROM от этого метода
            rf_targets = await _fetch_all(
                db,
                """
                SELECT n.qualified_name, e.attributes
                FROM graph_nodes n
                JOIN graph_edges e ON e.dst_id = n.id
                WHERE e.src_id = ? AND e.edge_kind = ?
                """,
                (method_id, EdgeKind.READS_FROM.value),
            )
            for target_qname, e_attrs_raw in rf_targets:
                e_attrs = _json_loads(e_attrs_raw)
                via = e_attrs.get("via", "physical_table")
                virtual_kind = e_attrs.get("virtual_kind")
                key = (target_qname, virtual_kind or via)
                if key in reads_from_seen:
                    continue
                reads_from_seen.add(key)
                reads_from_list.append(
                    CardContextRegisterRead(
                        register_qname=target_qname,
                        via=via,
                        virtual_kind=virtual_kind,
                    )
                )

            # CALLS — топ-N агрегируем
            call_targets = await _fetch_all(
                db,
                """
                SELECT n.qualified_name FROM graph_nodes n
                JOIN graph_edges e ON e.dst_id = n.id
                WHERE e.src_id = ? AND e.edge_kind = ?
                """,
                (method_id, EdgeKind.CALLS.value),
            )
            for (target_qname,) in call_targets:
                top_calls_counter[target_qname] = top_calls_counter.get(target_qname, 0) + 1

    # 6. Приоритезация методов: handlers → exported → остальное
    methods.sort(
        key=lambda m: (
            not m.is_handler,
            not m.is_exported,
            m.name,
        )
    )
    methods_capped = tuple(methods[:MAX_METHODS])

    # 7. Top calls — отсортировать по убыванию count, взять MAX_TOP_CALLS
    top_calls_sorted = sorted(
        top_calls_counter.items(), key=lambda kv: (-kv[1], kv[0])
    )[:MAX_TOP_CALLS]
    top_calls = tuple(name for name, _count in top_calls_sorted)

    # 8. Reverse REFERENCES: кто ссылается на этот объект
    reverse_refs_rows = await _fetch_all(
        db,
        """
        SELECT n.qualified_name FROM graph_nodes n
        JOIN graph_edges e ON e.src_id = n.id
        WHERE e.dst_id = ? AND e.edge_kind = ?
        LIMIT ?
        """,
        (obj_id, EdgeKind.REFERENCES.value, MAX_REVERSE_REFS),
    )
    referenced_by_list = [r[0] for r in reverse_refs_rows]

    # 9. Для регистров — incoming WRITES_TO + READS_FROM → parent объекты
    # (fix 2026-05-28: build_card_context не возвращал связи документ↔регистр,
    # из-за чего NIM-карточки регистров теряли related_objects/movements).
    _REGISTER_KINDS = {
        "AccumulationRegister",
        "AccountingRegister",
        "InformationRegister",
        "CalculationRegister",
    }
    if object_kind in _REGISTER_KINDS:
        existing = set(referenced_by_list)
        writers: set[str] = set()
        readers: set[str] = set()
        for edge_kind, bucket in (
            (EdgeKind.WRITES_TO.value, writers),
            (EdgeKind.READS_FROM.value, readers),
        ):
            rows = await _fetch_all(
                db,
                """
                SELECT DISTINCT n.qualified_name FROM graph_nodes n
                JOIN graph_edges e ON e.src_id = n.id
                WHERE e.dst_id = ? AND e.edge_kind = ?
                LIMIT ?
                """,
                (obj_id, edge_kind, MAX_REVERSE_REFS * 4),
            )
            for (method_qname,) in rows:
                parts = method_qname.split(".")
                if len(parts) >= 2:
                    bucket.add(f"{parts[0]}.{parts[1]}")
        # writers важнее (документы которые формируют записи в регистре)
        for parent in sorted(writers):
            if parent not in existing and parent != object_qualified_name:
                referenced_by_list.append(parent)
                existing.add(parent)
        for parent in sorted(readers - writers):
            if parent not in existing and parent != object_qualified_name:
                referenced_by_list.append(parent)
                existing.add(parent)

    referenced_by = tuple(referenced_by_list[:MAX_REVERSE_REFS])

    return CardContext(
        object_qualified_name=object_qualified_name,
        object_kind=object_kind,
        object_name=object_name,
        object_uuid=object_uuid,
        object_comment=object_comment,
        object_source_path=obj_row[2],
        attributes=attributes,
        tabular_sections=tabular_sections,
        methods=methods_capped,
        writes_to=tuple(sorted(writes_to)),
        reads_from=tuple(reads_from_list),
        top_calls=top_calls,
        referenced_by=referenced_by,
    )


# ── Helpers ──────────────────────────────────────────────────────────


async def _build_attribute_context(
    db: aiosqlite.Connection,
    attribute_rows: list[tuple],
    *,
    limit: int,
) -> tuple[CardContextAttribute, ...]:
    """Собирает атрибуты + REFERENCES + сортирует по приоритету."""
    result: list[CardContextAttribute] = []
    for attr_id, attr_qname, attr_attrs_raw in attribute_rows:
        attr_attrs = _json_loads(attr_attrs_raw)

        # REFERENCES от этого атрибута
        ref_rows = await _fetch_all(
            db,
            """
            SELECT n.qualified_name FROM graph_nodes n
            JOIN graph_edges e ON e.dst_id = n.id
            WHERE e.src_id = ? AND e.edge_kind = ?
            """,
            (attr_id, EdgeKind.REFERENCES.value),
        )
        references = tuple(r[0] for r in ref_rows)

        result.append(
            CardContextAttribute(
                name=attr_attrs.get("name", ""),
                type_definition=attr_attrs.get("type_definition", ""),
                indexed=bool(attr_attrs.get("indexed")),
                fill_check=bool(attr_attrs.get("fill_check")),
                references=references,
            )
        )

    # Приоритезация: с references → fill_check → остальные.
    result.sort(
        key=lambda a: (not bool(a.references), not a.fill_check, a.name)
    )
    return tuple(result[:limit])


async def _build_tabular_section_context(
    db: aiosqlite.Connection,
    ts_rows: list[tuple],
) -> tuple[CardContextTabularSection, ...]:
    """Собирает ТЧ + их атрибуты (через CONTAINS)."""
    result: list[CardContextTabularSection] = []
    for ts_id, ts_qname, ts_attrs_raw in ts_rows[:MAX_TABULAR_SECTIONS]:
        ts_attrs = _json_loads(ts_attrs_raw)
        ts_name = ts_attrs.get("name", "")

        # Реквизиты ТЧ
        inner_attrs_rows = await _fetch_all(
            db,
            """
            SELECT n.id, n.qualified_name, n.attributes
            FROM graph_nodes n
            JOIN graph_edges e ON e.dst_id = n.id
            WHERE e.src_id = ? AND e.edge_kind = ?
            """,
            (ts_id, EdgeKind.CONTAINS.value),
        )

        inner_attrs = await _build_attribute_context(
            db, inner_attrs_rows, limit=MAX_TS_ATTRIBUTES,
        )

        result.append(
            CardContextTabularSection(name=ts_name, attributes=inner_attrs)
        )
    return tuple(result)


async def _fetch_one(db: aiosqlite.Connection, sql: str, params: tuple) -> tuple | None:
    cursor = await db.execute(sql, params)
    return await cursor.fetchone()


async def _fetch_all(db: aiosqlite.Connection, sql: str, params: tuple) -> list[tuple]:
    cursor = await db.execute(sql, params)
    return list(await cursor.fetchall())


def _json_loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        result = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return result if isinstance(result, dict) else {}
