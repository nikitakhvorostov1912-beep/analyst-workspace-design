"""Typical Configurations Tools для LLM orchestrator (M-K2.5.6).

Экспозит граф + карточки типовых как async-internal tools для LLM.
Когда пользователь спрашивает «как работает X в УТ», «куда пишет
движения Y», «откуда берётся Z», LLM вызывает соответствующий tool
вместо MCP-блуждания по live-базе.

## Tools

| Tool | Назначение |
|---|---|
| `list_typical_configurations` | Список загруженных типовых |
| `search_typical_objects` | Поиск объекта по name / summary |
| `explain_typical_object` | Карточка целиком + контекст графа |
| `trace_typical_calls` | Граф CALLS (depth-N в стороны) |
| `trace_typical_movements` | WRITES_TO / READS_FROM регистров |
| `compare_with_typical` | Diff client object vs typical (заглушка v1) |

## Pattern

Реализован по аналогии с `bsp_tool.py` / `its_tool.py`:
- TOOL_SCHEMA — OpenAI function schema
- `is_typical_tool(name)` — dispatcher gate
- `dispatch_typical_tool(db, settings, name, args)` — single entry
- Возвращает `(ok, result_dict, error_str)` для loop.py

## Что НЕ делает (отложено)

- Semantic search через embedding — карточки пока в mock-режиме
  без эмбеддингов; substring/LIKE match как fallback
- compare_with_typical — требует client_channel graph (M-K3) +
  diff алгоритм; заглушка возвращает «not implemented»
- trace_data_flow — комбинация REFERENCES + READS_FROM, многошаговая;
  отложено до подключения real LLM (требует валидации на реальных
  карточках)
"""

from __future__ import annotations

import json
import logging
from typing import Any

import aiosqlite

from app.knowledge.graph_storage import (
    EdgeKind,
    NodeKind,
    count_by_kind,
    find_node,
    get_neighbors,
    list_nodes,
    traverse_bfs,
)
from app.knowledge.typical.card_storage import (
    count_cards_by_channel,
    count_mock_cards_by_channel,
    get_card_by_qname,
    list_cards_by_channel,
)
from app.knowledge.typical.storage import list_configurations

logger = logging.getLogger(__name__)


# ── Tool names ───────────────────────────────────────────────────────


TOOL_LIST_CONFIGS = "list_typical_configurations"
TOOL_SEARCH_OBJECTS = "search_typical_objects"
TOOL_EXPLAIN = "explain_typical_object"
TOOL_TRACE_CALLS = "trace_typical_calls"
TOOL_TRACE_MOVEMENTS = "trace_typical_movements"
TOOL_COMPARE = "compare_with_typical"


_TYPICAL_TOOL_NAMES: frozenset[str] = frozenset(
    [
        TOOL_LIST_CONFIGS,
        TOOL_SEARCH_OBJECTS,
        TOOL_EXPLAIN,
        TOOL_TRACE_CALLS,
        TOOL_TRACE_MOVEMENTS,
        TOOL_COMPARE,
    ]
)


# Лимиты для защиты context window LLM
_MAX_SEARCH_TOP_K = 20
_MAX_EXPLAIN_NEIGHBORS = 30
_MAX_TRACE_DEPTH = 4
_MAX_TRACE_HITS = 50


# ── OpenAI function schemas ──────────────────────────────────────────


LIST_CONFIGS_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": TOOL_LIST_CONFIGS,
        "description": (
            "Список загруженных в систему типовых конфигураций 1С "
            "(УТ 11.5, БП 3.0, ERP 2.5, КА 2, ЗУП 3.1, УСО 2.5, "
            "Документооборот). Когда вызывать: пользователь спрашивает "
            "«какие типовые есть», «есть ли у тебя БП», или ты не знаешь "
            "точное имя channel_id для последующих tools. Возвращает: "
            "[{channel_id, config_kind, config_version, display_name, status}]."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


SEARCH_OBJECTS_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": TOOL_SEARCH_OBJECTS,
        "description": (
            "Поиск объекта метаданных в типовой конфигурации по имени "
            "или фрагменту описания. Когда вызывать: пользователь "
            "спрашивает «есть ли документ для X», «какой справочник "
            "хранит Y», или ты не знаешь точный qualified_name для "
            "explain_typical_object. Поиск идёт по qualified_name + "
            "summary карточек (если карточки уже сгенерированы). "
            "Возвращает топ-N matches с qualified_name + summary."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "description": (
                        "Channel ID типовой (например '_bp30_138_24'). "
                        "Получи через list_typical_configurations если не знаешь."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Запрос для поиска. Примеры: «реализация товаров», "
                        "«контрагенты», «остатки на складе». Match идёт по "
                        "qualified_name (substring case-insensitive) и по "
                        "summary карточки если она есть."
                    ),
                },
                "object_kind": {
                    "type": "string",
                    "description": (
                        "Опциональный фильтр по типу: Document / Catalog / "
                        "AccumulationRegister / InformationRegister / etc."
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "description": f"Сколько результатов вернуть (1-{_MAX_SEARCH_TOP_K}, default 10).",
                    "minimum": 1,
                    "maximum": _MAX_SEARCH_TOP_K,
                },
            },
            "required": ["channel_id", "query"],
            "additionalProperties": False,
        },
    },
}


