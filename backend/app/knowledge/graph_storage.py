"""Knowledge Graph storage (M-K3.17.1a, ADR-002).

L2 Relational layer: nodes (модули / методы / типы метаданных) + edges
(CALLS / CONTAINS / USES / WRITES_TO / READS_FROM). Хранилище — SQLite +
recursive CTE для traversal'а. **Не** Neo4j (per ADR-002: embed-friendly,
no extra runtime, JOIN с metadata_cache / its_chunks / bsp_chunks).

**Архитектура:**
- `graph_nodes`: id, channel_id, node_kind, qualified_name, source_path,
  attributes JSON.
- `graph_edges`: id, src_id, dst_id, edge_kind, attributes JSON.
- UNIQUE constraint на (channel_id, qualified_name, node_kind) обеспечивает
  idempotent upsert (один node для одного fully-qualified имени per канал).
- UNIQUE на (src_id, dst_id, edge_kind) обеспечивает идемпотентность edges.

**Что НЕ делает M-K3.17.1a (foundation):**
- Не парсит BSL — это next phase (M-K3.17.1b).
- Не интегрируется с indexer'ом — это next phase.
- Не делает graph algorithms (PageRank, centrality) — M-K3.17 use cases.
- Не embeds — vec0 уже M-K2, graph dimensions добавятся через JOIN.

**Что делает:**
- CRUD: insert_node / insert_edge / get_node / list_nodes_by_kind /
  delete_channel.
- Traversal: get_neighbors (1-hop) / traverse_bfs (CTE recursive, depth
  limit).
- Counters: count_nodes / count_edges / by_kind разбивки.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


class NodeKind(str, Enum):
    """Типы node'ов в Knowledge Graph.

    Покрывают первичные BSL/metadata сущности. Расширяется по мере
    появления новых use cases (см. M-K3 phase 17.2-17.6).
    """

    MODULE = "Module"               # CommonModule, ObjectModule, FormModule
    METHOD = "Method"               # Процедура / Функция
    METADATA_OBJECT = "MetadataObject"  # Документ.X, Справочник.Y, РегистрНакопления.Z
    ATTRIBUTE = "Attribute"         # Реквизит документа / справочника
    TABULAR_SECTION = "TabularSection"  # Табличная часть документа
    ROLE = "Role"                   # Роль
    SUBSYSTEM = "Subsystem"         # Подсистема


class EdgeKind(str, Enum):
    """Типы edges. Названия — мнемоничные глаголы.

    Direction matters: edges направлены `src → dst`. Пример:
    `Module.X CALLS Method.Y` означает что код Module.X вызывает Method.Y.
    """

    CONTAINS = "CONTAINS"           # MetadataObject CONTAINS Attribute / Method
    CALLS = "CALLS"                 # Method CALLS Method (BSL call)
    USES = "USES"                   # Method USES MetadataObject (e.g. ссылается на тип)
    WRITES_TO = "WRITES_TO"         # Method WRITES_TO Register (Движения.X.Записать)
    READS_FROM = "READS_FROM"       # Method READS_FROM Register (Запрос или .Остатки())
    REFERENCES = "REFERENCES"       # Generic reference (для редких связей)
    RESTRICTS = "RESTRICTS"         # Role RESTRICTS access to MetadataObject (M-K3.17.2 RLS; attrs: right, condition)


# Максимальная глубина traverse_bfs — защита от infinite cycles
# (BSL CALLS может быть circular: ChromaticMode → BlackWhite → Chromatic).
MAX_TRAVERSAL_DEPTH = 10


@dataclass(frozen=True, slots=True)
class GraphNode:
    """Один node в KG. Иммутабельный — модификация через upsert."""

    id: int
    channel_id: str
    node_kind: str
    qualified_name: str
    source_path: str | None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "node_kind": self.node_kind,
            "qualified_name": self.qualified_name,
            "source_path": self.source_path,
            "attributes": self.attributes,
        }


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """Одна direct связь src → dst."""

    id: int
    src_id: int
    dst_id: int
    edge_kind: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "src_id": self.src_id,
            "dst_id": self.dst_id,
            "edge_kind": self.edge_kind,
            "attributes": self.attributes,
        }


@dataclass(frozen=True, slots=True)
class TraversalHit:
    """Result entry для traverse_bfs: node + depth + path_edges."""

    node: GraphNode
    depth: int
    # path: список edge_kind'ов от стартового node до текущего (длина = depth).
    path_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Subgraph:
    """Подграф вокруг центрального узла — для GraphCard (React Flow) / REST.

    nodes — достижимые узлы (с глубиной), edges — ИНДУЦИРОВАННЫЕ рёбра: только
    те, у которых ОБА конца попали в отображаемый набор. truncated=True если
    достижимых узлов было больше max_nodes (UI: «показаны первые N из M»).
    """

    center: GraphNode | None
    hits: tuple[TraversalHit, ...]
    edges: tuple[GraphEdge, ...]
    total_reached: int
    truncated: bool

    def to_dict(self) -> dict:
        return {
            "center": self.center.to_dict() if self.center else None,
            "nodes": [{**h.node.to_dict(), "depth": h.depth} for h in self.hits],
            "edges": [
                {"src_id": e.src_id, "dst_id": e.dst_id, "edge_kind": e.edge_kind}
                for e in self.edges
            ],
            "total_reached": self.total_reached,
            "truncated": self.truncated,
        }


class GraphStorageError(Exception):
    """Любая ошибка graph storage layer."""


def _serialize_attrs(attrs: dict[str, Any] | None) -> str:
    """JSON-encode attributes с защитой от циклических ссылок."""
    if not attrs:
        return "{}"
    try:
        return json.dumps(attrs, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise GraphStorageError(f"Non-serializable attributes: {exc}") from exc


def _deserialize_attrs(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        result = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return result if isinstance(result, dict) else {}


def _row_to_node(row: tuple) -> GraphNode:
    return GraphNode(
        id=int(row[0]),
        channel_id=row[1],
        node_kind=row[2],
        qualified_name=row[3],
        source_path=row[4],
        attributes=_deserialize_attrs(row[5]),
    )


def _row_to_edge(row: tuple) -> GraphEdge:
    return GraphEdge(
        id=int(row[0]),
        src_id=int(row[1]),
        dst_id=int(row[2]),
        edge_kind=row[3],
        attributes=_deserialize_attrs(row[4]),
    )


# ============================================================================
# CRUD: nodes
# ============================================================================


async def insert_node(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    node_kind: str,
    qualified_name: str,
    source_path: str | None = None,
    attributes: dict[str, Any] | None = None,
    commit: bool = True,
) -> int:
    """Upserts node. Возвращает id (новый или существующий).

    Идемпотентен через UNIQUE(channel_id, qualified_name, node_kind):
    повторный insert с теми же ключами обновит source_path / attributes.

    `commit=False` — пропускает `await db.commit()`. Полезно для bulk
    операций в graph_builder: один commit на батч даёт 5-10× ускорение
    на типовых конфигурациях с 150k+ узлов (graph_builder calls
    explicit `await db.commit()` после Phase B/C/D).

    Использует `RETURNING id` (SQLite 3.35+) — один SQL call вместо
    INSERT + SELECT.
    """
    if not channel_id or not qualified_name or not node_kind:
        raise GraphStorageError(
            "channel_id, node_kind, qualified_name — все обязательны"
        )

    attrs_json = _serialize_attrs(attributes)

    cursor = await db.execute(
        """
        INSERT INTO graph_nodes (channel_id, node_kind, qualified_name, source_path, attributes)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(channel_id, qualified_name, node_kind) DO UPDATE SET
            source_path = excluded.source_path,
            attributes = excluded.attributes
        RETURNING id
        """,
        (channel_id, node_kind, qualified_name, source_path, attrs_json),
    )
    row = await cursor.fetchone()
    if row is None:
        raise GraphStorageError("upsert не вернул id — внутренняя ошибка")
    if commit:
        await db.commit()
    return int(row[0])


async def get_node(
    db: aiosqlite.Connection,
    node_id: int,
) -> GraphNode | None:
    """Returns node by id, или None."""
    cursor = await db.execute(
        """
        SELECT id, channel_id, node_kind, qualified_name, source_path, attributes
        FROM graph_nodes WHERE id = ?
        """,
        (node_id,),
    )
    row = await cursor.fetchone()
    return _row_to_node(row) if row else None


async def find_node(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    qualified_name: str,
    node_kind: str,
) -> GraphNode | None:
    """Returns node by natural key, или None."""
    cursor = await db.execute(
        """
        SELECT id, channel_id, node_kind, qualified_name, source_path, attributes
        FROM graph_nodes
        WHERE channel_id = ? AND qualified_name = ? AND node_kind = ?
        """,
        (channel_id, qualified_name, node_kind),
    )
    row = await cursor.fetchone()
    return _row_to_node(row) if row else None


async def list_nodes(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    node_kind: str | None = None,
    limit: int = 100,
) -> list[GraphNode]:
    """Returns nodes канала. Опционально фильтр по kind."""
    if node_kind:
        cursor = await db.execute(
            """
            SELECT id, channel_id, node_kind, qualified_name, source_path, attributes
            FROM graph_nodes
            WHERE channel_id = ? AND node_kind = ?
            ORDER BY qualified_name
            LIMIT ?
            """,
            (channel_id, node_kind, limit),
        )
    else:
        cursor = await db.execute(
            """
            SELECT id, channel_id, node_kind, qualified_name, source_path, attributes
            FROM graph_nodes
            WHERE channel_id = ?
            ORDER BY node_kind, qualified_name
            LIMIT ?
            """,
            (channel_id, limit),
        )
    rows = await cursor.fetchall()
    return [_row_to_node(row) for row in rows]


# ============================================================================
# CRUD: edges
# ============================================================================


async def insert_edge(
    db: aiosqlite.Connection,
    *,
    src_id: int,
    dst_id: int,
    edge_kind: str,
    attributes: dict[str, Any] | None = None,
    commit: bool = True,
) -> int:
    """Upserts edge. Возвращает id.

    Идемпотентен через UNIQUE(src_id, dst_id, edge_kind). При повторе —
    обновляет только attributes.

    `commit=False` — пропускает commit (для bulk операций). Использует
    `RETURNING id` (SQLite 3.35+) для одного SQL вызова вместо двух.
    """
    if src_id == dst_id:
        # Self-loops запрещены — это обычно baggy parser, а не реальная связь.
        raise GraphStorageError(
            f"Self-loop запрещён (src_id == dst_id == {src_id})"
        )

    attrs_json = _serialize_attrs(attributes)
    cursor = await db.execute(
        """
        INSERT INTO graph_edges (src_id, dst_id, edge_kind, attributes)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(src_id, dst_id, edge_kind) DO UPDATE SET
            attributes = excluded.attributes
        RETURNING id
        """,
        (src_id, dst_id, edge_kind, attrs_json),
    )
    row = await cursor.fetchone()
    if row is None:
        raise GraphStorageError("edge upsert не вернул id")
    if commit:
        await db.commit()
    return int(row[0])


async def get_edges_from(
    db: aiosqlite.Connection,
    src_id: int,
    *,
    edge_kind: str | None = None,
) -> list[GraphEdge]:
    """Все исходящие edges от node'а. Опционально по kind."""
    if edge_kind:
        cursor = await db.execute(
            """
            SELECT id, src_id, dst_id, edge_kind, attributes
            FROM graph_edges WHERE src_id = ? AND edge_kind = ?
            """,
            (src_id, edge_kind),
        )
    else:
        cursor = await db.execute(
            """
            SELECT id, src_id, dst_id, edge_kind, attributes
            FROM graph_edges WHERE src_id = ?
            """,
            (src_id,),
        )
    rows = await cursor.fetchall()
    return [_row_to_edge(row) for row in rows]


