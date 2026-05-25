# M6 Integrated Plan — Knowledge Layer ✕ Multi-MCP + EPF/CFE

**Создан:** 2026-05-25
**Источники интеграции:**
1. **Knowledge Layer план** (M-K0..M-K6) в `.planning/knowledge-layer-2026-05-24/`
2. **M6 handoff** от другой сессии — `C:/CLOUDE_PR/M6-Handoff-2026-05-25.zip` (12 файлов)

**Status:** проект интеграции; требует ответов пользователя на 4 open questions
(см. `INTEGRATION-DECISIONS.md`) перед началом фаз M-K1+.

---

## Ключевой инсайт

Два плана **смотрят на проект под разными углами и не конфликтуют**, а
дополняют друг друга:

| Аспект | Knowledge Layer (моё) | M6 Handoff |
|---|---|---|
| **Главный вопрос** | «Что Аналитик умеет **понять** про базу клиента?» | «Как Аналитик **интегрируется** с 1С технически?» |
| **Фокус** | Intelligence — L0 Lexical → L6 Predictive | Infrastructure — Multi-MCP + EPF/CFE delivery + RAG sources |
| **Метафора** | «Мозг» — даёт reasoning, объяснения, граф знаний | «Нервная система» — даёт каналы для получения данных |
| **Конечный продукт** | Diagnose engine, dossier, что-если, NL2SQL | 5 MCP параллельно, EPF/CFE installer, capability discovery |

**Решение:** **слить** в единый roadmap, где **M6 фазы доставляют инфраструктуру**,
а **M-K фазы используют её для построения intelligence**.

---

## Архитектурное наложение (Capability matrix vs Levels of Understanding)

```
M6 Capabilities (23 шт) ──────┐
                              │
                              ▼
              ┌───────────────────────────────┐
              │  Knowledge Layer (L0-L6)      │
              │  ──────────────────────────   │
              │  L1 Structural ── mcp.get_metadata
              │                    cfe.hot_reload_metadata
              │  L2 Relational ── mcp.find_references
              │                    service.metavision (граф)
              │  L3 Semantic ──── service.rag_search (тройной RAG)
              │  L4 Behavioral ── cfe.activity_stream
              │                    cfe.posting_trace
              │  L5 Normative ─── buddy.search_its (RAG ИТС)
              │                    service.bsl_ls (антипаттерны live)
              │  L6 Predictive ── + git history + reference configs
              └───────────────────────────────┘
                              │
                              ▼
                    Use Cases UC-1..UC-25
                    (diagnose, dossier, lineage, what-if)
```

**Каждый L-уровень требует соответствующих capabilities** для активации.

---

## Объединённый Roadmap

### M-K0 Stabilization — **АКТИВЕН СЕЙЧАС, 32% done**

Закрытие 28 critical+high findings из общего аудита. **НЕ МЕНЯЕТСЯ** —
это pre-requisite ко всему остальному.

- Wave 0 Security: ✅ DONE (7 commits, SEC-1..7, SEC-12)
- Wave 1 Backend Quality: pending (BE-1..6)
- Wave 2-6: pending

Срок: до **20.06.2026**.

### M-K1 / M6 Phase 12 = MERGED → «M-K1 Foundation + Multi-MCP»

**Цель:** Архитектурные решения + capability discovery + первое подключение
нескольких MCP параллельно + первый killer UX «расскажи про объект».

**Содержание (объединённое):**

Из Knowledge Layer M-K1:
- ADR-001 Vector DB (sqlite-vec → LanceDB)
- ADR-002 Graph DB (SQLite + recursive CTE)
- ADR-003 Embeddings runtime (FastEmbed ONNX)
- OPEN-VS-CLOSED.md
- `backend/app/knowledge/` skeleton
- StorageManager per-config layout
- Configuration Fingerprint
- Metadata Cache filler
- Object Dossier API
- UC «расскажи про объект»

**Из M6 Phase 12 (новое):**
- **ADR-004 Capability Discovery Protocol** через `experimental.analyst-1c.features`
  в MCP `initialize`
- Backend модель `MCPConnection` расширена 5 полями: `mode`, `configuration`,
  `platform_version`, `extension_version`, `capabilities`
- Alembic миграция (поверх существующей schema v10)
- Capability discovery service (parse_capabilities + legacy mode detection)
- MCP Orchestrator с unified tool registry (префиксы `toolkit.*`, `buddy.*`,
  `context.*`, `metr.*`, `edt.*`)