EXPLAIN_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": TOOL_EXPLAIN,
        "description": (
            "Полная карточка объекта типовой конфигурации: что это, "
            "зачем нужен, какие реквизиты, какие движения регистров "
            "пишет/читает, связанные объекты. Когда вызывать: "
            "пользователь просит «расскажи про X», «как работает Y», "
            "«какой смысл Z». Возвращает summary + purpose + "
            "key_attributes + movements + posting_flow + related_objects "
            "+ список handler-методов из графа."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "description": "Channel ID типовой.",
                },
                "object_qualified_name": {
                    "type": "string",
                    "description": (
                        "Полное имя объекта в формате 'Kind.Name'. "
                        "Примеры: 'Document.РеализацияТоваровУслуг', "
                        "'Catalog.Контрагенты', 'AccumulationRegister.ТоварыНаСкладах'. "
                        "Если не знаешь точное имя — вызови сначала search_typical_objects."
                    ),
                },
            },
            "required": ["channel_id", "object_qualified_name"],
            "additionalProperties": False,
        },
    },
}


TRACE_CALLS_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": TOOL_TRACE_CALLS,
        "description": (
            "Граф вызовов методов (CALLS) вокруг указанного метода или "
            "объекта. Когда вызывать: пользователь спрашивает «кто "
            "вызывает X», «что вызывает X», «откуда дёргается этот код». "
            "direction='out' — что вызывает X; 'in' — кто вызывает X."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "description": "Channel ID типовой.",
                },
                "qualified_name": {
                    "type": "string",
                    "description": (
                        "Полное имя метода или объекта. Для метода: "
                        "'CommonModule.X.CommonModuleBody.МойМетод'. "
                        "Для объекта — будут traverse'нуты все его методы."
                    ),
                },
                "direction": {
                    "type": "string",
                    "enum": ["out", "in"],
                    "description": "'out' — кого вызывает; 'in' — кто вызывает.",
                },
                "depth": {
                    "type": "integer",
                    "description": f"Глубина traversal (1-{_MAX_TRACE_DEPTH}, default 1).",
                    "minimum": 1,
                    "maximum": _MAX_TRACE_DEPTH,
                },
            },
            "required": ["channel_id", "qualified_name", "direction"],
            "additionalProperties": False,
        },
    },
}


TRACE_MOVEMENTS_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": TOOL_TRACE_MOVEMENTS,
        "description": (
            "Граф движений регистров: WRITES_TO (кто пишет в регистр) + "
            "READS_FROM (кто читает). Когда вызывать: «кто пишет в "
            "регистр X», «какие документы делают движения в Y», «откуда "
            "читается остаток Z». direction='writes' — методы которые "
            "пишут; 'reads' — методы которые читают; 'both' — оба."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "description": "Channel ID типовой.",
                },
                "register_qualified_name": {
                    "type": "string",
                    "description": (
                        "Полное имя регистра: 'AccumulationRegister.X', "
                        "'InformationRegister.Y', 'AccountingRegister.Z'."
                    ),
                },
                "direction": {
                    "type": "string",
                    "enum": ["writes", "reads", "both"],
                    "description": "Какие связи показать.",
                },
            },
            "required": ["channel_id", "register_qualified_name"],
            "additionalProperties": False,
        },
    },
}