async def get_edges_to(
    db: aiosqlite.Connection,
    dst_id: int,
    *,
    edge_kind: str | None = None,
) -> list[GraphEdge]:
    """Все входящие edges (reverse traversal)."""
    if edge_kind:
        cursor = await db.execute(
            """
            SELECT id, src_id, dst_id, edge_kind, attributes
            FROM graph_edges WHERE dst_id = ? AND edge_kind = ?
            """,
            (dst_id, edge_kind),
        )
    else:
        cursor = await db.execute(
            """
            SELECT id, src_id, dst_id, edge_kind, attributes
            FROM graph_edges WHERE dst_id = ?
            """,
            (dst_id,),
        )
    rows = await cursor.fetchall()
    return [_row_to_edge(row) for row in rows]


async def get_neighbors(
    db: aiosqlite.Connection,
    node_id: int,
    *,
    direction: str = "out",
    edge_kind: str | None = None,
) -> list[GraphNode]:
    """1-hop соседи.

    Args:
        direction: 'out' (dst_id targets), 'in' (src_id sources), 'both'.
        edge_kind: фильтр по типу edge'а.
    """
    if direction not in ("out", "in", "both"):
        raise GraphStorageError(f"direction должно быть 'out'|'in'|'both', получено {direction!r}")

    sql_parts: list[str] = []
    params: list = []

    if direction in ("out", "both"):
        sub = """
            SELECT n.id, n.channel_id, n.node_kind, n.qualified_name, n.source_path, n.attributes
            FROM graph_nodes n
            JOIN graph_edges e ON e.dst_id = n.id
            WHERE e.src_id = ?
        """
        params.append(node_id)
        if edge_kind:
            sub += " AND e.edge_kind = ?"
            params.append(edge_kind)
        sql_parts.append(sub)

    if direction in ("in", "both"):
        sub = """
            SELECT n.id, n.channel_id, n.node_kind, n.qualified_name, n.source_path, n.attributes
            FROM graph_nodes n
            JOIN graph_edges e ON e.src_id = n.id
            WHERE e.dst_id = ?
        """
        params.append(node_id)
        if edge_kind:
            sub += " AND e.edge_kind = ?"
            params.append(edge_kind)
        sql_parts.append(sub)

    sql = " UNION ".join(sql_parts)
    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [_row_to_node(row) for row in rows]


