---
milestone: M-K1
status: in_progress
started_at: "2026-05-25T22:30:00Z"
branch: "feature/m-k1-foundation"
phases_total: 17
phases_done: 5
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
| M-K1.7 | Capability Discovery Service | pending | — |
| M-K1.8 | MCP Orchestrator unified registry | pending | — |
| M-K1.9 | Backend MCP clients refactor | pending | — |
| M-K1.10 | Frontend useCapability hooks | pending | — |
| M-K1.11 | SourceSelector refactor | pending | — |
| M-K1.12 | Metadata Cache filler | pending | — |
| M-K1.13 | Object Dossier API | pending | — |
| M-K1.14 | UC «расскажи про объект» | pending | — |
| M-K1.15 | Seed 3 MCP (Toolkit/buddy/context) | pending | config готов (G1 done) |
| M-K1.16 | E2E smoke Multi-MCP | pending | — |
| M-K1.17 | SUMMARY + handoff to M-K2 | pending | — |

## Текущая задача

**M-K1.7 Capability Discovery Service** — parsing `experimental.analyst-1c.features`
из MCP initialize response, сохранение в БД (mode/configuration/platform/
ext_version/capabilities/fingerprint через миграцию v11 которая уже готова).

Следующие 11 фаз (M-K1.7-1.17) — это **реальная функциональность Multi-MCP +
Object Dossier**. Каждая фаза 0.5-2 дня, итого 9-13 дней работы.

## Commits в M-K1

```
TBD после первого коммита текущей сессии
```

## Метрики

- **Покрытие новых модулей backend/app/knowledge/**: TBD после M-K1.6 (новые
  тесты 37 для knowledge + 9 для migration v11 = 46)
- **Frontend изменения**: 0 (M-K1.2-1.6 чисто backend)
- **Регрессий**: TBD после full regression
