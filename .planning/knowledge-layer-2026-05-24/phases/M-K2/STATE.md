---
milestone: M-K2
status: complete
started_at: "2026-05-26T09:30:00Z"
completed_at: "2026-05-26T23:45:00Z"
last_updated: "2026-05-26T23:45:00Z"
branch: "feature/m-k2-summary"
parent_branch_merged_to_main: "feature/m-k2-knowledge-badge (d10d72d)"
phases_total: 13
phases_done: 12        # 11 content phases + SUMMARY
phases_deferred: 1     # M-K2.smoke (E2E Playwright)
backend_tests_passed: 1472
frontend_tests_passed: 378
---

# M-K2 Knowledge Foundation — STATE

## Активность

| Phase | Subject | Status | Note |
|-------|---------|--------|------|
| **M-K2.1** | **Indexer Skeleton** | **✅ DONE** | indexer.py + NormalizedMetadata + IndexerProgress + 29 tests |
| **M-K2.2** | **Indexer State Machine + Endpoints** | **✅ DONE** | migration v12 + indexer_state.py + POST/GET /knowledge/{ch}/index/* + background asyncio task + 23 tests (16 state + 7 routes) |
| **M-K2.3** | **Incremental Update** | **✅ DONE** | indexer.py: compute_cache_diff (pure function) + write_cache_batch_incremental (UPSERT added/updated + DELETE removed, single transaction). CacheDiff dataclass: added/updated/removed/unchanged + total_changes property. bulk_refresh_metadata_cache получил incremental:bool=True (default). В incremental mode: objects_written = added+updated, objects_skipped = unchanged. fetched_at сохраняется для unchanged rows. Legacy mode (incremental=False) — старое DELETE+INSERT. 15 тестов: pure diff (6 сценариев), batch incremental (5: empty/remove/update/isolation/preserve fetched_at), CacheDiff.total_changes, bulk_refresh integration через FakeMCP (skips unchanged / detects changes / legacy mode). |
| **M-K2.4** | **MCP Result Cache** | **✅ DONE** | mcp_cache.py: TTL-кеш для get_metadata / find_references / get_access_rights / get_bsl_syntax_help / get_link_of_object / get_object_by_link (CACHEABLE_TOOLS). Key = (channel_id, tool_name, sha256(canonical JSON args)) — sort_keys, ensure_ascii=False. LRU-like eviction (10% самых старых). Settings: MCP_CACHE_ENABLED/TTL_S/MAX_SIZE (defaults 120s / 500 records). Singleton с asyncio.Lock, инвалидация per channel + clear. Hit/miss/eviction counters для будущего admin endpoint. Wired в _execute_mcp_tool (loop.py) — channel_id передаётся из ChatRequest. 34 теста: hash determinism, isolation, TTL expiry, eviction, invalidate_channel, integration через FakeMCP (cache hit не зовёт MCP). |
| **M-K2.5** | **Vector Store (sqlite-vec)** | **✅ DONE** | sqlite-vec 0.1.9 + migration v13 vec_objects + vector_store.py (load_sqlite_vec, init_vector_store, upsert_embedding, semantic_search, delete_channel_embeddings, count_embeddings) + 18 tests |
| **M-K2.6** | **Embedding Pipeline** | **✅ DONE** | embeddings.py с OpenAIEmbeddingClient (cloud-only, text-embedding-3-small 1536-D) + MockEmbeddingClient (детерминированный для тестов) + EmbeddingClient Protocol + 19 tests. BGE-M3 local отложен до M-K5 distribution. |
| **M-K2.7** | **ИТС RAG** | **✅ DONE** | Полный pipeline v8std → chunk → embed → vec_objects + its_chunks + search_its tool в LLM. Migration v14. Модули: its_loader.py (5 категорий v8std, 36 тестов) + its_chunker.py (header-based split, code-fence safe, 25 тестов) + its_indexer.py (idempotent через chunk_hash, batch embed, 11 тестов) + its_search.py (semantic_search → JOIN, 14 тестов) + its_tool.py (OpenAI function schema + singleton embedding client, 28 тестов). Settings: ITS_ENABLED / ITS_EMBEDDING_* / ITS_DOCS_ROOT. Endpoints: POST /knowledge/its/reload + GET /knowledge/its/status (6 тестов). LLM tool wired в loop.py через _build_openai_tools + async dispatch перед clarify. Сумма: 120+ тестов. |
| **M-K2.8** | **БСП Pattern Index** | **✅ DONE** | Полный pipeline ssl_3_1+ssl_3_2 → BSL parser → embed → vec_objects + bsp_chunks + search_bsp tool в LLM. Migration v15. Модули: bsp_loader.py (BSL parser с balanced parens, doc-comment collect, public region filter — 34 теста + 4 migration) + bsp_indexer.py (channel_id="_bsp", per-version hash cache, batch embed, multi-root support — 20 тестов) + bsp_search.py (semantic_search → JOIN + version_filter) + bsp_tool.py (OpenAI function schema с enum version + переиспользует embedding client от ИТС — 21 тест включая admin endpoints). Settings: BSP_ENABLED / BSP_SSL_ROOTS / is_bsp_ready. Endpoints: POST /knowledge/bsp/reload + GET /knowledge/bsp/status. LLM tool wired в loop.py рядом с search_its (отдельная dispatch ветка). Сумма: 75+ тестов. |
| **M-K2.9** | **Configuration Type Detection** | **✅ DONE** | config_detection.py: 7 known sigs (УТ/ERP/КА/БП/БГУ/ЗУП/УСО) + intersection scoring + custom fallback. Интегрировано в indexer.bulk_refresh post-success hook (best-effort UPDATE mcp_connections.configuration). 18 tests включая anti-conflict signature overlap test. |
| **M-K2.10** | **UX-6 Indexing Progress UI** | **✅ DONE** | useIndexerStatus hook + IndexerProgress компонент + интеграция в ChannelSelector dropdown + 16 vitest тестов |
| **M-K2.11** | **OPS-1 Privacy badge** | **✅ DONE** | KnowledgeBadge.tsx + useKnowledgeStatus.ts хук. Fetch /knowledge/its/status + /bsp/status параллельно через Promise.allSettled (один упал → второй всё равно). Компактный badge в Header: status dot (зелёный/жёлтый/серый) + label «ИТС 2543 · БСП 1820». Hover/click → popover с подробностями: chunks/methods counts, by_version разбивка БСП, кнопка-инструкция /reload если пусто. Privacy-нотификация: «данные локальные, query-text отправляется в OpenAI для embedding». frontend/lib/api.ts: getITSStatus / getBSPStatus + типы. Wired в shell/Header.tsx между UpdateBanner и AnonymizationStatus. 17 vitest (10 hook + 7 компонент): mount fetch, anyReady/bothReady логика, totalEntries sum, error tolerance (один из двух упал), popover open/close, privacy block visible. Frontend tests: 361 → 378. |
| M-K2.smoke | E2E Playwright | ⏸ deferred → M-K3.smoke | Требует live backend + MCP fixture, CI ещё не настроен |
| **M-K2.SUMMARY** | **Финальный документ** | **✅ DONE** | См. `SUMMARY.md` рядом — handoff в M-K3 |

## Финал

M-K2 закрыт SUMMARY 2026-05-26. 12/13 done (M-K2.smoke deferred → M-K3.smoke).

Следующая сессия Claude: M-K3.1 — TreeSitter BSL setup + AST extractor.
См. `SUMMARY.md` для полного handoff'а.

## Готовые куски из M-K1

- `KnowledgeStorage` per-config layout
- `ConfigurationFingerprint` 12-hex slug
- `fill_cache_entry()` (one record write)
- `get_dossier()` (read by path)
- `metadata_cache` table (миграция v5)
- Inline bulk-refresh в `metadata_suggest` (extract source)