# ============================================================================
# CTE Recursive traversal
# ============================================================================


async def traverse_bfs(
    db: aiosqlite.Connection,
    start_id: int,
    *,
    max_depth: int = 3,
    direction: str = "out",
    edge_kind: str | None = None,
) -> list[TraversalHit]:
    """BFS traversal через recursive CTE.

    Возвращает все достижимые nodes до max_depth, включая стартовый
    (depth=0). Каждый hit имеет `path_kinds` — sequence edge'ов которой
    он достигнут (для UI «как X связан с Y»).

    Args:
        start_id: ID стартового node
        max_depth: ограничение глубины (1..MAX_TRAVERSAL_DEPTH=10)
        direction: 'out' (по dst_id) | 'in' (по src_id). 'both' пока не
            поддерживается в CTE (заметно усложняет SQL, нужно только для
            edge cases — добавим в M-K3.17 если потребуется).
        edge_kind: фильтр по типу (только этот kind в traversal).

    Returns:
        list[TraversalHit] упорядоченный по depth ASC.

    Raises:
        GraphStorageError при невалидных параметрах.
    """
    if max_depth < 1 or max_depth > MAX_TRAVERSAL_DEPTH:
        raise GraphStorageError(
            f"max_depth должно быть 1..{MAX_TRAVERSAL_DEPTH}, получено {max_depth}"
        )
    if direction not in ("out", "in"):
        raise GraphStorageError(
            f"direction должно быть 'out'|'in', получено {direction!r}"
        )

    # Итеративный BFS с visited-множеством вместо рекурсивного CTE.
    #
    # Рекурсивный CTE c UNION ALL и без visited-guard переисследует узлы по
    # ВСЕМ путям: в графе вызовов (циклы + высокий fan-out) число path-строк
    # длины ≤ max_depth растёт экспоненциально (depth=5 от формы с out-degree
    # ~267 → сотни тысяч промежуточных строк → ~384мс на типовой УТ, выше
    # бюджета 300мс). Visited-set даёт O(nodes + edges): каждый узел
    # посещается один раз, на кратчайшей глубине. См. M-K3.17.1 benchmark.
    #
    # direction='out': идём по e.src_id == cur → next = e.dst_id
    # direction='in':  идём по e.dst_id == cur → next = e.src_id
    if direction == "out":
        cur_col, next_col = "src_id", "dst_id"
    else:
        cur_col, next_col = "dst_id", "src_id"

    # depth + path_kinds фиксируются на момент ПЕРВОГО (кратчайшего) достижения.
    visited: dict[int, tuple[int, tuple[str, ...]]] = {start_id: (0, ())}
    frontier: list[int] = [start_id]

    # SQLite ограничивает число bind-переменных (SQLITE_MAX_VARIABLE_NUMBER,
    # исторически 999) — бьём frontier/выборку узлов на чанки с запасом.
    chunk = 800

    for _ in range(max_depth):
        if not frontier:
            break
        next_frontier: list[int] = []
        for i in range(0, len(frontier), chunk):
            batch = frontier[i : i + chunk]
            placeholders = ",".join("?" * len(batch))
            sql = (
                f"SELECT {cur_col}, {next_col}, edge_kind FROM graph_edges "
                f"WHERE {cur_col} IN ({placeholders})"
            )
            params: list = list(batch)
            if edge_kind:
                sql += " AND edge_kind = ?"
                params.append(edge_kind)
            cursor = await db.execute(sql, params)
            for cur_id, nxt_id, kind in await cursor.fetchall():
                if nxt_id in visited:
                    continue
                depth, path = visited[cur_id]
                visited[nxt_id] = (depth + 1, (*path, kind))
                next_frontier.append(nxt_id)
        frontier = next_frontier

    # Детали узлов одним проходом (теми же чанками).
    nodes_by_id: dict[int, GraphNode] = {}
    node_ids = list(visited.keys())
    for i in range(0, len(node_ids), chunk):
        batch = node_ids[i : i + chunk]
        placeholders = ",".join("?" * len(batch))
        cursor = await db.execute(
            "SELECT id, channel_id, node_kind, qualified_name, source_path, "
            f"attributes FROM graph_nodes WHERE id IN ({placeholders})",
            batch,
        )
        for row in await cursor.fetchall():
            node = _row_to_node(row)
            nodes_by_id[node.id] = node

    results: list[TraversalHit] = []
    for node_id, (depth, path_kinds) in visited.items():
        node = nodes_by_id.get(node_id)
        if node is None:
            continue  # FK гарантирует наличие; страховка от рассинхрона
        results.append(TraversalHit(node=node, depth=depth, path_kinds=path_kinds))

    # Документированный порядок: depth ASC, затем qualified_name ASC.
    results.sort(key=lambda h: (h.depth, h.node.qualified_name))
    return results