COMPARE_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": TOOL_COMPARE,
        "description": (
            "Сравнение объекта клиентской базы с одноимённым объектом "
            "типовой. Когда вызывать: «что доработано в этой реализации», "
            "«отличается ли наша Х от типовой». ВНИМАНИЕ: в текущей "
            "версии (v1) это заглушка — требует подключения графа "
            "клиентской базы (M-K3). Возвращает «not_implemented» — "
            "не вызывай пока."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "typical_channel_id": {"type": "string"},
                "client_channel_id": {"type": "string"},
                "object_qualified_name": {"type": "string"},
            },
            "required": ["typical_channel_id", "client_channel_id", "object_qualified_name"],
            "additionalProperties": False,
        },
    },
}


TYPICAL_TOOL_SCHEMAS: list[dict] = [
    LIST_CONFIGS_SCHEMA,
    SEARCH_OBJECTS_SCHEMA,
    EXPLAIN_SCHEMA,
    TRACE_CALLS_SCHEMA,
    TRACE_MOVEMENTS_SCHEMA,
    COMPARE_SCHEMA,
]


# ── Dispatcher ───────────────────────────────────────────────────────


def is_typical_tool(name: str) -> bool:
    """True если name — один из typical configurations tools."""
    return name in _TYPICAL_TOOL_NAMES


async def dispatch_typical_tool(
    db: aiosqlite.Connection,
    name: str,
    args: dict,
) -> tuple[bool, Any, str | None]:
    """Single entry-point для loop.py.

    Возвращает `(ok, result_dict_or_None, error_str_or_None)`.
    """
    if not isinstance(args, dict):
        return False, None, f"args должен быть dict, получен {type(args).__name__}"

    try:
        if name == TOOL_LIST_CONFIGS:
            return await _handle_list_configs(db)
        if name == TOOL_SEARCH_OBJECTS:
            return await _handle_search_objects(db, args)
        if name == TOOL_EXPLAIN:
            return await _handle_explain(db, args)
        if name == TOOL_TRACE_CALLS:
            return await _handle_trace_calls(db, args)
        if name == TOOL_TRACE_MOVEMENTS:
            return await _handle_trace_movements(db, args)
        if name == TOOL_COMPARE:
            return await _handle_compare(db, args)
    except ValueError as exc:
        return False, None, str(exc)
    except Exception as exc:  # noqa: BLE001 — граница LLM-tool
        logger.exception("typical tool %s failed", name)
        return False, None, f"{type(exc).__name__}: {exc}"

    return False, None, f"Неизвестный typical tool: {name}"


# ── Handlers ─────────────────────────────────────────────────────────


async def _handle_list_configs(db: aiosqlite.Connection) -> tuple[bool, Any, str | None]:
    configs = await list_configurations(db)
    result_items: list[dict] = []
    for c in configs:
        # Симметрично с backend endpoint /knowledge/typical/configurations:
        # включаем total_nodes + total_cards чтобы LLM мог понять что
        # конфигурация «готова» (status=graph_built без узлов = неполная).
        node_counts = await count_by_kind(db, c.channel_id)
        card_counts = await count_cards_by_channel(db, c.channel_id)
        mock_counts = await count_mock_cards_by_channel(db, c.channel_id)
        total_cards = sum(card_counts.values())
        mock_cards = mock_counts.get("mock", 0)
        result_items.append({
            "channel_id": c.channel_id,
            "config_kind": c.config_kind,
            "config_version": c.config_version,
            "display_name": c.display_name,
            "status": c.status,
            "indexed_at": c.indexed_at,
            "total_nodes": sum(node_counts.values()),
            "total_cards": total_cards,
            # v2.0-step-2: visibility во сколько процентов карточек mock-сгенерированы.
            # Если всё 100% mock — бот должен честно сказать «данные не верифицированы».
            "mock_cards": mock_cards,
            "verified_cards": mock_counts.get("verified", 0),
            "mock_ratio": (
                round(mock_cards / total_cards, 3) if total_cards else 0.0
            ),
        })
    return True, {
        "configurations": result_items,
        "total": len(result_items),
    }, None


