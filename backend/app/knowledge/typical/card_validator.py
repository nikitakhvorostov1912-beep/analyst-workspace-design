"""Card validator против семантического графа (M-K2.5.9.5).

GraphEval-стиль валидации: граф — ground truth. LLM-генерируемая карточка
сравнивается со связями в графе, выявляются противоречия (LLM выдумала
register которого нет в WRITES_TO; LLM выдумала связь с объектом
которого нет в графе).

## Архитектура

```
TypicalObjectCard (LLM-output)
       ↓
validate_card_against_graph(db, channel_id, card)
       ↓                                      ↑
       ↓                                graph_storage queries
       ↓                                (graph_nodes, graph_edges)
       ↓
CardValidationResult
  - status: 'valid' | 'issues_found' | 'object_not_in_graph'
  - issues: list[CardValidationIssue]
  - validated_at: timestamp
```

## Что валидируем

| Поле карточки | Vs граф | Тип issue |
|---|---|---|
| `movements[i].register` | WRITES_TO edges от методов объекта | `phantom_movement` (карточка → graph mismatch) |
| (обратное) | WRITES_TO в графе но нет в карточке | `missing_movement` (info) |
| `related_objects` | Существуют ли node'ы с этими qnames в графе | `phantom_related` |

## Что НЕ валидируем (out of scope)

- `summary`, `purpose` — текстовые, нет ground truth (validate против ИТС
  будет в отдельной фазе M-K4 — normative refs)
- `posting_flow`, `typical_scenarios`, `preconditions` — описательные
- `key_attributes` — attributes в графе есть отдельной node_kind ATTRIBUTE,
  но они могут быть переименованы / синонимизированы LLM. Cross-check
  слишком жёсткий для v1.

## Хранение результата

Migration v20 добавила колонки `validation_status`, `validation_issues`,
`validated_at` в typical_object_cards. Storage helpers — в card_storage.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal

import aiosqlite

from app.knowledge.graph_storage import (
    EdgeKind,
    GraphNode,
    NodeKind,
    find_node,
    get_neighbors,
)
from app.knowledge.typical.card_models import TypicalObjectCard

logger = logging.getLogger(__name__)


# ── Result types ─────────────────────────────────────────────────────


ValidationSeverity = Literal["error", "warning", "info"]
ValidationStatus = Literal["valid", "issues_found", "object_not_in_graph"]


@dataclass(frozen=True, slots=True)
class CardValidationIssue:
    """Один пункт в отчёте валидации.

    severity:
      - 'error' — карточка явно противоречит графу (phantom-объект)
      - 'warning' — расхождение которое аналитик должен проверить
      - 'info' — наблюдение которое не блокирует использование
    """

    severity: ValidationSeverity
    code: str
    field: str | None
    detail: str

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "field": self.field,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class CardValidationResult:
    """Полный отчёт валидации одной карточки."""

    status: ValidationStatus
    issues: tuple[CardValidationIssue, ...]
    validated_at: str  # ISO-8601 timestamp
    object_qualified_name: str
    channel_id: str

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "issues": [i.to_dict() for i in self.issues],
            "validated_at": self.validated_at,
            "object_qualified_name": self.object_qualified_name,
            "channel_id": self.channel_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# ── Validation ───────────────────────────────────────────────────────


async def validate_card_against_graph(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    card: TypicalObjectCard,
) -> CardValidationResult:
    """Сверяет карточку с графом канала.

    Граф — ground truth. Если в карточке `movements` ссылается на регистр
    которого нет среди WRITES_TO для методов этого объекта — это
    hallucination, фиксируется как `phantom_movement`.

    Args:
        db: подключение
        channel_id: channel объекта
        card: карточка для валидации

    Returns:
        CardValidationResult — статус + список issues.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    issues: list[CardValidationIssue] = []

    # 1. Найти объект в графе
    obj_node = await find_node(
        db,
        channel_id=channel_id,
        qualified_name=card.object_qualified_name,
        node_kind=NodeKind.METADATA_OBJECT.value,
    )
    if obj_node is None:
        # Карточка ссылается на объект которого нет в графе.
        # Это критическое противоречие (например, объект удалён, channel mismatch).
        return CardValidationResult(
            status="object_not_in_graph",
            issues=(CardValidationIssue(
                severity="error",
                code="object_not_in_graph",
                field=None,
                detail=(
                    f"Объект {card.object_qualified_name!r} не найден "
                    f"в графе канала {channel_id!r}. Карточка ссылается на "
                    f"несуществующий объект."
                ),
            ),),
            validated_at=now_iso,
            object_qualified_name=card.object_qualified_name,
            channel_id=channel_id,
        )

    # 2. Собрать все registers куда пишут методы этого объекта (WRITES_TO).
    writes_to_in_graph = await _collect_object_writes_to(db, obj_node)
    reads_from_in_graph = await _collect_object_reads_from(db, obj_node)

    # 3. Сверить movements в карточке с writes_to из графа.
    card_movement_registers = {m.register for m in card.movements}

    # 3a. Phantom movements: в карточке есть, в графе нет.
    for movement in card.movements:
        if movement.register not in writes_to_in_graph and movement.register not in reads_from_in_graph:
            issues.append(CardValidationIssue(
                severity="error",
                code="phantom_movement",
                field="movements",
                detail=(
                    f"В карточке указано движение в {movement.register!r}, "
                    f"но в графе нет WRITES_TO или READS_FROM от методов "
                    f"объекта к этому регистру. Возможно LLM выдумала."
                ),
            ))

    # 3b. Missing movements: в графе WRITES_TO есть, в карточке нет.
    # Это «info», не «error» — LLM могла осознанно опустить регистр.
    for register in writes_to_in_graph - card_movement_registers:
        issues.append(CardValidationIssue(
            severity="info",
            code="missing_movement",
            field="movements",
            detail=(
                f"В графе есть WRITES_TO к {register!r}, но карточка не "
                f"упоминает это движение. Возможно LLM сочла его неважным."
            ),
        ))

    # 4. Related_objects: проверить что каждое имя есть в графе.
    for related in card.related_objects:
        related_node = await find_node(
            db,
            channel_id=channel_id,
            qualified_name=related,
            node_kind=NodeKind.METADATA_OBJECT.value,
        )
        if related_node is None:
            issues.append(CardValidationIssue(
                severity="warning",
                code="phantom_related",
                field="related_objects",
                detail=(
                    f"related_objects[{related!r}] — объект не найден в "
                    f"графе канала. Возможно LLM выдумала имя."
                ),
            ))

    status: ValidationStatus = "valid" if not issues else "issues_found"
    # Status downgrade rule: даже если есть только info-issues (missing_movement),
    # это всё ещё 'issues_found' для visibility. Но severity осталась info.

    return CardValidationResult(
        status=status,
        issues=tuple(issues),
        validated_at=now_iso,
        object_qualified_name=card.object_qualified_name,
        channel_id=channel_id,
    )


