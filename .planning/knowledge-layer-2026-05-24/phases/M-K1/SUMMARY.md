---
milestone: M-K1
status: complete
started_at: "2026-05-25T22:30:00Z"
completed_at: "2026-05-26T09:00:00Z"
phases_done: 14
phases_total: 17
phases_deferred: 3  # M-K1.9, M-K1.16, частично M-K1.17 (auto-archive)
backend_tests: 1121
frontend_tests: 345
new_tests_in_mk1: 162  # 134 cumulative из STATE + 28 mentions
backend_coverage_pct: 87.3
---

# M-K1 Foundation — SUMMARY

> Knowledge Layer Foundation milestone — capability-aware multi-MCP shell,
> per-config storage layout, Object Dossier API и первая «видимая» интеграция
> через `@Документ.ОПП` mentions в чате.

## Что закрыто (14 из 17 phases)

| Phase | Subject | Артефакты | Tests |
|-------|---------|-----------|-------|
| M-K1.1 | ADR-001..005 + README | 5 ADR + навигация | — (docs) |
| M-K1.2 | Dual license + NOTICE + OPEN-VS-CLOSED.md | LICENSE / LICENSE-EPF / LICENSE-CFE / NOTICE / OPEN-VS-CLOSED.md | — |
| M-K1.3 | knowledge/ skeleton | types.py + __init__.py + README.md | 12 |
| M-K1.4 | Storage Layout per-config | storage.py + `KnowledgeStorage` | 11 |
| M-K1.5 | Configuration Fingerprint | fingerprint.py + 12-char SHA-256 slug | 16 |
| M-K1.6 | MCPConnection +6 полей (migration v11) | migrations DDL + models + routes | 9 |
| M-K1.7 | Capability Discovery Service | capability_discovery.py + ping integration | 14 |
| M-K1.8 | MCP Orchestrator unified registry | mcp_orchestrator.py + Protocol | 32 |
| M-K1.10 | Frontend useCapability hooks | useCapability/useCapabilities/useChannelMode/useUpgradeAction | 16 |
| M-K1.11 | ChannelSelector ModeBadge | ModeBadge.tsx + integration | 7 |
| M-K1.12 | Metadata Cache filler | fill_cache_entry helper + idempotent INSERT OR REPLACE | (in 1.13) |
| M-K1.13 | Object Dossier API | dossier.py + GET /knowledge/{ch}/dossier/{path} | 10 |
| M-K1.14 | UC «расскажи про объект» | mentions.py + mentions_prefetch.py + loop.py pre-step | 28 |
| M-K1.15 | Seed 3 MCP + Factory | mcp_factory.py + FactoryResult | 9 |

**Итого:** 162 новых теста в M-K1 (134 cumulative из 13 фаз + 28 mentions).

## Что отложено (3 phases) — с причинами

| Phase | Причина |
|-------|---------|
| M-K1.9 Backend MCP clients refactor (HTTP+stdio base class) | Stdio transport ещё не нужен — все 3 seed MCP (Toolkit / buddy / context) работают через HTTP. Context (bsl-context, stdio) откладывается до M-K3, тогда же и base class. Сейчас рефакторинг = преждевременная абстракция. |
| M-K1.16 E2E smoke Multi-MCP Playwright | Объективно требует live окружения: запущенный backend (port 8010), frontend (port 3010), mock MCP server (port 6010), DEFAULT_LLM_API_KEY в env, seeded metadata_cache. CI на GitHub Actions для AWD ещё не настроен (это M-K5 Distribution). Все ключевые поведения уже покрыты integration-тестами через pytest (1121) и vitest (345) — gap минимальный. Перенесено в **M-K2.smoke**, где будет вместе с indexer regression test. |
| M-K1.17 SUMMARY + handoff | ✅ Это текущий документ. |

## Метрики (cumulative)

- **Backend pytest:** 1121 passed, 0 failed (от 982 после M-K0 → +139)
- **Frontend vitest:** 345 passed (от 322 → +23: useCapability 16 + ModeBadge 7)
- **Backend coverage:** 87.3% (≥80% gate)
- **Production frontend build:** чистый, 0 errors
- **Регрессий:** 0
- **Branches merged into main (FF):**
  - feature/m-k1-foundation → main (6 commits, 4b9a08f..c646fb3)
  - feature/m-k1-orchestrator → main (2 commits, 1c786d2..f29a4b9)
  - feature/m-k1-mentions → main (2 commits, da91d6a..d271832)

## Новые модули backend

```
app/knowledge/
├── __init__.py        — public API re-export
├── README.md          — module roadmap (Q-NEW, L1-L6)
├── types.py           — ObjectPath / PlatformVersion / KnowledgeMode
├── storage.py         — KnowledgeStorage class (per-config layout)
├── fingerprint.py     — SHA-256 canonical fingerprint → 12-hex slug
├── dossier.py         — ObjectDossier dataclass + get_dossier()
└── mentions.py        — @Тип.Имя парсер + dossier→card конвертер

app/services/
└── capability_discovery.py — experimental.analyst-1c.* parser

app/orchestrator/
├── mcp_orchestrator.py     — Protocol-based namespace router
├── mcp_factory.py          — build_orchestrator() + FactoryResult
└── mentions_prefetch.py    — prefetch_mentions() обвязка

app/routes/
└── knowledge.py            — GET /knowledge/{ch}/dossier/{path}

app/types/
└── capabilities.py         — 23-capability matrix + filter helpers
```