async def _handle_search_objects(
    db: aiosqlite.Connection, args: dict,
) -> tuple[bool, Any, str | None]:
    channel_id = _require_str(args, "channel_id")
    query = _require_str(args, "query").lower()
    object_kind = args.get("object_kind")
    top_k = _coerce_int(args.get("top_k", 10), default=10, lo=1, hi=_MAX_SEARCH_TOP_K)

    # 1. Поиск по qualified_name (substring)
    nodes = await list_nodes(
        db, channel_id=channel_id, node_kind=NodeKind.METADATA_OBJECT.value, limit=5000,
    )
    matched = [n for n in nodes if query in n.qualified_name.lower()]
    if object_kind:
        matched = [n for n in matched if n.attributes.get("kind") == object_kind]

    # 2. Поиск по summary карточек
    cards = await list_cards_by_channel(db, channel_id=channel_id, limit=5000)
    card_matches = [
        c for c in cards
        if query in (c.card.summary + " " + c.card.purpose).lower()
    ]
    if object_kind:
        card_matches = [c for c in card_matches if c.object_kind == object_kind]

    # Объединить и дедупнуть
    seen: set[str] = set()
    results: list[dict] = []
    for node in matched[:top_k]:
        qname = node.qualified_name
        if qname in seen:
            continue
        seen.add(qname)
        card = await get_card_by_qname(
            db, channel_id=channel_id, object_qualified_name=qname,
        )
        results.append({
            "qualified_name": qname,
            "kind": node.attributes.get("kind"),
            "name": node.attributes.get("name"),
            "has_card": card is not None,
            "is_mock": bool(card.is_mock) if card else False,
            "summary": (card.card.summary if card else None),
        })
        if len(results) >= top_k:
            break

    # Добавим карточки которые не были найдены по qname
    for cr in card_matches:
        if cr.object_qualified_name in seen or len(results) >= top_k:
            continue
        seen.add(cr.object_qualified_name)
        results.append({
            "qualified_name": cr.object_qualified_name,
            "kind": cr.object_kind,
            "name": cr.object_qualified_name.split(".", 1)[-1],
            "has_card": True,
            "is_mock": bool(cr.is_mock),
            "summary": cr.card.summary,
        })

    return True, {
        "query": query,
        "channel_id": channel_id,
        "results": results[:top_k],
        "total": len(results[:top_k]),
    }, None


async def _handle_explain(
    db: aiosqlite.Connection, args: dict,
) -> tuple[bool, Any, str | None]:
    channel_id = _require_str(args, "channel_id")
    qname = _require_str(args, "object_qualified_name")

    node = await find_node(
        db, channel_id=channel_id, qualified_name=qname,
        node_kind=NodeKind.METADATA_OBJECT.value,
    )
    if node is None:
        return False, None, f"Объект {qname!r} не найден в канале {channel_id}"

    card_rec = await get_card_by_qname(
        db, channel_id=channel_id, object_qualified_name=qname,
    )

    # 1-hop neighbors для контекста
    children = await get_neighbors(
        db, node.id, direction="out", edge_kind=EdgeKind.CONTAINS.value,
    )
    children_summary = _summarize_children(children, limit=_MAX_EXPLAIN_NEIGHBORS)

    # is_mock (M-K2.5.9.2) — обязательное warning-поле для LLM: если
    # карточка mock-сгенерирована, бот должен честно сказать
    # «данные не верифицированы экспертом», а не выдавать stub за факт.
    is_mock = bool(card_rec.is_mock) if card_rec else False

    # validation (M-K2.5.9.5) — результат сверки карточки с графом.
    # Если есть issues, LLM знает что НЕЛЬЗЯ слепо доверять полям
    # карточки — нужно cross-check с children_summary / графом.
    validation: dict | None = None
    if card_rec and card_rec.validation_status:
        validation = {
            "status": card_rec.validation_status,
            "validated_at": card_rec.validated_at,
            "issues": (
                json.loads(card_rec.validation_issues)
                if card_rec.validation_issues else []
            ),
        }

    return True, {
        "qualified_name": qname,
        "object_kind": node.attributes.get("kind"),
        "comment": node.attributes.get("comment", ""),
        "source_path": node.source_path,
        "card": card_rec.card.to_dict() if card_rec else None,
        "card_status": card_rec.status if card_rec else "not_generated",
        "is_mock": is_mock,
        "card_warning": (
            "Карточка mock-сгенерирована (LLM-stub), не верифицирована экспертом. "
            "Используй structure из children_summary как первичный факт; "
            "summary/purpose могут содержать обобщения."
            if is_mock else None
        ),
        "validation": validation,
        # v2.0-step-6 — embedding versioning visibility:
        # позволяет LLM и UI понять, какой версией embedding пайплайна
        # карточка была обработана.
        "embedding_meta": (
            {
                "model": card_rec.embedding_model,
                "model_version": card_rec.embedding_model_version,
                "dim": card_rec.embedding_dim,
            }
            if card_rec else None
        ),
        "children_summary": children_summary,
    }, None