# ── Helpers ──────────────────────────────────────────────────────────


async def _collect_object_writes_to(
    db: aiosqlite.Connection,
    obj_node: GraphNode,
) -> set[str]:
    """Собирает все qualified_name регистров, в которые пишут методы объекта.

    Алгоритм:
    1. Найти все методы объекта через CONTAINS.
    2. Для каждого метода — WRITES_TO edges (out-direction).
    3. Union qualified_names.
    """
    return await _collect_object_targets(db, obj_node, EdgeKind.WRITES_TO.value)


async def _collect_object_reads_from(
    db: aiosqlite.Connection,
    obj_node: GraphNode,
) -> set[str]:
    """Собирает все qualified_name регистров, из которых читают методы объекта."""
    return await _collect_object_targets(db, obj_node, EdgeKind.READS_FROM.value)


async def _collect_object_targets(
    db: aiosqlite.Connection,
    obj_node: GraphNode,
    edge_kind: str,
) -> set[str]:
    """Generic: object → CONTAINS → {Method | Module → CONTAINS → Method} → <edge_kind> → target.

    Структура графа (M-K2.5.4 builder):
    - Document/Catalog/Register → CONTAINS → Attribute (реквизиты)
    - Document/Catalog/Register → CONTAINS → Module (МодульОбъекта / ФормаДокумента / etc)
    - Module → CONTAINS → Method
    - Method → WRITES_TO / READS_FROM → Register

    Поэтому для сбора WRITES_TO/READS_FROM нужно обходить 2 hops:
    1. Прямые children объекта — может быть и Method (для редких случаев) и Module
    2. Если child — Module, ходим внутрь к его Method'ам
    Затем у каждого Method собираем edges нужного типа.
    """
    direct_children = await get_neighbors(
        db, obj_node.id, direction="out", edge_kind=EdgeKind.CONTAINS.value,
    )

    methods: list[GraphNode] = []
    for child in direct_children:
        if child.node_kind == NodeKind.METHOD.value:
            # Method напрямую в объекте (legacy / редкий случай)
            methods.append(child)
        elif child.node_kind == NodeKind.MODULE.value:
            # Module — ищем методы внутри
            module_methods = await get_neighbors(
                db, child.id, direction="out", edge_kind=EdgeKind.CONTAINS.value,
            )
            methods.extend(
                m for m in module_methods if m.node_kind == NodeKind.METHOD.value
            )

    # Сбор targets от каждого метода
    targets: set[str] = set()
    for method in methods:
        method_targets = await get_neighbors(
            db, method.id, direction="out", edge_kind=edge_kind,
        )
        for t in method_targets:
            targets.add(t.qualified_name)
    return targets


# ── Storage integration ──────────────────────────────────────────────


async def save_validation_result(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    object_qualified_name: str,
    result: CardValidationResult,
) -> bool:
    """Сохраняет результат валидации в typical_object_cards.

    Обновляет колонки validation_status / validation_issues / validated_at.
    Возвращает True если карточка найдена и обновлена.
    """
    issues_json = json.dumps(
        [i.to_dict() for i in result.issues],
        ensure_ascii=False,
        sort_keys=True,
    )
    cursor = await db.execute(
        """
        UPDATE typical_object_cards
        SET validation_status = ?,
            validation_issues = ?,
            validated_at = ?
        WHERE channel_id = ? AND object_qualified_name = ?
        """,
        (
            result.status,
            issues_json,
            result.validated_at,
            channel_id,
            object_qualified_name,
        ),
    )
    await db.commit()
    return cursor.rowcount > 0
