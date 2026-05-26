---
milestone: M-K2
status: in_progress
started_at: "2026-05-26T09:30:00Z"
last_updated: "2026-05-26T09:30:00Z"
branch: "feature/m-k2-indexer"
parent_branch_merged_to_main: "feature/m-k1-summary (11575ab)"
phases_total: 13   # 11 content + smoke + summary
phases_done: 0
backend_tests_passed: 1121
frontend_tests_passed: 345
---

# M-K2 Knowledge Foundation — STATE

## Активность

| Phase | Subject | Status | Note |
|-------|---------|--------|------|
| M-K2.1 | Indexer Skeleton | 🔄 in_progress | Extract bulk-refresh + IndexerProgress + tests |
| M-K2.2 | Indexer State Machine | pending | Migration v12 + endpoints + background task |
| M-K2.3 | Incremental Update | pending | mtime + delta indexer |
| M-K2.4 | MCP Result Cache | pending | TTL для повторных вызовов |
| M-K2.5 | Vector Store (sqlite-vec) | pending | Migration v13 + base API |
| M-K2.6 | Embedding Pipeline (BGE-M3) | pending | FastEmbed + download-on-first-run |
| M-K2.7 | ИТС RAG | pending | Crawler + parser + vector index |
| M-K2.8 | БСП Pattern Index | pending | ssl_3_1 + ssl_3_2/src parser |
| M-K2.9 | Configuration Type Detection | pending | УТ/ERP/БП/УСО/custom heuristic |
| M-K2.10 | UX-6 Indexing Progress UI | pending | SSE modal frontend |
| M-K2.11 | OPS-1 Privacy badge | pending | «Local Knowledge» indicator |
| M-K2.smoke | E2E Playwright | pending | Перенесённый из M-K1.16 |
| M-K2.SUMMARY | Финальный документ | pending | Handoff в M-K3 |

## Текущая задача

**M-K2.1 Indexer Skeleton.** Цель — вытащить bulk-refresh metadata_cache
из inline кода `connections.metadata_suggest` в reusable модуль
`backend/app/knowledge/indexer.py`. Это позволит M-K2.2 строить state
machine и endpoint поверх чистой функции, не таская с собой HTTP-обвязку.

## Готовые куски из M-K1

- `KnowledgeStorage` per-config layout
- `ConfigurationFingerprint` 12-hex slug
- `fill_cache_entry()` (one record write)
- `get_dossier()` (read by path)
- `metadata_cache` table (миграция v5)
- Inline bulk-refresh в `metadata_suggest` (extract source)