async def _handle_trace_calls(
    db: aiosqlite.Connection, args: dict,
) -> tuple[bool, Any, str | None]:
    channel_id = _require_str(args, "channel_id")
    qname = _require_str(args, "qualified_name")
    direction = _require_str(args, "direction")
    if direction not in ("out", "in"):
        raise ValueError(f"direction должно быть 'out' или 'in', получено {direction!r}")
    depth = _coerce_int(args.get("depth", 1), default=1, lo=1, hi=_MAX_TRACE_DEPTH)

    # Ищем method node, или metadata object
    node = await find_node(
        db, channel_id=channel_id, qualified_name=qname, node_kind=NodeKind.METHOD.value,
    )
    if node is None:
        node = await find_node(
            db, channel_id=channel_id, qualified_name=qname,
            node_kind=NodeKind.METADATA_OBJECT.value,
        )
    if node is None:
        return False, None, f"Узел {qname!r} не найден в канале {channel_id}"

    hits = await traverse_bfs(
        db, node.id, max_depth=depth, direction=direction,
        edge_kind=EdgeKind.CALLS.value,
    )
    hits = hits[:_MAX_TRACE_HITS]

    return True, {
        "channel_id": channel_id,
        "start": qname,
        "direction": direction,
        "depth": depth,
        "hits": [
            {
                "qualified_name": h.node.qualified_name,
                "node_kind": h.node.node_kind,
                "depth": h.depth,
                "path": list(h.path_kinds),
            }
            for h in hits
        ],
        "total": len(hits),
    }, None


async def _handle_trace_movements(
    db: aiosqlite.Connection, args: dict,
) -> tuple[bool, Any, str | None]:
    channel_id = _require_str(args, "channel_id")
    qname = _require_str(args, "register_qualified_name")
    direction = args.get("direction", "both")
    if direction not in ("writes", "reads", "both"):
        raise ValueError(f"direction должно быть 'writes'|'reads'|'both', получено {direction!r}")

    register_node = await find_node(
        db, channel_id=channel_id, qualified_name=qname,
        node_kind=NodeKind.METADATA_OBJECT.value,
    )
    if register_node is None:
        return False, None, f"Регистр {qname!r} не найден"

    result: dict[str, Any] = {
        "channel_id": channel_id,
        "register": qname,
        "writes": [],
        "reads": [],
    }

    if direction in ("writes", "both"):
        writers = await get_neighbors(
            db, register_node.id, direction="in", edge_kind=EdgeKind.WRITES_TO.value,
        )
        result["writes"] = [
            {
                "method_qualified_name": w.qualified_name,
                "module_kind": w.attributes.get("module_kind"),
            }
            for w in writers[:_MAX_TRACE_HITS]
        ]

    if direction in ("reads", "both"):
        readers = await get_neighbors(
            db, register_node.id, direction="in", edge_kind=EdgeKind.READS_FROM.value,
        )
        result["reads"] = [
            {
                "method_qualified_name": r.qualified_name,
                "module_kind": r.attributes.get("module_kind"),
            }
            for r in readers[:_MAX_TRACE_HITS]
        ]

    result["total_writes"] = len(result["writes"])
    result["total_reads"] = len(result["reads"])
    return True, result, None


async def _handle_compare(
    db: aiosqlite.Connection, args: dict,
) -> tuple[bool, Any, str | None]:
    # Заглушка v1 — требует client graph из M-K3.
    return True, {
        "status": "not_implemented",
        "message": (
            "compare_with_typical пока не реализован. Требуется граф клиентской базы "
            "(M-K3). Используй explain_typical_object для типовой и MCP-tools для "
            "клиентской базы, сравни вручную."
        ),
    }, None


# ── Helpers ──────────────────────────────────────────────────────────


def _summarize_children(children: list, limit: int) -> dict[str, list[str]]:
    """Группирует children по node_kind, возвращает list имён в каждой группе."""
    grouped: dict[str, list[str]] = {}
    for n in children:
        grouped.setdefault(n.node_kind, []).append(
            n.attributes.get("name") or n.qualified_name.split(".")[-1]
        )

    # Сортировка + ограничение
    result: dict[str, list[str]] = {}
    for kind, names in grouped.items():
        result[kind] = sorted(set(names))[:limit]
    return result


def _require_str(args: dict, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Параметр {key!r} обязателен и должен быть непустой строкой")
    return value.strip()


def _coerce_int(value: Any, *, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))