- HTTP + stdio MCP clients (refactor existing)
- Frontend `useCapability` + `useEnabledModules` hooks
- `SourceSelector` (рефакторинг `ChannelSelector`) с группировкой
  Базы 1С / Знания / Инструменты
- Seed 5 default подключений: Транзит MCP Toolkit / 1c-buddy / mcp-bsl-context /
  METR / EDT-MCP

**Срок:** 2-3 недели (vs 1-2 в исходном M-K1) — handoff добавил инфраструктуру
для multi-MCP.

**Дата завершения:** до **20.07.2026** (vs 05.07 в исходном).

### M-K2 / M6 Phase 14 = MERGED → «Knowledge Foundation + Triple RAG»

**Цель:** Полный indexing pipeline + три параллельных RAG источника
(v8std + БСП + .hbk).

**Содержание объединённое:**

Из M-K2:
- First-Touch Indexer Pipeline (X-1)
- Incremental Update (mtime + event log) (X-2)
- MCP Result Cache (X-4)
- Vector store (sqlite-vec) (L3-1)
- Embedding pipeline (BGE-M3) (L3-2)
- Configuration Type Detection (L1-5)
- Indexing Progress UI (UX-6)
- Privacy badge (OPS-1)

**Из M6 Phase 14 (новое):**
- **v8std RAG** — 317 ИТС-стандартов из `tools/v8std/content/*.md` (sfaqer)
- **БСП API RAG** — парсер `tools/ssl_3_1/`, `tools/ssl_3_2/` для ~3000 БСП методов
- **.hbk Platform RAG** — парсер `1ceBsl.hbk` (под риском Q4 = MetaVision-подобный)
- **Тройной merge с приоритетами** — top-K (3 per source) → inject в system prompt
- **CodeCard citations** — ссылки на ИТС §NNN / БСП.МодульX:строкаN

**Срок:** 4-5 недель (vs 3-4 в исходном M-K2). **Дата:** до **20.08.2026**.

### M-K3 / M6 Phase 13a + 13b + 15 + 17 = MERGED → «Relational + Behavioral + Delivery»

**Цель:** L2 + L4 use cases + EPF/CFE delivery + BSL LS live diagnostics.
**MVP «Объяснитель»** (killer USP).

**Содержание объединённое:**

Из M-K3:
- Knowledge Graph SQLite + CTE (L2-1)
- BSL Parser TreeSitter (L2-2)
- Call Graph + Data Flow Lineage (L2-3, L2-4)
- Diagnose Engine (L4-1)
- UC-1 RLS-tracer
- UC-2 Empty-report tracer
- UC-3 Цепочка проведения
- UC-4 Impact analysis
- UC-15 Query optimizer
- Semantic Code Search (L3-3)
- Antipattern Detector (L5-3)
- GraphCard + DiagnoseCard (UX-1, UX-2)

**Из M6 Phase 13a + 13b (новое):**
- **EPF Lite (АналитикLite.epf)** — внешняя обработка `~3 MB`
  - Содержит: MCP Toolkit (наш) + tools_ui_1c (опц.) + Connector
  - Mode = "epf", 8 capabilities
  - Quick start без правки конфигурации
- **CFE Full (АналитикПлюс.cfe)** — расширение конфигурации `~8 MB`
  - HTTP-сервис постоянный (не требует открытой формы)
  - Подписки на события + регламентные задания
  - HMAC SSO от 1С-пользователя
  - Mode = "cfe", 23 capabilities
- **Migration EPF↔CFE** — без потери истории сессий
- **PowerShell installer** для CFE
- **Onboarding step 1.5** — выбор EPF/CFE

**Из M6 Phase 15 (новое):**
- **BSL LS subprocess + WebSocket для live diagnostics**
- **SHA256 кэш** диагностик — повторные вызовы ≤ 100ms
- **BSLDiagnostics card** (новый тип) — inline warnings в code

**Из M6 Phase 17 (новое):**
- **8 типов cards** (вместо 6): Code/Table/Object/Log/Metric/References/
  BSLDiagnostics/StandardsCitation/MetaVisionGraph/ActivityEvent/PostingTrace
- **Feature gates per capability** — UpgradeCTA для disabled фич

**Срок:** 6-8 недель (vs 4-6 в исходном M-K3). Дата: до **15.10.2026**.

