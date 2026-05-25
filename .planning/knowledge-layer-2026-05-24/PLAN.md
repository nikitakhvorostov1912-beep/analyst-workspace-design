# PLAN — Knowledge Layer для 1С Аналитик

**Версия:** 1.2  
**Создан:** 2026-05-24, обновлён 2026-05-25 (M6 handoff integration)  
**Owner:** Никита Хворостов  
**Status:** Approved, ready to execute (M-K0 in progress, Wave 0 ✅)  
**Linked Excel:** `Knowledge_Layer_1С_Аналитик_2026-05-24.xlsx`

> Этот документ — стратегический и операционный план развития Knowledge Layer  
> поверх существующего приложения **1С Аналитик** (`analyst-workspace-design/`).  
> Он живёт вместе с уже работающим продуктом v1.4.5 и НЕ заменяет основной  
> roadmap (`ROADMAP.md` в корне проекта).

## 🔗 Связь с M6 Handoff (2026-05-25)

2026-05-25 получен handoff от другой сессии — **M6 Quality Expansion**
(`C:/CLOUDE_PR/M6-Handoff-2026-05-25.zip`). Это **ортогональный план**:
- **Этот PLAN** = «что Аналитик умеет **понять** про базу» (L0-L6 intelligence)
- **M6 Handoff** = «как Аналитик **интегрируется** с 1С технически»
  (Multi-MCP + EPF/CFE + тройной RAG + BSL LS live)

**Интегрированный roadmap:** `../milestones/M6-INTEGRATED-PLAN.md` (единый view)
**Решения по интеграции:** `../milestones/INTEGRATION-DECISIONS.md`
(9 принято / 6 слито / 4 ждут пользователя / 3 отклонено).

**Ключевое:** M6 фазы 12-18 **мапятся** на M-K1..M-K5 (нумерация моя сохраняется):
- M6 Phase 12 (Multi-MCP + Capabilities) → влит в **M-K1**
- M6 Phase 14 (Triple RAG) → влит в **M-K2**
- M6 Phase 13a/13b/15/17 (EPF/CFE + BSL LS + UX) → влит в **M-K3**
- M6 Phase 16 + 17b (MetaVision + Activity Stream) → влит в **M-K4**
- M6 Phase 18 (Distribution v2.0) → влит в **M-K5**

**Расширение сроков:** +1.5 месяца суммарно (M-K5 финиш 15.01.2027 vs 20.12.2026).
Оправдано scope: добавлены EPF/CFE delivery + Multi-MCP + Triple RAG + visual graph.

---

## 1. North Star (одна страница)

### Что строим

**Knowledge Layer** — слой глубокого понимания 1С-конфигурации, встроенный в  
1С Аналитик. Аналитик задаёт вопросы естественным языком про **свою** базу  
1С, а получает ответы, грountованные в конкретных файлах кода, метаданных,  
стандартах ИТС и БСП.

Ключевая отличительная способность — **«объяснять почему»**:

- «Почему Иванов не видит этот документ?» → trace по RLS до конкретного условия
- «Почему отчёт пустой?» → анализ СКД + параметров + лишних фильтров
- «Что сломается если переименовать реквизит X?» → impact analysis по графу
- «Покажи цепочку проведения этого документа» → визуальный граф движений
- «Почему запрос медленный?» → анализ антипаттернов + готовая исправленная версия

### Для кого

- **P1** — опытный 1С-аналитик с 4-6 проектами параллельно, который читает  
  BSL, но не пишет руками, и тратит часы на discovery незнакомых баз
- **P2** — внедренец-франчайзи (2-3 года опыта), работающий с типовыми  
  УТ/КА/ERP/УСО, нуждается в low-friction onboarding в чужой конфигурации

### Почему сейчас

Конкурентное окно:

- **1С:Напарник** — бесплатен до 01.10.2026, после — неизвестная цена. Работает  
  только в EDT и только для **разработчиков**. Не объясняет «почему».
- **MetaVision** — статический анализатор, видит граф, но не reasonsит  
  и не интегрирован с LLM. Уровень L1-L2 (см. модель уровней).
- **Aether Lab** — только запросы. Не покрывает discovery базы.
- **Уровни L4-L6** (Behavioral / Normative / Predictive) — **пусты** на рынке.  
  Это наша ниша.

---

## 2. Модель уровней понимания (L0-L6)

