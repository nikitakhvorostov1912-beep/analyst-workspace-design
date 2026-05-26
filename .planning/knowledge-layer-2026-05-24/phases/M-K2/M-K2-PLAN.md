---
milestone: M-K2
milestone_name: "Knowledge Foundation — Indexer + L5 базы"
status: in_progress
created_at: "2026-05-26T09:30:00Z"
estimated_weeks: 4-5
phases_total: 11
phases_done: 0
predecessor: "M-K1 (closed 2026-05-26, commit 11575ab)"
---

# M-K2 Plan — Knowledge Foundation + Triple RAG

> Запускаем полноценный indexing pipeline (L1 metadata bulk + L2 baseline)
> и загружаем статические RAG базы (ИТС + БСП). После M-K2 у Knowledge
> Layer есть «мозг»: знает структуру конфигурации, ИТС-стандарты и
> БСП-паттерны, но ещё не понимает поведенческих связей (это M-K3).

## Definition of Done (из PLAN.md)

- [ ] При подключении нового канала пользователь видит «Изучаю вашу базу.
      Прогресс: ...» — индексация в background, SSE прогресс
- [ ] Полная индексация средней УТ 11.5 (~15k BSL): ≤ 10 минут
- [ ] Инкрементальное обновление одного файла: ≤ 2 сек
- [ ] «Что такое БСП.ДлительныеОперации?» — точный ответ с цитатой из
      `ssl_3_2/src/`
- [ ] «Как избежать запроса в цикле?» — цитата ИТС-стандарта с ссылкой
- [ ] Vector store: `semantic_search("выгрузка в эксель") → top-10`
- [ ] Configuration type определяется автоматически с confidence score

## Атомарная декомпозиция

| Phase | Subject | Effort | Зависит от |
|-------|---------|--------|------------|
| **M-K2.1** | **Indexer Skeleton** — extract bulk-refresh из `connections.metadata_suggest` в reusable `knowledge/indexer.py` + Pydantic `IndexerProgress` + tests | 0.5 дня | M-K1 dossier/storage |
| M-K2.2 | Indexer State Machine — migration v12 `index_runs` table + endpoint POST `/knowledge/{ch}/index/start` + GET `/.../index/status` + background asyncio.Task | 1 день | M-K2.1 |
| M-K2.3 | Incremental Update — mtime + change detection (delta indexer) | 1 день | M-K2.2 |
| M-K2.4 | MCP Result Cache — TTL для повторных `get_metadata`/`execute_query` (per-call key) | 0.5 дня | M-K2.1 |
| M-K2.5 | Vector Store — sqlite-vec init + schema migration v13 + base API | 0.5 дня | — (parallelizable) |
| M-K2.6 | Embedding Pipeline — BGE-M3 client (FastEmbed) + download-on-first-run | 1.5 дня | M-K2.5 |
| M-K2.7 | ИТС RAG — статический crawler + parser + vector index `tools/v8327doc + v8std` | 2 дня | M-K2.6 |
| M-K2.8 | БСП Pattern Index — `ssl_3_1 + ssl_3_2/src` parser + vector index | 1.5 дня | M-K2.6 |
| M-K2.9 | Configuration Type Detection — эвристика по metadata (УТ/ERP/БП/УСО/custom) с confidence score | 1 день | M-K2.1 |
| M-K2.10 | UX-6 Indexing Progress UI — SSE-driven modal с прогрессом для frontend | 1 день | M-K2.2 |
| M-K2.11 | OPS-1 Privacy badge «Local Knowledge» — индикатор что dossiers/vectors/embeddings локальные | 0.25 дня | — |
| M-K2.smoke | E2E Playwright (перенесённый M-K1.16) — Multi-MCP полный flow + indexer integration | 1 день | M-K2.2 + M-K2.10 |
| M-K2.SUMMARY | Финальный документ + handoff в M-K3 | 0.5 дня | — |

**Итого:** ~13 рабочих дней ≈ 3 календарных недели solo. С запасом на
неожиданности и review-итерации: **4-5 недель** (из PLAN.md).

## Принципы реализации (унаследованы из M-K1)

1. **Минимально invasive** — расширяем существующие модули, не дублируем.
   Пример: `metadata_suggest` уже имеет inline bulk-refresh → вытащим в
   reusable `indexer.bulk_refresh_metadata_cache()`, заменим inline вызовом.
2. **DDL migrations без alembic** (ADR-005) — `MIGRATIONS_V12`, `_V13` и т.д.
3. **Best-effort** — knowledge layer никогда не валит chat (try/except +
   logger.exception, продолжаем работу).
4. **Per-config storage** — все индексы/embeddings под
   `$ANALYST_HOME/knowledge/<slug>/{metadata,embeddings,graph}/`.
5. **Forward-compat capabilities** — если канал в `mcp_only` mode и не
   поддерживает feature (например change events) — индексер работает в
   degraded mode (полный re-index по таймеру вместо incremental).
6. **Test-first для pure functions** — parser/normalizer/fingerprint покрыты
   100%. Integration tests с aiosqlite in-memory.

## Риски

| ID | Risk | Mitigation |
|----|------|------------|
| R-MK2-01 | BGE-M3 модель 570 MB взрывает Electron installer (183 → 750 MB) | Download-on-first-run + progress UI |
| R-MK2-02 | ИТС crawler упирается в rate-limit | Сначала `v8std-for-humans` (готовый markdown), потом v8327doc |
| R-MK2-03 | sqlite-vec extension не embed-friendly для PyInstaller | Spike в M-K2.5 — план B = numpy + brute-force для < 100k vectors |
| R-MK2-04 | Полная индексация ERP 2.5 > 20 минут (DoD violation) | Batch concurrency через asyncio.gather + progress checkpointing |
| R-MK2-05 | MCP get_metadata pagination на больших базах падает | Retry + chunking по object_type (Документы → потом Регистры → ...) |

## Источники / готовые куски

- `backend/app/routes/connections.py` lines 494-543 — bulk inline write
  (extract в M-K2.1)
- `backend/app/knowledge/dossier.py::fill_cache_entry` — single record write
  (reuse в M-K2.1 для одного объекта)
- `backend/app/knowledge/storage.py::KnowledgeStorage` — куда складывать
  embeddings/graph/cache
- `backend/app/knowledge/fingerprint.py` — slug для shared corpus
- `tools/ssl_3_2/src/` + `tools/ssl_3_1/src/` — БСП исходники (грепабельные)
- `tools/v8std/` — ИТС стандарты в markdown (`zeegin/v8std` form)
- `tools/bsl-atlas` (опционально) — vector RAG если sqlite-vec не зайдёт

## Snapshot: что НЕ делаем в M-K2

- ❌ Knowledge Graph (L2 callgraph / data lineage) — это M-K3
- ❌ Diagnose Engine (L4 «почему») — это M-K3
- ❌ BSL Parser TreeSitter — это M-K3
- ❌ Antipattern Detector — это M-K3
- ❌ GraphCard / DiagnoseCard UI — это M-K3
