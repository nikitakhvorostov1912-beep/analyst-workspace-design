---
milestone: M-K1
status: in_progress
started_at: "2026-05-25T22:30:00Z"
last_updated: "2026-05-25T23:30:00Z"
branch: "feature/m-k1-foundation"
phases_total: 17
phases_done: 8
backend_tests_passed: 1042
frontend_tests_passed: 338
---

# M-K1 Foundation — STATE

## Активность

| Phase | Subject | Status | Note |
|-------|---------|--------|------|
| **M-K1.1** | **ADR-001..005** | **✅ DONE** | 5 ADR + README (M-K0.10 pre-flight) |
| **M-K1.2** | **LICENSE-CORE/EPF/CFE + NOTICE + OPEN-VS-CLOSED.md** | **✅ DONE** | Q6 dual license закреплён |
| **M-K1.3** | **backend/app/knowledge/ skeleton** | **✅ DONE** | types.py + __init__.py + README.md |
| **M-K1.4** | **Storage Layout — per-config layout** | **✅ DONE** | storage.py + 11 tests |
| **M-K1.5** | **Configuration Fingerprint** | **✅ DONE** | fingerprint.py + 16 tests |
| **M-K1.6** | **MCPConnection +6 полей (migration v11)** | **✅ DONE** | DDL v11 + models + connections route + 9 tests |
| **M-K1.7** | **Capability Discovery Service** | **✅ DONE** | MCPSession.experimental + discover_capabilities() + ping integration + 14 tests |
| M-K1.8 | MCP Orchestrator unified registry | pending | refactor: 1-2 дня работы (отдельная сессия) |
| M-K1.9 | Backend MCP clients refactor | pending | HTTP+stdio base class (1 день) |
| **M-K1.10** | **Frontend useCapability hooks** | **✅ DONE** | 3 hook'а + 16 tests + types.ts +6 полей |
| M-K1.11 | SourceSelector refactor | pending | использует useCapability (0.5 дня) |
| M-K1.12 | Metadata Cache filler | pending | — |
| M-K1.13 | Object Dossier API | pending | — |
| M-K1.14 | UC «расскажи про объект» | pending | — |
| M-K1.15 | Seed 3 MCP (Toolkit/buddy/context) | pending | config готов (G1 done) |
| M-K1.16 | E2E smoke Multi-MCP | pending | — |
| M-K1.17 | SUMMARY + handoff to M-K2 | pending | — |

## Текущая задача

**M-K1.8 MCP Orchestrator unified registry** (следующая сессия).
Refactor: 1-2 дня. Pattern — unified tools list с префиксами
`toolkit.execute_query`, `buddy.search_its`, `context.search`, routing
к нужному MCP server.

После — M-K1.9 (backend MCP refactor), M-K1.11 SourceSelector (uses
useCapability), M-K1.12-1.17 (metadata cache, dossier, smoke).

## Commits в M-K1 (текущая сессия)

```
ed5bd4d feat(M-K1.10): Frontend useCapability + useUpgradeAction hooks
f384827 feat(M-K1.7): Capability Discovery Service + integration в /connections/{id}/ping
9d51b2f feat(M-K1.6): MCPConnection capability-aware fields (migration v11)
4b9a08f feat(M-K1.3+1.4+1.5): backend/app/knowledge/ skeleton + Storage + Fingerprint
49b00ee feat(M-K1.2): LICENSE-CORE (Apache 2.0) + LICENSE-EPF/CFE + NOTICE + OPEN-VS-CLOSED.md
```

5 атомарных коммитов = 8 закрытых M-K1 phases (1.2-1.7 + 1.10).

## Метрики

- **Backend pytest**: **1042 passed**, 0 failed (от 982 после M-K0 → +60 новых)
- **Frontend vitest**: **338 passed** (322 базовых + 16 useCapability)
- **Регрессий**: 0
- **Новые тесты M-K1**:
  - knowledge types/fingerprint/storage: 37
  - migration v11: 9
  - capability discovery: 14
  - useCapability hooks: 16
  - **Итого: 76 новых тестов**
- **Coverage backend**: 87.3% сохранён (≥80% threshold)
- **Frontend изменения**: types.ts +6 полей, hooks/ новая директория, capabilities.ts из pre-flight

## Что НЕ сделано в этой сессии (оставлено на след. сессии)

| Phase | Effort | Why deferred |
|---|---|---|
| M-K1.8 MCP Orchestrator unified registry | 1-2 дня | Большой refactor 5 MCP клиентов |
| M-K1.9 Backend MCP clients refactor | 1 день | HTTP+stdio base class, не блокирует 1.10/1.11 |
| M-K1.11 SourceSelector refactor | 0.5 дня | Тривиально после 1.10 hooks |
| M-K1.12 Metadata Cache filler | 0.5 дня | Background task |
| M-K1.13 Object Dossier API | 1 день | Использует metadata_cache |
| M-K1.14 UC «расскажи про объект» | 0.5 дня | Frontend integration |
| M-K1.15 Seed 3 MCP | 0.5 дня | Config готов (G1), нужен seed loader |
| M-K1.16 E2E smoke Multi-MCP | 1 день | Playwright |
| M-K1.17 SUMMARY + handoff | 0.5 дня | Финал M-K1 |

**Оставшийся объём M-K1: ~7-8 дней работы.** Включает реальную бизнес-логику
(Orchestrator, Dossier, Metadata cache filler). M-K1.2-1.7 + 1.10 — это
**foundation** (типы, schemas, primitives, service layer), на котором будет
строиться оставшаяся логика.