| L | Уровень | Что значит | Где сейчас рынок | Где мы целимся |
|---|---------|-----------|------------------|----------------|
| L0 | Lexical | Знает имена, поиск по строке | feenlace/mcp-1c | Уже есть (MCP) |
| L1 | Structural | Знает структуру (метаданные) | Code Index, EDT | M-K1 (фундамент) |
| L2 | Relational | Знает связи (графы вызовов) | bsl-graph (alpha), MetaVision | **M-K3** |
| L3 | Semantic | Понимает смысл (embeddings) | bsl-atlas, Напарник (writing) | **M-K2-K3** |
| L4 | Behavioral | Понимает «почему» (diagnose) | **ПУСТО — наша ниша** | **M-K3-K4** |
| L5 | Normative | Знает ИТС-стандарты | **ПУСТО** | **M-K2-K4** |
| L6 | Predictive | Предсказывает последствия | **ПУСТО — moat** | M-K5-K6 |

Принцип: **каждый следующий уровень требует предыдущих**. L4 без L1+L2  
невозможен. L6 без всех остальных — фантазия.

---

## 3. Базовые принципы (не нарушать)

Эти принципы должны проверяться при любой задаче. Если задача нарушает  
принцип — задача неправильно сформулирована, не код.

### 3.1. Local-first

- Индексация — **локально на машине аналитика**
- Embeddings — **local ONNX** (через FastEmbed, не Ollama/Docker)
- Vector store — **embedded** (sqlite-vec → LanceDB при scale)
- LLM — на выбор пользователя (Cloud.ru для 152-ФЗ / NVIDIA NIM / DeepSeek)

**Следствие:** Knowledge Layer не отправляет код пользователя в облако без  
явного opt-in. Это базовое compliance-обещание.

### 3.2. Grounded (всё с file:line + ссылкой)

Любой ответ Knowledge Layer должен ссылаться на:

- файл и строку кода (`MyModule.bsl:42`)
- объект метаданных (`Документ.ОПП.Реквизит.Контрагент`)
- стандарт ИТС или БСП (`ИТС §3.1.4`, `БСП.ДлительныеОперации:ВыполнитьФункцию`)

Любой ответ без grounding = баг.

### 3.3. Incremental (не пере-индексировать всё каждый раз)

- Mtime watcher для файлов
- Event log subscription для метаданных в БД (когда возможно)
- Diff-based update: парсятся только изменённые subtree (TreeSitter)
- Полная переиндексация — только по запросу или при `fingerprint mismatch`

### 3.4. Per-configuration isolation

Каждая база 1С — отдельный Knowledge Layer:

```
~/.analyst-1c/knowledge/<config-fingerprint>/
├── metadata.sqlite
├── graph.sqlite
├── vectors.sqlite-vec / vectors.lance/
├── ast/
└── snapshots/
```

Один проект клиента ≠ другой. Никаких глобальных индексов между конфигурациями  
(кроме reference configurations типовых, см. L6).

### 3.5. Open-core boundary (Pricing/GTM)

- **Open**: indexing pipeline, AST parser, graph schema, MCP server skeleton
- **Closed**: reference configurations library, business semantics rulebook,  
  pre-built knowledge bundles для типовых

Это создаёт moat без блокировки community contributions.

### 3.6. Test-first для каждого Use Case

UC = пользовательский запрос + ожидаемый ответ. Реализация любого UC должна  
начинаться с **тестового кейса** (golden dataset entry), не с кода.

```python
# tests/uc/test_uc_01_rls_tracer.py
def test_uc01_rls_blocked_by_owner_field():
    # arrange: fixture с 1С базой где у пользователя нет права на документ
    # act: knowledge_diagnose("почему пользователь Иванов не видит ОПП-00001")
    # assert: ответ содержит "условие <ВладелецДокумента <> &ТекущийПользователь>"
    # assert: ответ содержит file:line на RLS-шаблон
```

### 3.7. Прозрачность процесса (trace везде)

Каждый ответ Knowledge Layer = развёрнутый ToolTrace:
- какой workflow выбран (diagnose / search / explain)
- какие источники задействованы (graph / vector / MCP / RAG ИТС)
- какие промежуточные результаты получены
- финальный ответ

Это уже архитектурный паттерн AWD — продолжаем.

---

## 4. Архитектура (high-level)

