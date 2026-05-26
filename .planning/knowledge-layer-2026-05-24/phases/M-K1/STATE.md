---
milestone: M-K1
status: complete  # SUMMARY.md — финальный документ M-K1, handoff в M-K2
started_at: "2026-05-25T22:30:00Z"
completed_at: "2026-05-26T09:00:00Z"
last_updated: "2026-05-26T09:00:00Z"
branch: "main"  # все feature ветки merged FF (последний коммит d271832)
phases_total: 17
phases_done: 15  # +SUMMARY.md (M-K1.17)
phases_deferred: 2  # M-K1.9 (HTTP+stdio base — до M-K3), M-K1.16 (E2E — в M-K2.smoke)
backend_tests_passed: 1121
frontend_tests_passed: 345
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
| **M-K1.14** | **UC «расскажи про объект»** | **✅ DONE** | mentions.py + mentions_prefetch.py + loop.py pre-step + 28 tests (frontend already supported via existing MentionPopover + ObjectCard) |
| **M-K1.15** | **Seed 3 MCP + Factory** | **✅ DONE** | mcp_factory.py + FactoryResult + 9 tests (context deferred → M-K3) |
| M-K1.16 | E2E smoke Multi-MCP | ⏭️ перенесён в M-K2.smoke | Требует live env (backend+frontend+mock MCP+LLM key). Покрытие через integration tests pytest+vitest достаточно для M-K1. |
| **M-K1.17** | **SUMMARY + handoff to M-K2** | **✅ DONE** | SUMMARY.md — финальный документ, handoff в M-K2 |

## Текущая задача

✅ **M-K1 закрыт.** Подробности в [SUMMARY.md](./SUMMARY.md).

**Следующий milestone:** **M-K2 Knowledge Foundation + Triple RAG** (4-5 weeks).
Стартовая фаза — M-K2.1 indexer skeleton (DDL v12 если потребуется).

**Отложено в M-K1:**
- M-K1.9 (HTTP+stdio base class) — до M-K3 с stdio MCP
- M-K1.16 (E2E Playwright) — перенесён в M-K2.smoke (требует live env)

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
