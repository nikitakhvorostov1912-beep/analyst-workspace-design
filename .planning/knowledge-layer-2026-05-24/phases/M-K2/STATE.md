---
milestone: M-K2
status: in_progress
started_at: "2026-05-26T09:30:00Z"
last_updated: "2026-05-26T19:00:00Z"
branch: "feature/m-k2-its-rag"
parent_branch_merged_to_main: "feature/m-k2-indexer (44049e0)"
phases_total: 13   # 11 content + smoke + summary
phases_done: 7     # +M-K2.7 ИТС RAG
backend_tests_passed: 1342  # +114 ИТС RAG (36+25+11+14+28+6 + регрессии)
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
| **M-K2.7** | **ИТС RAG** | **✅ DONE** | Полный pipeline v8std → chunk → embed → vec_objects + its_chunks + search_its tool в LLM. Migration v14. Модули: its_loader.py (5 категорий v8std, 36 тестов) + its_chunker.py (header-based split, code-fence safe, 25 тестов) + its_indexer.py (idempotent через chunk_hash, batch embed, 11 тестов) + its_search.py (semantic_search → JOIN, 14 тестов) + its_tool.py (OpenAI function schema + singleton embedding client, 28 тестов). Settings: ITS_ENABLED / ITS_EMBEDDING_* / ITS_DOCS_ROOT. Endpoints: POST /knowledge/its/reload + GET /knowledge/its/status (6 тестов). LLM tool wired в loop.py через _build_openai_tools + async dispatch перед clarify. Сумма: 120+ тестов. |
| M-K2.8 | БСП Pattern Index | pending | ssl_3_1 + ssl_3_2/src parser |
| **M-K2.9** | **Configuration Type Detection** | **✅ DONE** | config_detection.py: 7 known sigs (УТ/ERP/КА/БП/БГУ/ЗУП/УСО) + intersection scoring + custom fallback. Интегрировано в indexer.bulk_refresh post-success hook (best-effort UPDATE mcp_connections.configuration). 18 tests включая anti-conflict signature overlap test. |
| **M-K2.10** | **UX-6 Indexing Progress UI** | **✅ DONE** | useIndexerStatus hook + IndexerProgress компонент + интеграция в ChannelSelector dropdown + 16 vitest тестов |
| M-K2.11 | OPS-1 Privacy badge | pending | «Local Knowledge» indicator |
| M-K2.smoke | E2E Playwright | pending | Перенесённый из M-K1.16 |
| M-K2.SUMMARY | Финальный документ | pending | Handoff в M-K3 |

## Текущая задача

Закрыто 7/13. Остались (priority по PLAN.md):

**M-K2.3 Incremental Update** — delta indexer на основе mtime / change events.
Не зависит от M-K2.7 — параллельная ветка.

**M-K2.8 БСП Pattern Index** — переиспользует ITS RAG pipeline (loader+chunker+
indexer+search) для tools/ssl_3_1+3_2/src. Большая часть инфраструктуры уже
готова; нужен `bsp_loader.py` (BSL модули вместо markdown) + alternate channel
`_bsp` или раздельные channel_ids.

**M-K2.4 MCP Result Cache** — короткая, можно вклинить когда удобно.

**M-K2.11 OPS-1 Privacy badge** — UI индикатор «Local Knowledge».

**M-K2.smoke** — E2E Playwright (multi-MCP + indexer + ИТС tool).

**M-K2.SUMMARY** — финальный handoff в M-K3 (Knowledge Graph + Behavioral).

## Готовые куски из M-K1

- `KnowledgeStorage` per-config layout
- `ConfigurationFingerprint` 12-hex slug
- `fill_cache_entry()` (one record write)
- `get_dossier()` (read by path)
- `metadata_cache` table (миграция v5)
- Inline bulk-refresh в `metadata_suggest` (extract source)