```
┌──────────────────────────────────────────────────────────────────┐
│ Frontend (Next.js 15 — существующий)                              │
│   + новые карточки: GraphCard, DiagnoseCard, ComparisonCard,      │
│     TimelineCard, ProcessCard                                     │
└─────────────────────────┬────────────────────────────────────────┘
                          │ SSE
┌─────────────────────────▼────────────────────────────────────────┐
│ Backend Orchestrator (FastAPI — существующий)                     │
│   loop.py остаётся.                                                │
│   Новые internal tools:                                            │
│     knowledge_dossier, knowledge_diagnose, knowledge_impact,       │
│     knowledge_explain, knowledge_compare, knowledge_lineage,       │
│     knowledge_search_semantic                                      │
└─────────────────────────┬────────────────────────────────────────┘
                          │ in-process calls
┌─────────────────────────▼────────────────────────────────────────┐
│ Knowledge Layer (NEW — backend/app/knowledge/)                    │
│                                                                    │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐       │
│   │ Indexer     │  │ Retrieval    │  │ Reasoning        │       │
│   │ Pipeline    │  │ Engine       │  │ Engine           │       │
│   │             │  │              │  │                  │       │
│   │ - MCP fetch │  │ - SQL/CTE    │  │ - Diagnose rules │       │
│   │ - TS parser │  │ - Vector     │  │ - LLM CoT        │       │
│   │ - mdclasses │  │ - Hybrid     │  │ - Hypothesis     │       │
│   │ - Embed     │  │ - Reranker   │  │                  │       │
│   └──────┬──────┘  └──────┬───────┘  └────────┬─────────┘       │
│          │                │                    │                  │
│          └────────────────┴────────────────────┘                  │
│                           │                                       │
│   ┌───────────────────────▼───────────────────────────────────┐  │
│   │ Storage Layer (per-config: ~/.analyst-1c/knowledge/<hash>) │  │
│   │   metadata.sqlite | graph.sqlite | vectors.sqlite-vec      │  │
│   │   ast/ snapshots/                                          │  │
│   └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   ┌─────────┐      ┌──────────┐      ┌──────────┐
   │ MCP 1С  │      │ ИТС RAG  │      │ БСП RAG  │
   │ (live)  │      │ (static) │      │ (static) │
   └─────────┘      └──────────┘      └──────────┘
```

**Граница**: Knowledge Layer экспонируется как **новый внутренний MCP-сервер**  
(порт 7070) — orchestrator вызывает его как обычный MCP-tool. Это:
- Чистая граница: можно тестировать изолированно
- Marketable: «MCP-first product»
- Гибкость: сторонние ИИ (Claude Desktop, Cursor) могут подключаться к нашему  
  Knowledge Layer

---

## 5. Roadmap по милстоунам

### Общий принцип

Один милстоун = 2-6 недель. Каждый — атомарно полезный (не «полу-готов»).  
Каждый имеет:
- **Цель** (одна фраза)
- **Содержание** (список Findings из Excel)
- **Definition of Done** (acceptance criteria)
- **Метрики успеха** (что измеряем)
- **Зависимости** (что должно быть готово до старта)
- **Риски** (что может пойти не так)

### Общая последовательность

```
M-K0 Stabilization (закрытие дыр)   → ~3-4 недели  ← ПЕРВЫМ
   ↓
M-K1 Foundation (decisions + QW)    → 1-2 недели
   ↓
M-K2 Knowledge Foundation           → 3-4 недели
   ↓
M-K3 Relational + Behavioral        → 4-6 недель
   ↓
M-K4 Normative + Hybrid             → 4-5 недель
   ↓
M-K5 Predictive + 8.5-Ready         → 5-7 недель
   ↓
M-K6 Predictive++ Enterprise        → 6-10 недель
```

### M-K0: Stabilization — закрытие технического долга

**Срок:** 3-4 недели, до **20.06.2026**

**Цель:** Закрыть 9 CRITICAL + 14 критичных HIGH из общего аудита проекта  
(99 findings) ПЕРЕД стартом Knowledge Layer. Фундамент должен быть стабильным,  
безопасным, коммерчески пригодным.

**Содержание (Findings из общего аудита `План_развития_1С_Аналитик_2026-05-24.xlsx`):**

Wave 0 Security (8): SEC-1 SSRF, SEC-2..7 Electron+CORS+admin+injection,  
SEC-12 deprecation deadline

Wave 1 Backend (6): BE-1 _pending race, BE-2 task leak, BE-3 silent failures,  
BE-4 CLARIFY leak, BE-5 card_id matching, BE-6 SQLite batch commit

Wave 2 Performance (3): PERF-1 SQLite connection, PERF-2 LLMClient reuse,  
PERF-3 fetch elimination

Wave 3 Prompts (3): PROMPT-1 few-shot, PROMPT-2 indirect injection,  
PROMPT-3 memory recall

Wave 4 Frontend (3): FE-1 prefers-reduced-motion, FE-3 контраст,  
FE-4 attachment keys

Wave 5 Architecture (1): ARCH-2 globals → contextvars  
(ARCH-1 decompose loop.py перенесён в M-K3.0 preparatory)

