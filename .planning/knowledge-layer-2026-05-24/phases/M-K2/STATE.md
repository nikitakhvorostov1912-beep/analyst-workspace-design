---
milestone: M-K2
status: in_progress
started_at: "2026-05-26T09:30:00Z"
last_updated: "2026-05-26T10:00:00Z"
branch: "feature/m-k2-indexer"
parent_branch_merged_to_main: "feature/m-k1-summary (11575ab)"
phases_total: 13   # 11 content + smoke + summary
phases_done: 5     # +M-K2.5 Vector Store + M-K2.6 Embedding Pipeline
backend_tests_passed: 1210  # +18 vector_store + +19 embeddings vs 1173
frontend_tests_passed: 361
---

# M-K2 Knowledge Foundation — STATE

## Активность

| Phase | Subject | Status | Note |
|-------|---------|--------|------|
| **M-K2.1** | **Indexer Skeleton** | **✅ DONE** | indexer.py + NormalizedMetadata + IndexerProgress + 29 tests |
| **M-K2.2** | **Indexer State Machine + Endpoints** | **✅ DONE** | migration v12 + indexer_state.py + POST/GET /knowledge/{ch}/index/* + background asyncio task + 23 tests (16 state + 7 routes) |
| M-K2.3 | Incremental Update | pending | mtime + delta indexer |
| M-K2.4 | MCP Result Cache | pending | TTL для повторных вызовов |
| **M-K2.5** | **Vector Store (sqlite-vec)** | **✅ DONE** | sqlite-vec 0.1.9 + migration v13 vec_objects + vector_store.py (load_sqlite_vec, init_vector_store, upsert_embedding, semantic_search, delete_channel_embeddings, count_embeddings) + 18 tests |
| **M-K2.6** | **Embedding Pipeline** | **✅ DONE** | embeddings.py с OpenAIEmbeddingClient (cloud-only, text-embedding-3-small 1536-D) + MockEmbeddingClient (детерминированный для тестов) + EmbeddingClient Protocol + 19 tests. BGE-M3 local отложен до M-K5 distribution. |
| M-K2.7 | ИТС RAG | pending | Crawler + parser + vector index |
| M-K2.8 | БСП Pattern Index | pending | ssl_3_1 + ssl_3_2/src parser |
| M-K2.9 | Configuration Type Detection | pending | УТ/ERP/БП/УСО/custom heuristic |
| **M-K2.10** | **UX-6 Indexing Progress UI** | **✅ DONE** | useIndexerStatus hook + IndexerProgress компонент + интеграция в ChannelSelector dropdown + 16 vitest тестов |
| M-K2.11 | OPS-1 Privacy badge | pending | «Local Knowledge» indicator |
| M-K2.smoke | E2E Playwright | pending | Перенесённый из M-K1.16 |
| M-K2.SUMMARY | Финальный документ | pending | Handoff в M-K3 |

## Текущая задача

**M-K2.3 Incremental Update** — delta indexer на основе mtime / change events.
Альтернативно: **M-K2.5 Vector Store** (sqlite-vec init + миграция v13) —
тоже подходит как параллельная ветка (не зависит от M-K2.3).

Решение для следующей сессии (пользователь / триаж):
- M-K2.3 если приоритет — UX «быстрое обновление при изменении одного объекта»
- M-K2.5/2.6 если приоритет — RAG поверх metadata (embeddings + semantic search)

M-K2.4 (MCP Result Cache) — короткая фаза, можно вклинить когда удобно.

## Готовые куски из M-K1

- `KnowledgeStorage` per-config layout
- `ConfigurationFingerprint` 12-hex slug
- `fill_cache_entry()` (one record write)
- `get_dossier()` (read by path)
- `metadata_cache` table (миграция v5)
- Inline bulk-refresh в `metadata_suggest` (extract source)
