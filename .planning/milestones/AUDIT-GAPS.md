# Audit Gaps — что пропущено в интеграции M6 ⇄ Knowledge Layer

**Создан:** 2026-05-25 (после ревизии)
**Триггер:** запрос пользователя «идеально выполнить два плана»
**Аудитор:** Claude (этот session)
**Status:** REQUIRES USER INPUT

---

## Контекст

Прошёлся по обоим планам после Wave 2 PERF. Цель — найти **всё что было упущено**
при интеграции M6 handoff в Knowledge Layer plan. Это **не код**, это аудит
полноты планов. Без закрытия gap'ов нельзя начинать дальнейшее выполнение.

**Проверены документы:**
- `handoff/m6-quality-expansion/` 00, 01, 02, 04, 08 (5 из 12 файлов)
- `knowledge-layer-2026-05-24/PLAN.md` v1.2 (полностью)
- `milestones/INTEGRATION-DECISIONS.md` v1.0 (полностью)
- `phases/M-K0-stabilization/STATE.md` (полностью)

**Не читал** (но видел оглавление): 03 (delivery modes), 05 (timeline), 06 (risks),
07 (code skeletons), 09 (current state) — если пропустил там что-то, нужен второй
проход.

---

## Gap-список (15 пунктов)

### 🔴 Критичные (блокируют следующие шаги)

#### G1. 1С:Напарник (`1c-buddy`) — не оформлен как технология в Knowledge Layer

**Что есть:**
- В **M6 handoff** (04-PHASES-PLAN.md строка 98): `ИТС + Напарник (1c-buddy :6002)` —
  default seed в Phase 12.10
- В **M6 INTEGRATION-DECISIONS** §Reject 3: «1c-buddy включён в 3 MCP в M-K1»
- В **Knowledge Layer PLAN.md**: упомянут **только как конкурент**, не как технология

**Чего нет:**
- ❌ Задачи в M-K1 «seed default connection: 1c-buddy на :6002»
- ❌ Решения **«использовать `buddy.search_its` для L5 ИТС vs строить свой crawler»**
  (плановый L5-1)
- ❌ Lifecycle plan «что после 01.10.2026 когда Напарник станет платным»
- ❌ Учёт что **сегодня MCP `mcp__1c-buddy__*` ОТВАЛИЛСЯ** (system-reminder
  начала сессии: «MCP server disconnected»)

**Impact:** блокирует решение по архитектуре L5 RAG (M-K2-4). Может дублировать
работу или упустить готовое решение.

**Action:** **новый вопрос Q-NEW** в INTEGRATION-DECISIONS.md (build vs buy для L5).

---

#### G2. Open Questions Q1, Q2, Q4 — НЕ решены пользователем

Из `INTEGRATION-DECISIONS.md` (мой собственный документ):
- **Q1** CFE префикс vs подсистема → рекомендация C, **молчание ≠ согласие**
- **Q2** для каких типовых → рекомендация C, **молчание ≠ согласие**
- **Q4** MetaVision CLI fork vs GUI wrapper → рекомендация A, **молчание ≠ согласие**

Q3 (EPF first) и Q6 (Dual license) — ✅ решены пользователем.
Q5 (cert), Q7 (соло) — отложены / приняты по умолчанию.

**Impact:** без Q1/Q2 не стартует **M-K3 EPF/CFE delivery** (нельзя писать
`АП_ОбщийМодуль` если не знаем подсистема vs префикс). Без Q4 — рискуем 5-7 дней
Java работы на MetaVision fork который пользователь не хотел.

**Action:** **спросить пользователя сейчас**, до начала M-K0.4 (PROMPT-1) —
эти решения не влияют на M-K0, но влияют на план M-K3.

---

#### G3. M-K1-PLAN.md не пересмотрен под решения Q3=A + Q6=C

**Что есть:** `phases/M-K1/M-K1-PLAN.md` (22 KB, 17 фаз после M6 merge)

**Чего нет:**
- ❌ В M-K1.1 секции — нет упоминания «`AnalyticLite.epf` EPF first» (Q3=A)
- ❌ В M-K1 нет задач «создать `LICENSE-CORE` (Apache 2.0), `LICENSE-EPF`,
  `LICENSE-CFE` (proprietary), `NOTICE` с атрибуциями» (Q6=C consequence)
- ❌ Capabilities matrix (23 features) — упомянута, но **не оформлена как
  TypeScript enum / Python Literal type в plan'е**
- ❌ MCPConnection миграция БД (5 новых полей: mode/configuration/platform/
  ext_version/capabilities) — **не зафиксировано alembic vs прямые DDL**

**Impact:** M-K1 при старте будет **переписан на ходу**, что увеличит сроки и
риск багов.