Wave 6 Docs+DevOps (4): DOC-1 ARCHITECTURE ревизия, DOC-2 STATE fix,  
DEVOPS-1 EV cert process init, DEVOPS-5 semver.gt downgrade check

**Итого:** 28 findings × ~5 рабочих дней + 5.5 буфер = ~31 день = ~3-4 нед

**Definition of Done:**
- [ ] Все 9 CRITICAL закрыты + 19 HIGH/MEDIUM из списка
- [ ] `pytest` + `vitest` зелёные (847+ / 323+ → не меньше)
- [ ] **Real coverage** ≥ 60% (от текущего 26.58%)
- [ ] Security re-audit: 0 CRITICAL, ≤ 2 HIGH
- [ ] Smoke на чистой Windows-VM проходит
- [ ] ARCHITECTURE.md актуален (schema v10, новые модули)

**Метрики успеха:**
- E2E latency 10-tool chain: 25-30 → ≤ 15 сек
- pytest -n 4 parallel: green без flake
- WCAG 2.3.1 A: pass через axe-core
- Tool selection accuracy (golden dataset): ≥ 80%

**Зависимости:** Никаких. M-K0 — pre-requisite ко всему.

**Риски:**
- ARCH-2 contextvars rewrite может сломать flow — feature-flag rollout
- EV cert процесс 1-3 недели — параллелим в M-K0.7
- Coverage push выявит новый долг — допускаем, отгружаем в backlog

**Детальный план:** `phases/M-K0-stabilization/M-K0-PLAN.md`

---

### M-K1: Foundation — Decisions + Quick Wins

**Срок:** 1-2 недели, до **05.07.2026** (после M-K0)

**Цель:** Зафиксировать 3 архитектурных решения (vector / graph / embeddings  
runtime), создать первичную инфраструктуру хранения, выдать первые quick wins  
без перепиливания кода.

**Содержание (Findings из Excel):**
- X-3 Knowledge Store Layout
- X-6 Vector DB — sqlite-vec выбран
- X-7 Graph DB — SQLite + CTE выбран
- X-8 Embedding Runtime — FastEmbed (ONNX) выбран
- OPS-4 Open vs Closed boundary документирован
- L1-1 Metadata Cache filler
- L1-2 Object Dossier (минимальный)
- L1-3 UC «Расскажи про объект»
- L1-4 Configuration Fingerprint

**Definition of Done:**
- [ ] Существует `backend/app/knowledge/` модуль с README.md
- [ ] При первом подключении канала — `metadata_cache` заполняется (видно в SQLite)
- [ ] `GET /knowledge/{channel}/dossier/{object_path}` возвращает паспорт объекта
- [ ] В чате UC: «расскажи про @Документ.ОПП» — работает за <5 сек
- [ ] `ADR-001-vector-db.md`, `ADR-002-graph-db.md`, `ADR-003-embeddings.md`  
  написаны и зафиксированы (Architecture Decision Records)
- [ ] `OPEN-VS-CLOSED.md` определяет boundary
- [ ] Configuration Fingerprint считается и пишется в SQLite

**Метрики успеха:**
- Время «спросил про объект → получил паспорт»: ≤ 5 сек (сейчас 10-15 сек  
  через MCP cold)
- 0 повторных вызовов `get_metadata` на одинаковый объект за сессию
- Onboarding нового разработчика по ADR: ≤ 30 минут понимания

**Зависимости:** Никаких (всё на существующей инфраструктуре)

**Риски:**
- FastEmbed на Electron PyInstaller — нужно убедиться что bundle работает  
  на чистой Windows-VM (≤ 200MB после bundling)

**Детальный план:** `phases/M-K1/M-K1-PLAN.md`

---

### M-K2: Knowledge Foundation — Indexer + L5 базы

**Срок:** 3-4 недели, до **05.08.2026**

**Цель:** Запустить полноценный indexing pipeline + загрузить статические RAG  
базы (ИТС + БСП). После M-K2 у Knowledge Layer есть «мозг» — он знает  
структуру конфигурации и стандарты, но ещё не понимает связи.

**Содержание:**
- X-1 First-Touch Indexer Pipeline
- X-2 Incremental Update (mtime + event log)
- X-4 MCP Result Cache
- L3-1 Vector Store (sqlite-vec)
- L3-2 Embedding Pipeline (BGE-M3 через FastEmbed)
- L5-1 ИТС RAG (v8327doc + v8std через v8std-for-humans)
- L5-2 БСП Pattern Index (ssl_3_1 + ssl_3_2)
- L1-5 Configuration Type Detection (УТ/ERP/БП/УСО/...)
- UX-6 Indexing Progress UI
- OPS-1 Privacy badge «Local Knowledge»