**M-K3.0 Preparatory** — ARCH-1 decompose loop.py остаётся (5 дней до start).

### M-K4 / M6 Phase 16 + 17b = MERGED → «Visual Architecture + Activity Stream»

**Цель:** Граф вызовов функций (MetaVision) + Activity Stream + Posting Trace
(CFE-only фичи) + Compliance dashboard + Hybrid retrieval.

**Содержание объединённое:**

Из M-K4:
- L4-4 Deadlock-tracer
- L4-6 Hypothesis-Driven Reasoning Framework
- L5-4 UC «Compliance check»
- L5-5 UC «Refactor God-модуля»
- L3-5 Sessions encoder (vector поиск по истории)
- L3-6 UC «Explain функцию построчно»
- X-5 Hybrid Retrieval (BM25 + Vector + Reranker)
- UX-7 Citation Layer
- OPS-2 Telemetry / Indexing Quality Metrics
- OPS-5 Knowledge Layer как MCP Server

**Из M6 Phase 16 (новое):**
- **MetaVision CLI fork** — `tools/MetaVision/` + headless mode
  (1 неделя Java; fallback на GUI integration через subprocess если не получится)
- **MetaVisionGraph card** — D3.js force-directed визуализация (или sigma.js
  для 5000+ узлов)
- **AntipatternHighlight** на графе

**Из M6 Phase 17b (новое — CFE-only):**
- **Activity Stream** — realtime поток событий 1С (ПриЗаписи, ПриУдалении, ...)
  через подписки CFE
- **Posting Trace card** — детальная трассировка ОбработкаПроведения "до/после"
- **Method Overrides** для трассировки типовых

**Срок:** 4-6 недель. Дата: до **30.11.2026**.

Готовность к **INFOSTART A&PM EVENT октябрь 2026** — успеваем по KL-плану.

### M-K5 / M6 Phase 18 = MERGED → «Predictive + Distribution v2.0»

**Цель:** L6 predictive use cases (temporal, vs типовой) + 8.5-Ready
Assessment как **standalone revenue trigger** + Electron installer v2.0.0
с EPF/CFE distribution.

**Содержание:**

Из M-K5:
- L6-1 UC «Temporal Diff» (что менялось — git history)
- L6-2 UC «Сравни с типовой УТ 11.5»
- L6-3 Reference Configurations Library
- **L6-4 UC «8.5-Ready Assessment»** — standalone paid сервис
- **PG-4 8.5-Ready** landing + payment + automated PDF report
- UX-3 ComparisonCard, UX-4 TimelineCard, UX-5 ProcessCard
- L2-7 UC «UI-trace кнопки до регистра»
- OPS-3 Export/Import bundle (.klzip)

**Из M6 Phase 18 (новое):**
- **Electron installer v2.0.0** (~250 MB)
- **EPF installer:** `АналитикLite.epf` (~3 MB)
- **CFE installer:** `АналитикПлюс.cfe` (~8 MB) + `Install-АналитикПлюс.ps1`
- **Auto-update** через electron-updater + EV/OV cert
- **Bundled JRE 17** для BSL LS / MetaVision
- **README-V2 + 4 INSTALL- docs** для пользователя

**Срок:** 5-7 недель. Дата: до **15.01.2027**.

### M-K6 (Predictive++) — без изменений

NL2SQL, Cross-config benchmark, Auto code review, Enterprise pricing.

Срок: до **31.03.2027**.

---

## Сводный календарь (объединённый)

```
2026-05-25  ─ план готов, M-K0 в работе
2026-06-20  ─ M-K0 done (Stabilization) ← обязательное условие
2026-07-20  ─ M-K1 done (Foundation + Multi-MCP) — сдвиг +2 нед от исходного
2026-08-20  ─ M-K2 done (Knowledge Foundation + Triple RAG) — сдвиг +2 нед
2026-10-15  ─ M-K3 done (Relational + Behavioral + EPF/CFE + BSL LS) → MVP «Объяснитель»
2026-11-30  ─ M-K4 done (MetaVision + Activity Stream + Compliance) → INFOSTART A&PM EVENT
2027-01-15  ─ M-K5 done (Predictive + 8.5-Ready + Installer v2.0.0) → revenue trigger
2027-03-31  ─ M-K6 done (Predictive++ + Enterprise) → Q1 2027 закрытие
```