# ============================================================================
# Subgraph (для GraphCard / REST)
# ============================================================================

# Дефолтный лимит узлов в подграфе для GraphCard — больше рендерить нет
# смысла (React Flow тормозит, человек не читает). UI помечает truncated.
DEFAULT_SUBGRAPH_MAX_NODES = 150


async def get_subgraph(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    start_qname: str,
    node_kind: str | None = None,
    max_depth: int = 2,
    direction: str = "out",
    edge_kind: str | None = None,
    max_nodes: int = DEFAULT_SUBGRAPH_MAX_NODES,
) -> Subgraph:
    """Собирает подграф вокруг узла start_qname для визуализации (GraphCard).

    Узлы = traverse_bfs(start, max_depth, direction) с cap'ом max_nodes
    (по возрастанию глубины). Рёбра = ИНДУЦИРОВАННЫЕ: только те, у которых
    оба конца попали в отображаемый набор узлов.

    node_kind опционален — без него берётся первый узел с таким именем.
    Если узел не найден — Subgraph с center=None (роут транслирует в 404).
    Валидация max_depth/direction делегируется traverse_bfs (GraphStorageError).
    """
    if node_kind:
        start = await find_node(
            db, channel_id=channel_id, qualified_name=start_qname, node_kind=node_kind,
        )
    else:
        cursor = await db.execute(
            "SELECT id, channel_id, node_kind, qualified_name, source_path, attributes "
            "FROM graph_nodes WHERE channel_id = ? AND qualified_name = ? LIMIT 1",
            (channel_id, start_qname),
        )
        row = await cursor.fetchone()
        start = _row_to_node(row) if row else None

    if start is None:
        return Subgraph(center=None, hits=(), edges=(), total_reached=0, truncated=False)

    hits = await traverse_bfs(
        db, start.id, max_depth=max_depth, direction=direction, edge_kind=edge_kind,
    )
    total_reached = len(hits)
    truncated = total_reached > max_nodes
    capped = hits[:max_nodes]
    node_ids = {h.node.id for h in capped}

    # Индуцированные рёбра: src в наборе И dst в наборе.
    edges: list[GraphEdge] = []
    ids_list = list(node_ids)
    chunk = 800
    for i in range(0, len(ids_list), chunk):
        batch = ids_list[i : i + chunk]
        placeholders = ",".join("?" * len(batch))
        sql = (
            "SELECT id, src_id, dst_id, edge_kind, attributes FROM graph_edges "
            f"WHERE src_id IN ({placeholders})"
        )
        params: list = list(batch)
        if edge_kind:
            sql += " AND edge_kind = ?"
            params.append(edge_kind)
        cursor = await db.execute(sql, params)
        for r in await cursor.fetchall():
            if int(r[2]) in node_ids:  # dst_id тоже отображается
                edges.append(
                    GraphEdge(
                        id=int(r[0]),
                        src_id=int(r[1]),
                        dst_id=int(r[2]),
                        edge_kind=r[3],
                        attributes=json.loads(r[4]) if r[4] else {},
                    )
                )

    return Subgraph(
        center=start,
        hits=tuple(capped),
        edges=tuple(edges),
        total_reached=total_reached,
        truncated=truncated,
    )