**Definition of Done:**
- [ ] При подключении нового канала пользователь видит модальное «Изучаю вашу  
  базу. Прогресс: ...» — индексация работает в background, видны SSE-события
- [ ] Полная индексация средней УТ 11.5 (~15k BSL): ≤ 10 минут
- [ ] Инкрементальное обновление одного файла: ≤ 2 сек
- [ ] При вопросе «что такое БСП.ДлительныеОперации?» — точный ответ с  
  цитатой из ssl_3_2/src/
- [ ] При вопросе «как избежать запроса в цикле?» — цитата ИТС-стандарта  
  с ссылкой на источник
- [ ] Vector store работает: `semantic_search("выгрузка в эксель") → top-10`
- [ ] Configuration type определяется автоматически (УТ / ERP / БП / УСО /  
  кастом) с confidence score

**Метрики успеха:**
- Полная индексация: ≤ 10 минут для УТ 11.5, ≤ 20 минут для ERP 2.5
- Semantic search precision@10: ≥ 70% на golden dataset из 30 запросов
- ИТС RAG precision@5: ≥ 80% на 20 типовых вопросах
- 0 повторных embedding вычислений для неизменённых файлов

**Зависимости:** M-K1 (decisions, storage layout)

**Риски:**
- BGE-M3 размер модели — 570 MB. Bundling в Electron installer увеличит размер  
  с 183 MB до ~750 MB. Альтернатива: download-on-first-run.
- ИТС crawler может упереться в rate-limit. Готовый v8std-for-humans (sfaqer) —  
  снижает риск (готовый markdown).

---

### M-K3: Relational + Behavioral — L2 + L4 + Killer UCs

**Срок:** 4-6 недель, до **20.09.2026**

**⚠ M-K3.0 Preparatory:** перед основной работой — ARCH-1 decompose loop.py  
(688→≤400 строк, ~5 дней). Был отложен из M-K0, но Knowledge Layer integration  
в loop.py требует чистоты.

**Цель:** Запустить graph (callgraph + data lineage) + diagnose engine + первые  
5 killer use cases. После M-K3 у Knowledge Layer есть **главное USP**:  
объясняет «почему».

**Содержание:**
- L2-1 Knowledge Graph (SQLite + CTE)
- L2-2 BSL Parser (TreeSitter)
- L2-3 Call Graph Builder
- L2-4 Data Flow Lineage
- L2-5 UC «Цепочка проведения»
- L2-6 UC «Impact analysis»
- L4-1 Diagnose Engine
- L4-2 UC «Почему Иванов не видит?» (RLS-tracer)
- L4-3 UC «Почему отчёт пустой?»
- L4-5 UC «Почему запрос медленный?»
- L3-3 Semantic Code Search
- L5-3 Antipattern Detector (A1-A11 + BSL LS)
- UX-1 GraphCard (React Flow)
- UX-2 DiagnoseCard
- PG-2 «Объяснитель» как marketing positioning
- PG-3 «Напарник пишет, MetaVision видит, мы — объясняем»

**Definition of Done:**
- [ ] UC «покажи цепочку проведения @Документ.ОПП-00001» → GraphCard  
  с движениями в регистры
- [ ] UC «что сломается если переименую Контрагент в Партнер у Документа.ОПП»  
  → список из ≥ 5 мест с file:line
- [ ] UC «почему пользователь Иванов не видит ОПП-00001» → diagnose с  
  конкретным RLS-условием
- [ ] UC «почему отчёт ОборотПоТоварам пустой» → diagnose с pinpoint антипаттерна
- [ ] UC «почему запрос медленный (вставка)» → исправленная версия + объяснение
- [ ] Antipattern detector находит ≥ 5 нарушений в `src/cfe/Русский_Транзит/`  
  (известный technical debt)
- [ ] Demo video 5-7 минут с этими 5 UC — публикуется как «Объяснитель»

**Метрики успеха:**
- Точность RLS-tracer: ≥ 85% на golden dataset из 20 проблемных кейсов
- Diagnose latency: ≤ 30 сек end-to-end (с MCP вызовами)
- Demo video — конверсия landing → trial: цель ≥ 8% (baseline 1-3%)

**Зависимости:** M-K2 (vector store, embeddings)

**Риски:**
- TreeSitter BSL грамматика — может быть неполной для редких конструкций  
  (директивы препроцессора). Mitigation: fallback на текстовый парсинг.
- Diagnose engine rules — нужны реальные кейсы пользователей. Mitigation:  
  собрать ≥ 20 кейсов из своей практики (Транзит, УСО) до старта.

---