**Расширение vs исходный KL plan: +1.5 месяца суммарно.** Это разумная цена
за **EPF/CFE delivery + Multi-MCP infrastructure + Triple RAG + Visual graph**.

---

## Готовые tools локально (которыми воспользуемся)

Из `09-CURRENT-STATE.md` handoff'а:

✅ **Уже установлено в `C:/CLOUDE_PR/tools/`:**
- `1c-buddy` запущен на :6002 (8 MCP tools, токен в env)
- `v8std/content/` — 317 ИТС-стандартов markdown (для L5-1 RAG)
- `ssl_3_1/`, `ssl_3_2/` — БСП исходники (для L5-2 RAG)
- `MetaVision/` собран — `MetaVisionFor1C-1.0.jar` 28.6 MB
- `bsl-language-server-0.30.0-rc.2-exec.jar` (для L5-3 + Phase 15)
- `tools_ui_1c/` (GPL-3.0, опционально в EPF)
- `Connector v2.6.1/` (MIT, для EPF/CFE)
- `MCP Toolkit v1.7.0` EPF
- `YAxUnit 25.12` + `Vanessa Automation 1.2.043`
- JDK 17 + JDK 21 локально

**Это значит** — Phase 12, 14, 15, 16 могут стартовать сразу после M-K0 + Q&A.

---

## Что НЕ интегрируем (отвергнуто с обоснованием)

См. полный список в `INTEGRATION-DECISIONS.md`. Кратко:

- ❌ **«Тройной RAG» сразу 3 источника** — если .hbk парсер сложен (R2 в risks),
  отдадим Phase 14.4 в backlog (v8std + БСП достаточно для MVP)
- ❌ **MetaVision GUI wrapper** — если CLI fork не получится за 1 нед,
  fallback на «открыть в MetaVision desktop» (кнопка вместо inline)
- ❌ **Подсистема `АналитикПлюс` без префиксов** — рекомендую B+namespace
  (подсистема + префикс `АП_` для общих модулей), требует решения пользователя

---

## Open Questions — ждут решения пользователя

См. `INTEGRATION-DECISIONS.md` секция «Q&A» — 4 критичных вопроса
(Q3 EPF/CFE first, Q6 лицензия, Q1 CFE именование, Q2 типовые) + 3 дополнительных.

**Минимум для start M-K1**: ответы на Q3 + Q6.

---

## Definition of Done объединённого M6/M-K плана

После M-K5 (январь 2027):
- ✅ 5 MCP параллельно (Multi-MCP Orchestration)
- ✅ EPF + CFE installers работают (доставка в 1С)
- ✅ 23 capabilities активны в CFE / 8 в EPF
- ✅ Тройной RAG (v8std + БСП + .hbk при возможности)
- ✅ BSL LS live diagnostics
- ✅ MetaVision граф вызовов (или fallback)
- ✅ Activity Stream + Posting Trace (CFE-only)
- ✅ 7 уровней понимания L0-L6 покрыты use cases
- ✅ 25+ killer UC доступны пользователю
- ✅ 8.5-Ready Assessment standalone paid сервис (revenue trigger)
- ✅ Electron installer v2.0.0 на Win10/11
- ✅ Migration EPF↔CFE без потери истории
- ✅ Backend tests coverage ≥ 80% на новом коде
- ✅ Frontend vitest coverage ≥ 80%
- ✅ Playwright E2E зелёные
- ✅ Документация пользователя написана

---

## Связанные документы

- `INTEGRATION-DECISIONS.md` — принятые/отклонённые решения + open questions
- `../knowledge-layer-2026-05-24/PLAN.md` — оригинальный Knowledge Layer план
  (обновляется reference на этот документ)
- `../knowledge-layer-2026-05-24/STATE.md` — текущий snapshot (active = M-K0)
- `C:/CLOUDE_PR/M6-Handoff-2026-05-25.zip` — исходный handoff (read-only,
  не модифицируется)
- `../knowledge-layer-2026-05-24/Knowledge_Layer_*.xlsx` — 63 findings
- `../development-plan-2026-05-24/План_развития_*.xlsx` — 99 общих findings

---

## История изменений

- **2026-05-25 v1.0**: Создан после интеграции M6 handoff в Knowledge Layer plan.
  9 фаз M6 (12-18) мапятся на 5 M-K милстоунов с сдвигом дат +1.5 месяца.