**Action:** обновить `phases/M-K1/M-K1-PLAN.md` отдельной задачей **до старта
M-K1**, после ответов Q1/Q2/Q4.

---

### 🟡 Серьёзные (создают long-term tech-debt)

#### G4. Тройной RAG: расхождение между M6 Phase 14 и Knowledge Layer L5

**M6 Phase 14:** v8std (317 std) + ssl_api (~3000 БСП методов) + **platform_hbk
(~5000 entries)**

**Knowledge Layer M-K2:** L5-1 ИТС RAG (v8327doc + v8std) + L5-2 БСП Pattern Index
**БЕЗ platform_hbk**

**Status в INTEGRATION-DECISIONS.md §Reject 2:** .hbk parser в **M-K2.4 под риском**,
если за 1 неделю не получится — отдаём в backlog M-K4.

**Что упущено:**
- ❌ **Acceptance criterion для M-K2.4**: «если .hbk не получится — fallback на
  alternative source X» (что X? bsl-language-server умеет читать .hbk?)
- ❌ **Cost estimate для embeddings** $250 (M6 Phase 14 budget) — **не учтён** в
  Knowledge Layer плане cost section

**Impact:** в M-K2 риск потратить неделю на .hbk без чёткого fallback.

**Action:** уточнить в M-K2 декомпозиции — спайк на .hbk parser (3 дня timeline)
с явным go/no-go gate.

---

#### G5. BSL LS live streaming vs after-the-fact detector

**M6 Phase 15:** WebSocket streaming diagnostics (LLM stream → debounce 500ms →
BSL LS subprocess → WS push → live highlighting в CodeCard). 10 atomic tasks.

**Knowledge Layer M-K3:** L5-3 Antipattern Detector (A1-A11 + BSL LS) — **detector
после генерации**, без streaming.

**INTEGRATION-DECISIONS.md §Merge 3** упоминает: «BSL LS live diagnostics + WebSocket»
влит в M-K3, но **deet атомарных задач нет**.

**Что упущено:**
- ❌ Решение «WebSocket streaming реализуем сразу (M6 way) или начинаем с
  detector then iterate (KL way)»
- ❌ Task: **bundle BSL LS jar (113 MB) + JRE 17 (~80 MB) в Electron** — это
  значимо раздувает installer

**Impact:** разное скоупа — 2 дня (detector) vs 10 дней (streaming).

**Action:** **новый вопрос Q-NEW-2** или решение по умолчанию + добавить в
M-K3 декомпозицию.

---

#### G6. MetaVision integration vs свой граф через TreeSitter

**M6 Phase 16** (20-28 дней!): MetaVision fork + CLI + Java subprocess + D3 frontend.

**Knowledge Layer M-K3 (L2):** свой граф через TreeSitter + SQLite + React Flow.

**Это два разных подхода к одной цели** (call graph). INTEGRATION-DECISIONS.md
§Merge 4 говорит «MetaVision CLI fork + MetaVisionGraph card» — но **рядом** с
L2 Knowledge Graph. То есть будут **дублировать** функционал.

**Что упущено:**
- ❌ Decision: «MetaVision = primary, наш граф = fallback» или «наш граф =
  primary, MetaVision = visualization only»?
- ❌ Phase 16 risk: «MetaVision GUI-only fork → CLI» = 5-7 дней Java работы
  **без гарантии что выйдет** (06-RISKS из M6 handoff подтверждает это HIGH risk)

**Impact:** до 28 дней потенциально потерянного времени.

**Action:** **зависит от Q4** (пользователь подтвердит подход MetaVision) +
явное решение «MetaVision или наш граф primary».

---

#### G7. EPF/CFE атомарные задачи не написаны в Knowledge Layer

**M6 Phase 13a** (EPF, 10-14 дней): 10 atomic tasks (13a.1-13a.10)
**M6 Phase 13b** (CFE, 15-21 день): 14 atomic tasks (13b.1.1 - 13b.5.2)

**Knowledge Layer M-K3:** обозначен как «M-K3 + M6 Phase 13a+13b+15+17 merged»
— но **нет файла `phases/M-K3/M-K3-PLAN.md`** с детальной декомпозицией.

**Impact:** при старте M-K3 будем **переписывать план на ходу**, как с M-K1.

**Action:** **до старта M-K3** — создать `phases/M-K3/M-K3-PLAN.md` со всеми
atomic tasks из M6 Phase 13a/13b/15/17 + интеграция с моими UC (RLS-tracer и т.д.).

---

#### G8. HMAC SSO + Activity Stream + Posting Trace — не в Knowledge Layer