### M-K4: Normative + Hybrid Retrieval + Advanced Diagnose

**Срок:** 4-5 недель, до **25.10.2026**

**Цель:** Углубление L4 (нестандартные диагностики) + полное L5 (compliance) +  
hybrid retrieval для точности. Готовность к **INFOSTART A&PM EVENT октябрь  
2026** как ключевому каналу.

**Содержание:**
- L4-4 UC «Deadlock-tracer»
- L4-6 Hypothesis-Driven Reasoning Framework
- L5-4 UC «Compliance check» (соответствие ИТС-стандартам)
- L5-5 UC «Refactor God-модуля по DDD»
- L3-5 Sessions encoder (semantic поиск по истории)
- L3-6 UC «Объясни функцию построчно»
- X-5 Hybrid Retrieval (BM25 + Vector + Reranker)
- UX-7 Citation Layer (как Perplexity)
- OPS-2 Telemetry / Indexing Quality Metrics
- OPS-5 Knowledge Layer как MCP Server

**Definition of Done:**
- [ ] UC deadlock-tracer на тестовом кейсе работает
- [ ] UC compliance check выдаёт PDF-отчёт по конфигурации
- [ ] Hybrid retrieval — precision@5 ≥ 85% (vs ≥ 70% только vector в M-K2)
- [ ] Citations в ответах LLM — каждое утверждение с источником, hover preview
- [ ] Knowledge Layer экспонируется как MCP-server на порту 7070
- [ ] Доклад для A&PM EVENT принят (заявка до 31.08)

**Метрики успеха:**
- A&PM EVENT — доклад + стенд + ≥ 50 trial-регистраций с конференции
- Hybrid retrieval precision@5: ≥ 85%
- Compliance report: распознавание 11 AI-антипаттернов из rules/1c

**Зависимости:** M-K3 (engine + UCs)

**Риски:**
- Заявка на A&PM EVENT — дедлайн жёсткий. Mitigation: подать в первую неделю  
  M-K3, не ждать готовности.

---

### M-K5: Predictive (L6) — Temporal + 8.5-Ready (revenue trigger)

**Срок:** 5-7 недель, до **20.12.2026**

**Цель:** Запустить **8.5-Ready Assessment** как отдельный paid сервис  
(прямой revenue до релиза Knowledge Layer как продукта).  
Базовый L6 — temporal + сравнение с типовой.

**Содержание:**
- L6-1 UC «Temporal Diff» (что менялось)
- L6-2 UC «Сравни с типовой УТ 11.5»
- L6-3 Reference Configurations Library
- **L6-4 UC «8.5-Ready Assessment»**
- **PG-4 8.5-Ready как standalone offering**
- UX-3 ComparisonCard
- UX-4 TimelineCard
- UX-5 ProcessCard (BPMN)
- L2-7 UC «UI-trace кнопки до регистра»
- OPS-3 Knowledge Layer Export / Import

**Definition of Done:**
- [ ] Reference configurations library содержит fingerprints УТ 11.5, ERP 2.5,  
  БП 3.0, УСО 2.5 (legal — только metadata, не код)
- [ ] UC «сравни мою базу с УТ 11.5» — отчёт с конкретными отличиями
- [ ] **8.5-Ready Assessment** — landing page + payment + automated pipeline:  
  загружаешь .dt → платишь 9900-49000 ₽ → получаешь PDF-отчёт с рисками
- [ ] Diff API 8.3 vs 8.5 заполнен (как минимум по 20 ключевым API изменениям)
- [ ] Export/Import работает: bundle .klzip переносится между машинами

**Метрики успеха:**
- **8.5-Ready Assessment**: ≥ 10 платных кейсов в первый месяц (Sep-Oct 2026)
- ROI пользователя: «вместо 2 недель ручного аудита — 1 день»
- 8.5-Ready как разогрев перед launch — генерит leads для основного продукта

**Зависимости:** M-K3 (graph), M-K4 (compliance)

**Риски:**
- Reference configurations — могут быть юридические вопросы по lawful inspection  
  типовых. Mitigation: только fingerprint + структура, не код типовой.

---

### M-K6: Predictive++ — NL2SQL + Cross-Config + Enterprise

**Срок:** 6-10 недель, до **28.02.2027**

**Цель:** Закрыть долгосрочный moat: NL2SQL, cross-configuration patterns,  
auto code review. Финализация pricing tier'ов и партнёрской программы.

**Содержание:**
- L6-5 UC «Cross-Configuration Patterns» (benchmark vs отрасль)
- L6-6 UC «Natural Language Query over Config» (NL2SQL)
- L6-7 UC «Automated Code Review» (git hook)
- PG-1 Per-Configuration Tier — финальный pricing
- PG-5 Franchise Bulk License
- PG-6 Self-Hosted License (КИИ-compliant)
- UX-8 Conversational Drill-Down chips

