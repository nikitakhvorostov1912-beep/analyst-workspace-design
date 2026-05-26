---
milestone: M-K2
milestone_name: "Knowledge Foundation — Indexer + Triple RAG"
status: complete
started_at: "2026-05-26T09:30:00Z"
completed_at: "2026-05-26T23:45:00Z"
phases_done: 11
phases_total: 13
phases_deferred: 1   # M-K2.smoke (требует backend + MCP fixture)
phases_summary: 1    # M-K2.SUMMARY (этот документ)
backend_tests: 1472
frontend_tests: 378
new_backend_tests_in_mk2: ~430   # за milestone
backend_coverage_pct: 87+
---

# M-K2 Knowledge Foundation — SUMMARY

> Knowledge Foundation milestone — local-first RAG (ИТС + БСП) + MCP
> Result Cache + Incremental metadata refresh + UI Privacy badge.
> Закрывает мост между M-K1 (capability-aware multi-MCP shell) и M-K3
> (Knowledge Graph + Behavioral Analysis).

## Что закрыто (11 из 13 phases)

| Phase | Subject | Артефакт |
|-------|---------|----------|
| M-K2.1 | Indexer Skeleton | indexer.py + NormalizedMetadata + IndexerProgress |
| M-K2.2 | Indexer State Machine + Endpoints | migration v12 + indexer_state.py + POST/GET /knowledge/{ch}/index/* |
| **M-K2.3** | **Incremental Update** | compute_cache_diff + write_cache_batch_incremental, default mode для bulk_refresh |
| **M-K2.4** | **MCP Result Cache** | mcp_cache.py + integration в _execute_mcp_tool (TTL 120s, max 500) |
| M-K2.5 | Vector Store | sqlite-vec migration v13 + vector_store.py |
| M-K2.6 | Embedding Pipeline | embeddings.py с OpenAI + Mock клиентами |
| **M-K2.7** | **ИТС RAG** | 5 модулей (loader/chunker/indexer/search/tool) + migration v14 + admin endpoints |
| **M-K2.8** | **БСП Pattern Index** | 4 модуля (loader/indexer/search/tool) + migration v15 + admin endpoints |
| M-K2.9 | Configuration Type Detection | config_detection.py: 7 known sigs + intersection scoring |
| M-K2.10 | UX-6 Indexing Progress UI | useIndexerStatus hook + IndexerProgress компонент |
| **M-K2.11** | **OPS-1 Privacy badge** | useKnowledgeStatus hook + KnowledgeBadge компонент в Header |

**Жирным** — phases закрытые в этой сессии (2026-05-26).

## Что отложено (1 phase) + причины

| Phase | Причина |
|-------|---------|
| M-K2.smoke E2E Playwright | Требует live окружения: запущенный backend (port 8010), frontend (port 3010), seeded MCP-канал, ITS_DOCS_ROOT + BSP_SSL_ROOTS clonированные в tools/. Без CI на GitHub Actions для AWD (это M-K5 Distribution). Поведения покрыты vitest 378 + pytest 1472. Перенесено в **M-K3.smoke** где будет вместе с graph regression test. |

## Метрики (cumulative за milestone)

- **Backend pytest:** 1472 passed (+351 относительно M-K1 closing 1121)
- **Frontend vitest:** 378 passed (+33 относительно M-K1 closing 345)
- **Backend coverage:** ≥87% (gate сохранён)
- **Production frontend build:** clean, 0 errors, 0 регрессий за milestone
- **Migrations:** v12 (index_runs) → v13 (vec_objects) → v14 (its_chunks) → v15 (bsp_chunks)
- **Branches merged into main (FF):**
  - feature/m-k2-indexer → main (2.1+2.2)
  - feature/m-k2-vector-store → main (2.5+2.6)
  - feature/m-k2-config-detection → main (2.9)
  - feature/m-k2-ui-indexer → main (2.10)
  - feature/m-k2-its-rag → main (2.7, 6 commits)
  - feature/m-k2-bsp-index → main (2.8, 3 commits)
  - feature/m-k2-mcp-cache → main (2.4, 1 commit)
  - feature/m-k2-incremental-refresh → main (2.3, 1 commit)
  - feature/m-k2-knowledge-badge → main (2.11, 1 commit)

## Новые модули backend

```
app/knowledge/
├── its_loader.py       — Markdown parser zeegin/v8std (5 категорий)
├── its_chunker.py      — Header-based split с защитой code-fence
├── its_indexer.py      — load → chunk → embed → vec_objects + its_chunks
├── its_search.py       — embed query → semantic_search → JOIN its_chunks
├── its_tool.py         — search_its LLM tool + singleton embedding client
├── bsp_loader.py       — BSL parser экспортных методов CommonModules
├── bsp_indexer.py      — load → embed → vec_objects + bsp_chunks (per-version)
├── bsp_search.py       — semantic_search + version_filter
├── bsp_tool.py         — search_bsp LLM tool (переиспользует ITS client)
├── vector_store.py     — sqlite-vec init + upsert_embedding + semantic_search
├── embeddings.py       — OpenAIEmbeddingClient + MockEmbeddingClient + Protocol
├── indexer.py          — + compute_cache_diff / write_cache_batch_incremental
├── indexer_state.py    — index_runs state machine
└── config_detection.py — 7 known signatures detection

app/orchestrator/
├── mcp_cache.py        — TTL cache для CACHEABLE_TOOLS
└── loop.py             — + search_its + search_bsp dispatch ветки

app/routes/
└── knowledge.py        — + /knowledge/its/{status,reload} + /knowledge/bsp/{status,reload}

app/storage/
└── migrations.py       — + v14 its_chunks + v15 bsp_chunks
```

## Новые модули frontend

```
hooks/
├── useIndexerStatus.ts   — polling /knowledge/{ch}/index/status
└── useKnowledgeStatus.ts — parallel fetch /its/status + /bsp/status

components/knowledge/
├── IndexerProgress.tsx   — кнопка «Изучить базу» + прогресс
└── KnowledgeBadge.tsx    — Header badge с popover + privacy notice

components/shell/
└── Header.tsx            — wired KnowledgeBadge
```

## Архитектурные решения, закреплённые в M-K2

1. **Per-config knowledge namespace через channel_id** (наследовано из M-K1):
   - Реальные MCP-каналы используют UUID v4 (никогда не начинаются с `_`)
   - Зарезервированные: `_its` (ИТС-эмбеддинги), `_bsp` (БСП-эмбеддинги).
   - vec0 виртуальная таблица одна на проект — channel_id фильтрует выдачу.

2. **Один embedding client на всё** (M-K2.7 + M-K2.8):
   - ITS и БСП используют OpenAI text-embedding-3-small (1536-D).
   - Singleton в `its_tool.get_embedding_client()`, БСП переиспользует.
   - Settings: `ITS_EMBEDDING_API_KEY` || `DEFAULT_LLM_API_KEY_OPENAI`.
   - `is_bsp_ready = bsp_enabled AND is_its_ready` — БСП не работает без ИТС client.

3. **Idempotency через SHA-256 chunk_hash** (M-K2.7 + M-K2.8):
   - Каждый chunk (ИТС) или method (БСП) хэшируется по content.
   - Re-index сравнивает hash с существующим — match → skip embedding (no $ cost).
   - `force_reindex=true` — обход для перестройки после смены модели.

4. **MCP Result Cache как process-singleton** (M-K2.4):
   - TTL 120s default, max 500 entries, LRU eviction 10% oldest.
   - Whitelist CACHEABLE_TOOLS — execute_code/execute_query/get_event_log
     НЕ кешируем (мутации / data freshness).
   - Cache key = (channel_id, tool_name, SHA-256 canonical JSON args)
     — sort_keys=True, ensure_ascii=False.

5. **Incremental metadata refresh as default** (M-K2.3):
   - `bulk_refresh_metadata_cache(incremental=True)` по умолчанию.
   - compute_cache_diff: pure function для unit-тестируемости.
   - `fetched_at` сохраняется для unchanged rows (нужно для UI).
   - Legacy режим доступен через `incremental=False`.

6. **DDL migrations linear chain** (наследовано из M-K1 ADR-005):
   - v12 (index_runs) → v13 (vec_objects) → v14 (its_chunks) → v15 (bsp_chunks).
   - Без alembic, без rollback by design (backup рекомендуется pre-migration).

7. **Privacy honesty в UI** (M-K2.11):
   - KnowledgeBadge popover явно сообщает: «query text → OpenAI».
   - Не маскируем cloud-component индекса (embedding API call).
   - Будущий M-K5 distribution может добавить local BGE-M3 — тогда
     badge поменяется на полностью local.

## Handoff в M-K3 (Relational + Behavioral)

### Что готово для M-K3

- ✅ **Triple RAG infrastructure** — keyword (FTS5 из M-K1) + vector
  (vec0 + sqlite-vec) + structural (готовится в M-K3 graph).
- ✅ **Per-channel + reserved namespaces** — `_its` / `_bsp` зарезервированы,
  `_graph` свободен для M-K3 Knowledge Graph.
- ✅ **MCP Result Cache** — повторные get_metadata быстрые (важно для
  graph traversal который дёргает много MCP-вызовов).
- ✅ **Embedding client singleton** — переиспользуется для M-K3 если
  потребуется embed для graph node descriptions.
- ✅ **Loop.py async dispatch pattern** — добавлять новые internal tools
  (search_graph?) тривиально, шаблон отработан на search_its + search_bsp.

### Что M-K3 нужно построить

- **L2 Knowledge Graph** (TreeSitter BSL → AST → graph edges в SQLite +
  CTE per ADR-002): callgraph, data lineage, RLS dependencies.
- **L3 Antipattern Detector** — A1-A11 detection (тернарник, ТекущаяДата,
  запрос в цикле и т.д.) поверх AST.
- **L4 Diagnose Engine** — YAML rulebook «почему этот документ не
  проводится» с traversal по графу.
- **L5 Hybrid Retrieval** — BM25 (FTS5) + vector (M-K2.5) + graph (M-K3)
  с weight tuning.
- **`graph_card` / `diagnose_card`** UI компоненты.
- **`search_graph` / `diagnose_object`** LLM tools.

### Известные ограничения M-K2 для M-K3

- vec0 dim фиксирован 1536 при первом init_vector_store. Смена модели на
  BGE-M3 (1024) или text-embedding-3-large (3072) требует DROP + recreate
  таблицы. M-K3 не должна менять dim без согласования.
- ИТС loader пропускает navigation-файлы (index.md / mcp.md), но если
  v8std structure изменится — _ALLOWED_CATEGORIES придётся апдейтить.
- БСП parser regex-based (не AST). Edge case: метод с `Экспорт` в
  комментарии перед сигнатурой — может ложно матчиться. Тесты покрывают
  типовые случаи; для M-K3 BSL graph нужен полноценный TreeSitter
  парсер (см. ADR-002).
- MCP Result Cache process-local — если backend restart, кеш теряется
  (acceptable — ephemeral by nature).

## Риски, оставшиеся открытыми (из RISKS.md)

| Risk | Status в M-K2 |
|------|---------------|
| R-MK2-01 BGE-M3 570 MB взрывает Electron installer | Отложен: используем OpenAI cloud в M-K2, local model в M-K5 |
| R-MK2-02 ИТС crawler упирается в rate-limit | Mitigated: используем готовый markdown zeegin/v8std (не crawl) |
| R-MK2-03 sqlite-vec не embed-friendly для PyInstaller | Закрыт: работает (M-K2.5 deploy verified) |
| R-MK2-04 Индексация ERP 2.5 > 20 минут | Открыт: chunking сделан, batch concurrency через asyncio.gather TBD M-K3 |
| R-MK2-05 MCP get_metadata pagination падает | Открыт: retry + chunking by object_type — задача для M-K3 indexer overhaul |

## Команда / окружение

- Branch: `feature/m-k2-summary` → merged FF в main (commit hash в `STATE.md`)
- Pre-conditions для M-K3: pip install (no new deps) + node 22 + pnpm 11
- Recommended next session: M-K3.1 — TreeSitter BSL setup + AST extractor

## Подпись

```
M-K2 Knowledge Foundation: complete (11/13 atomic phases done).
Тесты: backend 1472, frontend 378 — все зелёные, 0 регрессий за milestone.
Готов handoff в M-K3 (Relational + Behavioral, ~5-6 weeks).
1 deferred: M-K2.smoke (E2E Playwright) — перенесён в M-K3.smoke.
```