**M6 Phase 13b.4.1 (HMAC SSO) + 13b.2 (Activity Stream) + 13b.3 (Posting Trace):**
CFE-only фичи, ~7 дней суммарно.

**Knowledge Layer:** обозначены только в INTEGRATION-DECISIONS.md §accepted
№8 как «Activity Stream + Posting Trace как CFE-only фичи в M-K4».

**Что упущено:**
- ❌ Phase plan `phases/M-K4/M-K4-PLAN.md` не существует
- ❌ Связь Activity Stream (runtime events) с L4 Behavioral reasoning (например
  «почему этот документ записался с такими движениями?») — **не проработана**

**Impact:** будем терять контекст между «monitoring» и «reasoning» доменами.

**Action:** при создании M-K4-PLAN.md явно связать Activity Stream → L4 use cases.

---

### 🟢 Тактические (low risk, требуют упоминания)

#### G9. Distribution v2.0 (M6 Phase 18) — нет детализации в M-K5

**M6 Phase 18** (7-10 дней): Electron rebuild (~250 MB), CFE signing,
electron-updater granular updates, first-run wizard, release notes,
auto-update protocol.

**Knowledge Layer M-K5:** «PG-4 8.5-Ready Assessment как paid сервис».
Distribution не упомянут в M-K5 decomposition.

**Action:** при создании M-K5-PLAN.md (за неделю до M-K5 start) — добавить
Distribution v2.0 как Phase M-K5.X.

---

#### G10. Capabilities Matrix (23) — не оформлены как тип

**M6 указывает 23 capabilities** (8 base + 3 conditional + 12 extended):
`mcp.execute_query`, `cfe.activity_stream`, `tools_ui.query_console`, etc.

**Knowledge Layer plan**: упомянуты как «23 capabilities» без перечня.

**Action:** в M-K1.x создать `backend/app/types/capabilities.py` (Python Literal
type) + `frontend/lib/capabilities.ts` (TS const enum). Использовать в
`useCapability` hook и backend authorization.

---

#### G11. Cards registry — 13 типов (8 M6 + 5 KL)

**M6 Phase 17**: 8 новых cards (BSLDiagnostics, StandardsCitation, ITSArticle,
BSPMethod, PlatformHelp, MetaVisionGraph, Antipattern, Metrics).

**Knowledge Layer UX-1..UX-8**: 5 cards (GraphCard, DiagnoseCard, ComparisonCard,
TimelineCard, ProcessCard + UX-7 Citation Layer).

**Итого 13 типов cards**, плюс существующие 6 (table/object/log/metric/refs/code) =
**19 типов cards** в финальном продукте.

**Action:** в M-K3 (где появляются первые M6 cards) — создать `frontend/lib/
card-registry.ts` с типизированным реестром. Обновить `CardRenderer`.

---

#### G12. MCPConnection schema migration — alembic vs DDL

Текущий backend использует **прямые DDL** в `backend/app/storage/migrations.py`
(я видел при PERF-1). M6 предполагает **alembic** для capability fields migration
(Phase 12.1).

**Что упущено:** решение «alembic в M-K1 (M6 way) или продолжаем DDL (текущая
конвенция проекта)».

**Action:** **новый ADR-005-migrations** в M-K1 — фиксирует выбор. Рекомендую
**продолжить прямые DDL** (consistency с существующим migrations.py + меньше
зависимостей в Electron bundle).

---

#### G13. Tool routing accuracy — должен учитывать 23 capabilities

**M-K0 metric:** «Tool selection accuracy (golden dataset): ≥ 80%»
(PLAN.md строка 308).

**PROMPT-1** (следующая задача после Wave 2 PERF) — должен **routing'ить** между
**сколько tools?** Сейчас в orchestrator только Toolkit (10 tools). После M-K1
Multi-MCP — будет 5 MCP × N tools = десятки. Few-shot examples для PROMPT-1
должны **учитывать unified registry с префиксами** (`toolkit.execute_query`,
`buddy.search_its`, и т.д.).

**Что упущено:** PROMPT-1 spec **не учитывает unified tool registry**. Я бы
сделал few-shot для 10 базовых tools, а потом пришлось бы переделывать.

**Action:** уточнить scope PROMPT-1 — делаем для текущих 10 toolkit tools (Wave 3)
и **отдельно** перерабатываем в M-K1 после Orchestrator? Или сразу делаем для
unified registry?

---

#### G14. RISKS.md / CHECKLIST.md — не созданы

PLAN.md §6.5: «`RISKS.md` — live document» — **не существует**.
PLAN.md §10: упоминает «`CHECKLIST.md`» (косвенно, через governance) — нет.