**Definition of Done:**
- [ ] NL2SQL: «покажи поставщиков без оплаты за 90 дней» → запрос + Table card
- [ ] GitHub/GitLab webhook → comments на PR с file:line + ИТС-ссылками
- [ ] Cross-config benchmark при ≥ 50 проиндексированных конфигурациях  
  (opt-in аналитиков)
- [ ] 3 франчайзи-партнёра подписаны на Bulk License
- [ ] ≥ 1 Enterprise self-hosted клиент

**Метрики успеха:**
- MRR: ≥ 500 000 ₽ к январю 2027
- Self-hosted клиенты: ≥ 1
- Franchise contracts: ≥ 3

**Зависимости:** Все предыдущие M-K1..M-K5

---

## 6. Структура работы (как делаем)

### 6.1. Один милстоун = один branch + один summary

```
feature/m-k1-foundation
feature/m-k2-knowledge-foundation
feature/m-k3-relational-behavioral
...
```

После завершения — `.planning/knowledge-layer-2026-05-24/phases/M-Kx/SUMMARY.md`.

### 6.2. Phases внутри милстоуна

Один милстоун = 3-7 phases. Каждая phase:

- Имеет PLAN.md (что делаем) + SUMMARY.md (что сделали)
- Атомарна (1-5 дней)
- Покрыта тестами (unit + integration + по возможности E2E)
- Заканчивается коммитом и обновлением STATE.md

### 6.3. State tracking

Главный файл состояния: `.planning/knowledge-layer-2026-05-24/STATE.md`.  
Обновляется после каждой завершённой phase. Содержит:
- Активный милстоун + phase
- % прогресса
- Что blocked и почему
- Что следующее
- Last update + last commit hash

### 6.4. Architecture Decision Records (ADR)

Любое архитектурное решение → `.planning/knowledge-layer-2026-05-24/adr/NNN-name.md`.  
Формат:
```markdown
# ADR-NNN: <название>

## Context
## Decision
## Consequences
## Alternatives considered
```

В M-K1 пишем минимум 3 ADR: vector DB, graph DB, embeddings runtime.

### 6.5. Risk registry

`.planning/knowledge-layer-2026-05-24/RISKS.md` — live document.  
Каждый риск: severity (HIGH/MEDIUM/LOW), trigger, mitigation, owner.

### 6.6. Связь с основным проектом

- **M-K0 Stabilization — ПЕРВЫМ.** Включает 9 CRITICAL + 19 HIGH findings из  
  общего аудита (`План_развития_1С_Аналитик_2026-05-24.xlsx`). Knowledge Layer  
  не стартует до закрытия M-K0.
- **Remaining findings** (71 пункт MEDIUM/LOW) — параллельно с M-K1..M-K6,  
  по 1-2 в неделю как «гигиенические» коммиты, приоритезированные владельцем.
- Каждая phase Knowledge Layer проверяет не ломает ли существующий продукт  
  (`pnpm vitest run` + `pytest`).

---

## 7. Governance (как принимаем решения)

### 7.1. Approval gates

Перед началом каждого милстоуна — **gate check** с владельцем (Никита):
- ✓ Цель милстоуна актуальна?
- ✓ Метрики успеха согласованы?
- ✓ Зависимости готовы?
- ✓ Риски приняты?

Без явного approval — следующий милстоун не стартует.

### 7.2. Scope changes

Если в середине милстоуна — новая фича/изменение → **CONFUSION block** для  
владельца:

```
CONFUSION: <что изменилось>
Options:
  A) Включить в текущий милстоун (сдвиг даты)
  B) Отложить в backlog для следующего милстоуна
  C) Пересмотреть приоритет следующего милстоуна
→ Какой выбрать?
```

Никаких молчаливых скоупа изменений.

### 7.3. Правило 3 итераций (Матаков)

Если за 3 раунда работы над задачей нет прогресса → STOP, перевести в backlog,  
переформулировать spec. Подробнее: `rules/1c/1c-ai-collaboration.md`.

### 7.4. Качество vs скорость

Приоритет: **качество > скорость**. Лучше милстоун задержится на неделю,  
но `Definition of Done` выполнено полностью, чем «формально done с 60% качества».

---

## 8. Метрики продукта (отслеживаем непрерывно)

### Продуктовые

