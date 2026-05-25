# Architecture Decision Records

Реестр архитектурных решений для **Knowledge Layer 1С Аналитик**.

Формат ADR:

```markdown
# ADR-NNN: <Title>

**Status:** Proposed | Accepted | Deprecated | Superseded-by-ADR-XXX
**Date:** YYYY-MM-DD
**Deciders:** Никита, Claude
**Phase:** M-KN (где было принято)

## Context
<В чём проблема, что выбираем>

## Decision
<Что решено, одной фразой>

## Consequences
<Положительные / отрицательные / нейтральные следствия>

## Alternatives considered
<Что рассматривали и почему отвергли>

## References
<Ссылки на код, документацию, обсуждения>
```

## Индекс

| ADR | Title | Status | Phase | Дата |
|-----|-------|--------|-------|------|
| [001](001-vector-db.md) | Vector storage — sqlite-vec | Accepted | M-K1 | 2026-05-25 |
| [002](002-graph-db.md) | Graph storage — SQLite + recursive CTE | Accepted | M-K1 | 2026-05-25 |
| [003](003-embeddings-runtime.md) | Embeddings — FastEmbed + BGE-M3 | Accepted | M-K1 | 2026-05-25 |
| [004](004-capability-discovery.md) | Capability Discovery — через MCP initialize | Accepted | M-K1 | 2026-05-25 |
| [005](005-migrations-strategy.md) | Schema migrations — продолжить DDL (без alembic) | Accepted | M-K1 | 2026-05-25 |

Новые ADR добавляются как `NNN-kebab-title.md` с инкрементальной нумерацией.
