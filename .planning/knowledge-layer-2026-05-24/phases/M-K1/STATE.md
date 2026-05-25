---
milestone: M-K1
status: in_progress
started_at: "2026-05-25T22:30:00Z"
last_updated: "2026-05-26T00:30:00Z"
branch: "feature/m-k1-orchestrator"
parent_branch_merged_to_main: "feature/m-k1-foundation (c646fb3)"
phases_total: 17
phases_done: 13
backend_tests_passed: 1093
frontend_tests_passed: 357  # +19 (ModeBadge 7 + useCapability 16, было 322 + 16 + 7)
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
| **M-K1.8** | **MCP Orchestrator unified registry** | **✅ DONE** | mcp_orchestrator.py + Protocol + 32 tests |
| M-K1.9 | Backend MCP clients refactor | pending | HTTP+stdio base class — отложено (нет stdio MCP пока) |
| **M-K1.10** | **Frontend useCapability hooks** | **✅ DONE** | 3 hook'а + 16 tests + types.ts +6 полей |
| **M-K1.11** | **ChannelSelector ModeBadge** | **✅ DONE** | ModeBadge (mcp/EPF/CFE) + 7 tests + integration |
| **M-K1.12** | **Metadata Cache filler** | **✅ DONE** | fill_cache_entry helper + idempotent (full bulk filler — M-K2 indexer) |
| **M-K1.13** | **Object Dossier API** | **✅ DONE** | GET /knowledge/{ch}/dossier/{path} + dossier.py + 10 tests |
| M-K1.14 | UC «расскажи про объект» | pending | Frontend chat integration (0.5 дня) |
| **M-K1.15** | **Seed 3 MCP + Factory** | **✅ DONE** | mcp_factory.py + FactoryResult + 9 tests (context deferred → M-K3) |
| M-K1.16 | E2E smoke Multi-MCP | pending | Playwright (1 день) |
| M-K1.17 | SUMMARY + handoff to M-K2 | pending | финал (0.5 дня) |
| M-K1.12 | Metadata Cache filler | pending | — |
| M-K1.13 | Object Dossier API | pending | — |
| M-K1.14 | UC «расскажи про объект» | pending | — |
| M-K1.15 | Seed 3 MCP (Toolkit/buddy/context) | pending | config готов (G1 done) |
| M-K1.16 | E2E smoke Multi-MCP | pending | — |
| M-K1.17 | SUMMARY + handoff to M-K2 | pending | — |

## Текущая задача

**M-K1.14 UC «расскажи про объект»** — frontend integration: распознавание
`@Документ.ОПП` в chat input → orchestrator вызывает knowledge_dossier
internal tool → выводит Object Card.

После — M-K1.16 E2E Playwright smoke + M-K1.17 SUMMARY.

## Branches / Merge

- `feature/m-k0-stabilization` → **merged в main** (FF, 26 commits)
- `feature/m-k1-foundation` → **merged в main** (FF, 6 commits)
- `feature/m-k1-orchestrator` ← current, 2 коммита поверх main

## Commits в M-K1 (за две сессии)

**Сессия 1 (на ветке feature/m-k1-foundation, merged):**
```
c646fb3 docs(M-K1): STATE 8/17 phases done
ed5bd4d feat(M-K1.10): Frontend useCapability + useUpgradeAction hooks
f384827 feat(M-K1.7): Capability Discovery Service + ping integration
9d51b2f feat(M-K1.6): MCPConnection capability-aware fields (migration v11)
4b9a08f feat(M-K1.3+1.4+1.5): knowledge/ skeleton + Storage + Fingerprint
49b00ee feat(M-K1.2): LICENSE-CORE + LICENSE-EPF/CFE + NOTICE + OPEN-VS-CLOSED.md
```

**Сессия 2 (на ветке feature/m-k1-orchestrator):**
```
TBD       feat(M-K1.11): ChannelSelector + ModeBadge integration
1c786d2   feat(M-K1.8+1.12+1.13+1.15): Orchestrator + Factory + Dossier API
```

8 атомарных коммитов = **13 закрытых M-K1 phases** (1.2-1.8 + 1.10-1.13 + 1.15).

## Метрики (cumulative обеих сессий)

- **Backend pytest**: **1093 passed**, 0 failed (от 982 после M-K0 → +111 новых)
- **Frontend vitest**: **357 passed** (от 322 → +35: useCapability 16 + ModeBadge 7 + остальные)
- **Регрессий**: 0
- **Новые тесты M-K1 (обе сессии)**:
  - knowledge types/fingerprint/storage: 37
  - migration v11: 9
  - capability discovery: 14
  - MCP orchestrator: 32
  - MCP factory: 9
  - knowledge dossier + route: 10
  - useCapability hooks: 16
  - ModeBadge: 7
  - **Итого: 134 новых теста**
- **Coverage backend**: 87.3% сохранён (≥80% threshold)
- **Новых модулей backend**:
  - `app/knowledge/` (types, fingerprint, storage, dossier)
  - `app/services/` (capability_discovery)
  - `app/orchestrator/mcp_orchestrator.py` + `mcp_factory.py`
  - `app/routes/knowledge.py`
- **Новых модулей frontend**:
  - `hooks/useCapability.ts`
  - `components/shell/ModeBadge.tsx`
  - `lib/capabilities.ts` + `lib/card-registry.ts` (из pre-flight)

## Что НЕ сделано (оставлено на след. сессии)

| Phase | Effort | Why deferred |
|---|---|---|
| M-K1.9 Backend MCP clients refactor | 1 день | HTTP+stdio base class — stdio пока не нужен (mcp-bsl-context отложен до M-K3) |
| M-K1.14 UC «расскажи про объект» frontend | 0.5 дня | Chat input `@Документ.ОПП` parser + Object Card rendering |
| M-K1.16 E2E smoke Multi-MCP | 1 день | Playwright тест на full flow |
| M-K1.17 SUMMARY + handoff to M-K2 | 0.5 дня | Финал M-K1 |

**Оставшийся объём M-K1: ~3 дня.** Включая frontend chat integration и
E2E. M-K1.9 опционально (откладывается до stdio MCP).
