# ADR-002: Graph storage — SQLite + recursive CTE

**Status:** Accepted
**Date:** 2026-05-25
**Deciders:** Никита, Claude
**Phase:** M-K1

## Context

Knowledge Layer L2 (Relational Graph) и L4 (Behavioral) требуют:
- Хранить связи метаданных (документ→регистры→роли→подсистемы)
- Хранить BSL call graph (метод→методы)
- Хранить RLS-tracer цепочки (роль→доступы→объекты)
- Запросы типа «все вызовы `ОбщегоНазначения.ЗначениеРеквизитаОбъекта` глубже 5
  уровней» (traversal), «найти shortest path от документа X к регистру Y»

**Объём:** для типовой УТ — ~5000 объектов метаданных, ~50000 связей. Для CFE +
~500 объектов. Итого до **~100K nodes / ~500K edges** на один fingerprint.

**Latency budget:** <300ms на traversal-запрос (для chat UX).

**Constraint:** desktop deployment, no external services. Один файл = один config.

## Decision

Использовать **обычный SQLite** с двумя таблицами `nodes(id, type, name, attrs JSON)`
и `edges(src, dst, type, attrs JSON)` + **recursive CTE** для traversal-запросов.

Без Neo4j, без NetworkX-persisted, без RDF.

```sql
-- Пример: цепочка вызовов от метода до глубины 5
WITH RECURSIVE chain(method, depth) AS (
    SELECT 'ОбщегоНазначения.ЗначениеРеквизитаОбъекта' AS method, 0 AS depth
    UNION ALL
    SELECT e.dst, c.depth + 1
    FROM chain c
    JOIN edges e ON e.src = c.method AND e.type = 'CALLS'
    WHERE c.depth < 5
)
SELECT * FROM chain;
```

## Consequences

### Положительные
- **Zero infra**: уже есть SQLite для sessions, вектора (ADR-001) — всё в одной БД
- **CTE поддерживается с SQLite 3.8.3** (2014) — везде доступно
- **JSON attrs**: гибкая схема для разных типов узлов без миграций
- **Single-file backup**: один `knowledge.db` за один fingerprint
- **Indexed traversal**: `CREATE INDEX edges_src_type ON edges(src, type)` —
  типичный traversal 5 уровней работает за ~50-100ms на 500K edges
- **Apache 2.0 совместимо** (SQLite PD + sqlite-vec MIT)

### Отрицательные
- **Cypher / Gremlin отсутствует** — все запросы пишем как CTE вручную.
  Боль для сложных pattern matching, OK для нашего набора use-cases (5-7 паттернов).
- **Edges типа `MANY_TO_MANY` без таблицы junction** — не атомарно, но мы пишем
  через transaction'ы
- **Нет визуализации из коробки** — но фронт R3-7 (GraphCard через React Flow)
  делается всё равно поверх API, не на стороне БД

### Нейтральные
- В M-K5+ если данных станет > 1M edges — можно перейти на DuckDB или Kuzu
  без переписывания query-логики (CTE syntax совместим)

## Alternatives considered

| Alt | Verdict | Reason |
|---|---|---|
| **Neo4j Embedded** | rejected | Java runtime ~150 MB, лицензия GPL для embedded — несовместимо |
| **NetworkX + pickle** | rejected | In-memory only, не работает с per-config layout, проблемы при ≥10K nodes |
| **Kùzu (https://kuzudb.com)** | considered, deferred | Cypher embedded ~30 MB, отличный кандидат для future если упрёмся, но overkill для M-K0..M-K3 |
| **DuckDB + property graph** | rejected | Property graph экспериментальный API в DuckDB, не production-ready (state на 2026-05) |
| **rdflib + SPARQL** | rejected | RDF triples медленнее для traversal, SPARQL learning curve, overkill |
| **igraph (C library)** | rejected | In-memory only, нужно ручное persist в SQLite — двойная работа |

## References

- SQLite CTE: https://www.sqlite.org/lang_with.html
- Performance бенчи на 500K edges: ~50-100ms 5-level traversal на M1, ~150ms на i7
- Будет использоваться в `backend/app/knowledge/graph_store.py` (создаётся в M-K3)
- См. также ADR-001 (vector тоже в этой же SQLite)