## Новые модули frontend

```
hooks/
└── useCapability.ts        — useCapability/useCapabilities/useChannelMode/useUpgradeAction

components/shell/
└── ModeBadge.tsx           — MCP/EPF/CFE визуальная индикация

lib/
├── capabilities.ts         — TS mirror of backend capabilities
└── card-registry.ts        — 20 card types ↔ capability mapping
```

## Архитектурные решения, закреплённые в M-K1

1. **Capability Discovery via `experimental.analyst-1c.*`** в MCP initialize
   response (ADR-004). 8 namespaces. Graceful fallback к `mcp_only` +
   `CAPABILITIES_BASE` если experimental пустой.

2. **Configuration Fingerprint** (ADR-001) — SHA-256 от canonical JSON
   `{config_name, version, platform_8.X, bsp_3.X, extension_uids_sorted}`,
   truncate до 12 hex. Per-config knowledge corpus в
   `$ANALYST_HOME/knowledge/<slug>/{metadata,embeddings,graph,cache,logs}/`.

3. **DDL migrations без alembic** (ADR-005). `MIGRATIONS_VN` list + DDL
   string concatenation. Текущая версия — v11 (MCPConnection +6 полей).

4. **MCPOrchestrator namespace routing** (ADR-002): `toolkit.execute_query` →
   split on first dot → route to registered client. Protocol PEP 544 + 
   `runtime_checkable` для duck typing.

5. **Dual licensing** (ADR-003, Q6 решение): Apache 2.0 для open core,
   proprietary для EPF/CFE. Open-vs-Closed boundary документирован.

6. **23-capability matrix** (ADR-004 expanded): 8 base + 3 conditional + 
   12 CFE. `filter_capabilities_for_mode()` + `validate_capability_list()`
   forward-compat для unknown capabilities.

## Handoff в M-K2

### Что готово для M-K2 indexer

- ✅ `KnowledgeStorage` — куда писать metadata snapshots / embeddings / graph
- ✅ `fill_cache_entry()` helper — точечная запись в metadata_cache
- ✅ `ConfigurationFingerprint` — slug для shared corpus
- ✅ Capability discovery — знаем какие 23 capabilities доступны на канале
- ✅ MCPOrchestrator + factory — единая точка вызова любого MCP namespace
- ✅ Object Dossier API — frontend готов читать dossiers

### Что M-K2 нужно построить

- **L1 Metadata Indexer** — bulk filler через `mcp.get_metadata` для всех
  объектов канала (sync mode 1: первый ping, фоновая задача), запись в
  `metadata_cache` через существующий `fill_cache_entry` helper.
- **L2 Graph Layer** — Neo4j-lite (или sqlite-graph) с зависимостями:
  Документ → Регистр.Движение, Реквизит.Тип → Справочник, и т.д.
- **L3 Embedding Layer** — sqlite-vec + OpenAI text-embedding-3-small для
  semantic search по metadata + presentation strings.
- **Triple RAG** — комбинированный retrieval: keyword (FTS5) + vector
  (sqlite-vec) + structural (L2 graph traversal).
- **E2E Playwright smoke** (перенесённый M-K1.16) — full chat flow с
  mention + dossier + LLM response.

### Известные ограничения M-K1 для M-K2

- `ObjectDossier` сейчас содержит только `name`/`kind`/`presentation` —
  attributes/tabular_sections/forms всегда `[]`. Заполнятся в M-K2 indexer
  через MCP `get_metadata(detail='full')`.
- `dossier.source` сейчас только `'cache'` — `'mcp'` и `'cache_stale'`
  ветки в `get_dossier()` пока зарезервированы.
- `parse_object_mentions` не поддерживает `@Документ.ОПП.Реквизит.Номер`
  (вложенные пути) — добавится в M-K2 когда attributes будут реально
  заполнены.

## Риски, оставшиеся открытыми (из RISKS.md)

| Risk | Status в M-K1 |
|------|---------------|
| R-01 .hbk fallback strategy | Зарезервировано в M-K2.4 |
| R-02 BSL LS streaming в M-K3 | Документировано, спайк в M-K3 |
| R-04 MetaVision (Q4) | Spike в M-K4 Phase 16.0 |
| R-06 Capability drift между client/server | Mitigated: `validate_capability_list()` фильтрует unknown, frontend ignore-safe |
| R-08 SQLite migration rollback | Документировано: DDL без rollback by design (ADR-005), backup recommended pre-v12 |

## Команда / окружение

- Branch: `feature/m-k1-mentions` → merged FF в main (commit `d271832`)
- Pre-conditions для M-K2: `pip install` + node 22 + pnpm 11 (без новых deps)
- Recommended next session: M-K2.1 indexer skeleton + DDL v12 (если потребуется)

## Подпись

```
M-K1 Foundation: complete (14/17 atomic phases done).
Тесты: backend 1121, frontend 345 — все зелёные, 0 регрессий.
Готов handoff в M-K2 (Knowledge Foundation + Triple RAG, 4-5 weeks).
```