INTEGRATION-DECISIONS.md упоминает что эти файлы должны быть.

**Action:** создать оба в M-K1.1 (kickoff) с initial entries из M6 06-RISKS-AND-
MITIGATION.md (HIGH/MEDIUM risks).

---

#### G15. ADR-001..004 — не созданы

PLAN.md §6.4: «В M-K1 пишем минимум 3 ADR: vector DB, graph DB, embeddings
runtime».
INTEGRATION-DECISIONS.md §accepted №1: «ADR-004 Capability Discovery в M-K1».

**Что упущено:** ADR-001 (sqlite-vec), ADR-002 (SQLite+CTE), ADR-003 (FastEmbed),
ADR-004 (Capability Discovery), **ADR-005 (migrations strategy — см. G12)**.

**Action:** создать ВСЕ 5 ADR в M-K1.1 как первая задача (≤ 2 часа на каждый).

---

## Priority Matrix

| # | Gap | Severity | Blocks | Action | Owner |
|---|-----|----------|--------|--------|-------|
| G1 | Напарник как технология | HIGH | M-K2 L5 | Q-NEW в Decisions | Пользователь |
| G2 | Q1, Q2, Q4 не решены | HIGH | M-K3 | Ответы | Пользователь |
| G3 | M-K1-PLAN не пересмотрен | HIGH | M-K1 start | Update plan | Claude после Q1/Q2 |
| G4 | .hbk fallback не зафиксирован | MEDIUM | M-K2.4 | Phase decomp | Claude в M-K2 |
| G5 | BSL LS streaming vs detector | MEDIUM | M-K3 | Q-NEW-2 | Пользователь |
| G6 | MetaVision vs свой граф | MEDIUM | M-K3 L2 / Phase 16 | Q4 + decision | Пользователь |
| G7 | EPF/CFE atomic tasks нет | HIGH | M-K3 start | Create M-K3-PLAN | Claude после Q1/Q2 |
| G8 | HMAC SSO + Activity не в KL | MEDIUM | M-K4 | M-K4-PLAN | Claude в M-K4 |
| G9 | Distribution v2.0 в M-K5 | LOW | M-K5 | M-K5-PLAN | Claude в M-K5 |
| G10 | Capabilities как тип | LOW | M-K1 | M-K1 task | Claude в M-K1 |
| G11 | Cards registry | LOW | M-K3 | M-K3 task | Claude в M-K3 |
| G12 | alembic vs DDL | LOW | M-K1 | ADR-005 | Claude в M-K1 |
| G13 | PROMPT-1 tool routing scope | **CRITICAL** | **next task (PROMPT-1)** | **Decide now** | **Пользователь** |
| G14 | RISKS / CHECKLIST | LOW | governance | M-K1.1 | Claude в M-K1 |
| G15 | ADR-001..005 | LOW | M-K1 | M-K1.1 | Claude в M-K1 |

---

## Что блокирует следующие шаги

### Чтобы начать PROMPT-1 (следующее в M-K0):
- ✅ **G13** — нужно решение: PROMPT-1 для 10 базовых tools (быстро) или для
  unified registry с префиксами (правильно, но 2× больше времени)

### Чтобы начать M-K1:
- ✅ G3 (M-K1 plan update — Claude сделает после Q ответов)
- ✅ G1, G2 (вопросы пользователя)

### Чтобы начать M-K3 (EPF/CFE):
- ✅ G2 (Q1, Q2)
- ✅ G5 (BSL LS scope)
- ✅ G6 (MetaVision vs наш граф)
- ✅ G7 (M-K3-PLAN.md decomposition)

---

## Predлагаемая последовательность действий

1. **Пользователь отвечает на 4 вопроса** (Q1, Q2, Q4, Q-NEW Напарник, Q-NEW-2 BSL LS,
   G13 PROMPT-1 scope) — see USER-QUESTIONS секция ниже.
2. **Claude обновляет `INTEGRATION-DECISIONS.md`** — фиксирует ответы.
3. **Claude обновляет `phases/M-K1/M-K1-PLAN.md`** — учёт Q3/Q6 + capabilities + LICENSE.
4. **Claude создаёт `RISKS.md` + `CHECKLIST.md` + 5 ADR файлов** — pre-flight.
5. **Claude создаёт `phases/M-K3/M-K3-PLAN.md`** — atomic tasks из M6 Phase 13a/13b/15/17.
6. **Claude закрывает PROMPT-1 в M-K0** (с учётом G13 решения).
7. **Продолжение M-K0.4 → M-K0.10** по плану.

---

## USER-QUESTIONS (нужны ответы СЕЙЧАС)

См. отдельный блок в чате — задам через AskUserQuestion с 4 вопросами.