# ============================================================================
# Counts + delete
# ============================================================================


async def count_nodes(
    db: aiosqlite.Connection,
    channel_id: str | None = None,
) -> int:
    if channel_id:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM graph_nodes WHERE channel_id = ?",
            (channel_id,),
        )
    else:
        cursor = await db.execute("SELECT COUNT(*) FROM graph_nodes")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def count_edges(
    db: aiosqlite.Connection,
    channel_id: str | None = None,
) -> int:
    if channel_id:
        # edges не имеют прямого channel_id — join через nodes
        cursor = await db.execute(
            """
            SELECT COUNT(*) FROM graph_edges e
            JOIN graph_nodes n ON e.src_id = n.id
            WHERE n.channel_id = ?
            """,
            (channel_id,),
        )
    else:
        cursor = await db.execute("SELECT COUNT(*) FROM graph_edges")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def count_by_kind(
    db: aiosqlite.Connection,
    channel_id: str,
) -> dict[str, int]:
    """Возвращает {node_kind: count} для канала."""
    cursor = await db.execute(
        "SELECT node_kind, COUNT(*) FROM graph_nodes WHERE channel_id = ? GROUP BY node_kind",
        (channel_id,),
    )
    rows = await cursor.fetchall()
    return {row[0]: int(row[1]) for row in rows}


async def delete_channel_graph(
    db: aiosqlite.Connection,
    channel_id: str,
) -> int:
    """Удаляет все nodes канала + cascade edges. Возвращает количество nodes."""
    cursor = await db.execute(
        "SELECT COUNT(*) FROM graph_nodes WHERE channel_id = ?",
        (channel_id,),
    )
    row = await cursor.fetchone()
    count = int(row[0]) if row else 0
    if count == 0:
        return 0

    # Cascade удалит edges автоматически (FK ON DELETE CASCADE).
    await db.execute(
        "DELETE FROM graph_nodes WHERE channel_id = ?",
        (channel_id,),
    )
    await db.commit()
    return count