- Активные конфигурации (количество с ≥ 1 запросом в неделю)
- Запросы в день (avg)
- Diagnose accuracy на golden dataset (ежемесячно)
- Retrieval precision@5 (semantic + hybrid)
- Time to first answer (TTFA) — от вопроса до начала ответа
- Index rebuild time (per configuration)

### Бизнес

- MRR
- Активные подписки по tier'ам
- 8.5-Ready Assessment — количество и средний чек
- Trial → paid conversion
- Churn (отток)
- CAC по каналам (Infostart / Telegram / A&PM EVENT)

### Технические

- Backend test coverage по критичным модулям (target ≥ 80%)
- Bundle size Electron installer (target ≤ 800 MB после BGE-M3)
- Memory footprint при индексации средней УТ (target ≤ 4 GB)
- E2E happy-path latency (UC-1 RLS-tracer ≤ 30 сек)

---

## 9. Anti-goals (явно НЕ делаем)

Чтобы не разбрасываться:

- ❌ **Не делаем свой LLM** — используем NVIDIA NIM / Cloud.ru / DeepSeek
- ❌ **Не делаем редактор кода** — мы analyzer, не IDE
- ❌ **Не пишем код за пользователя** (это Напарник, мы — explainer)
- ❌ **Не индексируем чужие базы 1С на cloud-сервере** (local-first до M-K6)
- ❌ **Не делаем mobile / web SaaS hosted нами** в первый год  
  (152-ФЗ + KII запрет)
- ❌ **Не покупаем NebulaGraph / Neo4j / Kuzu** (SQLite CTE достаточно)
- ❌ **Не используем proprietary embeddings** (Voyage / OpenAI) — только local
- ❌ **Не паримся с macOS/Linux в M-K1..M-K4** — Windows-only до commerce launch

---

## 10. Связанные документы

### В этой папке

| Файл | Что |
|------|-----|
| `README.md` | Точка входа, навигация |
| `PLAN.md` | Этот файл — стратегия + roadmap |
| `STATE.md` | Текущий snapshot прогресса |
| `CLAUDE-RESUME.md` | Operational protocol для Claude |
| `Knowledge_Layer_*.xlsx` | 63 findings × 16 колонок |
| `phases/M-Kx/` | Детальные планы фаз |
| `adr/NNN-*.md` | Architecture Decision Records |
| `RISKS.md` | Live risk registry |

### В основном проекте

| Файл | Что |
|------|-----|
| `PROJECT.md` | Vision основного продукта v1.x |
| `ROADMAP.md` | Существующий roadmap M1-M7 |
| `.planning/STATE.md` | Состояние M7 Commerce Readiness |
| `.planning/development-plan-2026-05-24/План_развития_*.xlsx` | 99 общих findings  |
| `CHANGELOG.md` | История релизов |
| `rules/1c/*.md` | Стандарты разработки 1С (используем как корпус для L5) |

### Внешние

- Excel-планы — `.planning/development-plan-2026-05-24/` и  
  `.planning/knowledge-layer-2026-05-24/`
- Memory — `~/.claude/projects/C--CLOUDE-PR/memory/` (research, кейсы)
- Tools — `C:/CLOUDE_PR/tools/` (ssl_3_2, OnesTemplates, bsl-language-server,  
  mcp-1c-readonly)

---

## 11. Версионирование плана

Этот PLAN.md живой. При значимых изменениях:
- Бамп версии (1.0 → 1.1 минор, 2.0 мажор)
- Запись в секции `Changelog` внизу
- Commit в git с тегом `plan-v1.1`

### Changelog

- **1.2** (2026-05-25): Интегрирован M6 Handoff. Добавлен раздел «Связь с M6  
  Handoff» в начале. M6 фазы 12-18 мапятся на M-K1..M-K5 без смены  
  нумерации. Срок M-K1: 1-2 → 2-3 нед (Multi-MCP). M-K2: 3-4 → 4-5 нед  
  (Triple RAG). M-K3: 4-6 → 6-8 нед (EPF/CFE + BSL LS streaming).  
  Финальный M-K5: 20.12.2026 → 15.01.2027 (+1.5 мес). Детали:  
  `../milestones/M6-INTEGRATED-PLAN.md` и `INTEGRATION-DECISIONS.md`.
- **1.1** (2026-05-25): Добавлен M-K0 Stabilization как первый милстоун перед  
  M-K1. Содержание — 28 critical+high findings из общего аудита проекта.  
  Сдвинуты все даты M-K1..M-K6 на +3-4 недели. Раздел 6.6 обновлён —  
  параллельная работа над оставшимися 71 finding не блокеры.
- **1.0** (2026-05-24): Создан после deep research на основе 99 общих findings  
  + 63 Knowledge Layer findings + market research.
