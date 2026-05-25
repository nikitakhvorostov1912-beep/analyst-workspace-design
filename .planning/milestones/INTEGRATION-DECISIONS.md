# Integration Decisions — M6 Handoff ⇒ Knowledge Layer

**Создан:** 2026-05-25
**Триггер:** получен `C:/CLOUDE_PR/M6-Handoff-2026-05-25.zip` (12 файлов)
от другой сессии Claude.
**Результат интеграции:** `M6-INTEGRATED-PLAN.md` (этот же каталог).

---

## TL;DR

| Категория | Кол-во | Action |
|-----------|--------|--------|
| ✅ Принято без вопросов | 9 | Влиты в M-K1..M-K5 |
| 🔄 Слиты с моим планом | 6 | Merged как лучшее из двух |
| ✅ Резолюции пользователя | 6 | Q1, Q2, Q3, Q4, Q6, Q-NEW (Напарник) |
| ❌ Отклонены с обоснованием | 3 | Документировано |
| ⚠️ Открыто | 2 | Q5 (cert), Q7 (соло) — не блокирующие |

---

## ✅ Принято без вопросов (high-confidence)

Эти предложения handoff'а архитектурно правильны и согласуются с
текущей кодовой базой:

1. **Capability Discovery Protocol** через `experimental.analyst-1c.features`
   в MCP `initialize` → новое ADR-004 в M-K1.
2. **Двухрежимная архитектура EPF / CFE** с общим ядром (capability response,
   общие модули) → новая M-K3 phase.
3. **23 capabilities matrix** (8 base + 3 conditional + 12 CFE extended)
   → база для feature gates в frontend.
4. **`useCapability` hook + `FEATURE_MODULES` registry pattern** →
   стандарт для frontend в M-K1+.
5. **`UpgradeCTA` компонент** вместо просто скрытия disabled фич →
   UX улучшение для conversion EPF→CFE.
6. **Тройной RAG источник** — v8std (готов в `tools/v8std/`) + БСП API
   (готов в `tools/ssl_3_*`) + .hbk платформы (под риском, в M-K2.4).
7. **5 MCP параллельно через MCP Orchestrator** с unified tool registry
   (префиксы `toolkit.*`, `buddy.*`, `context.*`, `metr.*`, `edt.*`).
8. **`Activity Stream + Posting Trace` карточки** как CFE-only фичи через
   подписки на события → новый M-K4 контент.
9. **Готовые tools в `C:/CLOUDE_PR/tools/`** — переиспользуем 1c-buddy, v8std,
   ssl_3_*, MetaVision, BSL LS jar, JDK 17/21, MCP Toolkit, YAxUnit,
   Vanessa Automation, tools_ui_1c, Connector.

---

## 🔄 Слиты (merged best of two)

Эти решения сохранили **мою** логику + добавили лучшие куски из handoff:

### Merge 1: M-K1 Foundation + M6 Phase 12 → unified «Foundation + Multi-MCP»

- **Сохранил:** 3 ADR (vector DB, graph DB, embeddings), OPEN-VS-CLOSED.md,
  metadata_cache filler, Object Dossier API, UC «расскажи про объект».
- **Добавил из handoff:** ADR-004 Capability Discovery, MCP Orchestrator,
  unified tool registry, `MCPConnection` extended fields (5 новых),
  `useCapability` hook, `SourceSelector` refactor.
- **Срок:** 2-3 недели (vs 1-2 в исходном) — оправдано scope расширением.

### Merge 2: M-K2 Knowledge Foundation + M6 Phase 14 → «Knowledge Foundation + Triple RAG»

- **Сохранил:** Indexer Pipeline (X-1..X-4), vector store sqlite-vec, BGE-M3
  embeddings, Configuration Type Detection, Indexing Progress UI.
- **Добавил из handoff:** v8std structured RAG (317 ИТС .md из sfaqer),
  БСП API parser для `ssl_3_1`/`ssl_3_2`, .hbk parser (под риском Q4),
  тройной merge с priorities, CodeCard citations.
- **Срок:** 4-5 недель.

### Merge 3: M-K3 Relational + Behavioral + M6 Phases 13a+13b+15+17

- **Сохранил:** Knowledge Graph, BSL Parser TreeSitter, Diagnose Engine,
  топ-5 UC (RLS-tracer / report-tracer / цепочка / impact / query optimizer),
  Semantic Code Search, Antipattern Detector, GraphCard, DiagnoseCard.
- **Добавил из handoff:** EPF/CFE delivery (АналитикLite.epf + АналитикПлюс.cfe),
  Migration EPF↔CFE, PowerShell installer, Onboarding step 1.5, BSL LS
  live diagnostics + WebSocket, BSLDiagnostics card, Feature gates per capability.
- **Срок:** 6-8 недель (vs 4-6) — добавлены EPF/CFE delivery.

### Merge 4: M-K4 + M6 Phase 16 + 17b → «Visual + Activity Stream»

- **Сохранил:** L4-4 Deadlock-tracer, L4-6 Hypothesis reasoning, L5-4 Compliance,
  L5-5 Refactor planner, L3-5 Sessions encoder, L3-6 Explain функцию,
  X-5 Hybrid Retrieval, UX-7 Citation Layer, OPS-2 Telemetry, OPS-5 MCP Server.
- **Добавил из handoff:** MetaVision CLI fork + MetaVisionGraph card,
  Activity Stream realtime sidebar, Posting Trace card, Method Overrides.

### Merge 5: M-K5 Predictive + M6 Phase 18 → «Predictive + Distribution v2.0»

- **Сохранил:** L6-1..L6-4 use cases (temporal, vs типовой, reference configs,
  8.5-Ready), PG-4 8.5-Ready Assessment как paid сервис, UX-3/4/5 cards,
  L2-7, OPS-3 Export/Import.
- **Добавил из handoff:** Electron installer v2.0.0 (250 MB), EPF/CFE installers
  отдельные файлы, Bundled JRE 17, README-V2, INSTALL- docs.

### Merge 6: Decomposition фаз — сохранил **мою** нумерацию M-K0..M-K6

- Handoff использует Phase 12-18. Я остаюсь на M-K0..M-K6.
- M6 фазы 12-18 **мапятся** на M-K1..M-K5 (см. таблицу в M6-INTEGRATED-PLAN.md).
- Причина: уже создал `phases/M-K0-stabilization/`, `phases/M-K1/`, есть
  STATE.md с прогрессом — менять нумерацию = ломать ссылки.

---

## ⚠️ ОБСУДИ — требуют решения пользователя

Без ответов на **Q3 + Q6** не стартуем M-K1. Остальные можно по ходу.

### ✅ Q1. CFE именование — РЕШЕНО (2026-05-25)

**Ответ пользователя:** **C. Подсистема `АналитикПлюс` + префикс `АП_` для критичных**

**Что это значит:**
- Все объекты CFE — внутри подсистемы `АналитикПлюс` (БСП-стандарт grouping)
- **Общие модули** (наибольший риск конфликта имён в большой типовой) — с префиксом
  `АП_`: `АП_ОбщийМодуль`, `АП_AuthHMAC`, `АП_CapabilityResponse`, `АП_HTTPКоннектор`
- **Регистры** (специфичные для расширения) — без префикса: `МониторингАктивности`,
  `PostingTrace` (внутри подсистемы изоляция от типовых)
- **Обработки/формы** — без префикса (внутри подсистемы)
- **Реквизиты заимствованных типовых** (если будем добавлять) — с префиксом `АП_`

**Влияет на:**
- M-K3 (CFE delivery): все 1С-имена в плане 13b sub-фаз — соответствуют этой схеме
- M-K3.1 (EPF scaffold): тот же стандарт `АП_*` для общих модулей в EPF чтобы
  при migration EPF→CFE имена совпали

### ✅ Q2. CFE целевые типовые — РЕШЕНО (2026-05-25)

**Ответ пользователя:** **D. УТ 11.5 + ERP 2.5 + КА 2.5 + БГУ + ЗУП (всё на БСП 3.1+)**

**Что это значит:**
- Максимальный охват рынка типовых на базе БСП 3.1+
- Phase 13b.5.2 «Smoke tests on 3 typical» расширяется до **5 типовых**
- **Срок M-K3 +2 недели** (с 6-8 до 8-10 недель) — компенсация на тестирование
- Reference Configurations Library в M-K5 (L6-3) расширяется до 5 fingerprints
- **Риск:** БГУ/ЗУП могут иметь специфичные конфликты с capability features
  (например `cfe.method_overrides` для документов ЗП ≠ для документов УТ).

**Mitigation:**
- В Phase 13b.0 (новая, +0.5 дня) — feature-detection per configuration через
  `Метаданные.ВерсияСтандартныхПодсистем`
- Опциональные capabilities активируются если БСП >= 3.1.10 (общий minimum)
- В smoke tests — отдельный set per configuration type

**Влияет на:**
- M-K3 scope: +2 нед, теперь ~8-10 нед
- Reference Configurations Library (M-K5): 5 fingerprints вместо 3
- Финальная дата M-K5: 15.01.2027 → **30.01.2027** (+2 нед суммарно)

### ✅ Q4. MetaVision подход — РЕШЕНО (2026-05-25)

**Ответ пользователя:** **C. Spike 3 дня → решение по результату**

**Что это значит:**
- В начале M-K4 (Phase 16) — отдельный **Phase 16.0 Spike** длительностью 3 дня
- Цель спайка: проверить можно ли добавить CLI режим в MetaVision (без GUI deps)
  за разумное время
- **Go gate (после 3 дней):**
  - **Если PoC работает (CLI runs analyzer, выдаёт JSON)** → продолжаем Phase 16.1
    (full fork + integration), общий срок Phase 16 = 20-28 дней как в M6 plan
  - **Если PoC не работает** → переключаемся на наш граф (TreeSitter + SQLite +
    React Flow) как primary, MetaVision integration сводим к кнопке «Открыть в
    MetaVision desktop», срок Phase 16 = 8-10 дней (только наш граф)

**Влияет на:**
- M-K4 содержит conditional branch — Phase 16 имеет два варианта декомпозиции
- M-K3 L2 Knowledge Graph (TreeSitter + SQLite) делается **всегда** (для L4 reasoning)
- Если spike fail — наш граф становится primary visualization

### ✅ Q-NEW. 1С:Напарник как L5 источник — РЕШЕНО (2026-05-25)

**Ответ пользователя:** **B. Напарник primary, наш RAG fallback**

**Что это значит:**
- **Primary path:** runtime LLM использует `buddy.search_its` / `buddy.fetch_its`
  через 1c-buddy MCP на :6002 (пока бесплатно до 01.10.2026)
- **Fallback path:** наш RAG из v8std (sfaqer/v8std 317 ИТС стандартов в .md) +
  `tools/ssl_3_2/src/` БСП API parser
- Knowledge Layer L5-1 строит fallback corpus **параллельно** в M-K2, не блокирует
  primary path

**Lifecycle plan:**
- **Сейчас — 01.10.2026:** Primary = Напарник, fallback = наш RAG
- **01.10.2026 — TBD:** Перейти на наш RAG как primary (если Напарник станет
  дорогим) ИЛИ платить за Напарник (если ROI положительный — сравнить на metric
  «retrieval quality + retrieval cost per session»)
- **Метрика для решения:** в M-K4 OPS-2 Telemetry собираем «retrieval source
  used», «hit rate», «user clicked citation» для обоих путей

**Технические требования:**
- В M-K1 — задача «seed 1c-buddy MCP connection :6002» (Docker-image от
  feenlace/mcp-1c или native install + autostart)
- **Сегодня MCP `mcp__1c-buddy__*` отвалился** — необходим **healthcheck +
  auto-restart** для production reliability (не блокирует M-K0, но critical
  для M-K1)
- Backend RAG service в M-K2 имеет abstraction «primary → fallback» pattern
- Тест: degraded mode (1c-buddy down) → fallback на наш RAG → user видит warning
  badge «работаю на резервных стандартах»

**Влияет на:**
- M-K1: +1 задача (seed 1c-buddy + healthcheck)
- M-K2: L5-1 ИТС RAG fallback corpus (sfaqer) — фокус на корпусе, не на
  primary query path
- M-K4 OPS-2 Telemetry: расширенные метрики для build vs buy решения

### ⚠️ Q5. Code-signing cert — отложено (не блокирующее)

Рекомендация: B (self-signed для MVP), A (Sectigo OV ~$300/год) для commerce.
Уже в M-K0.7 как DEVOPS-1 EV cert. Решение можно отложить до v2.0 release.

### ⚠️ Q7. Команда — A (соло) по умолчанию

Текущий режим. Если появится бюджет — B/C/D в M-K4-M-K6.

### ✅ Q3. EPF first или CFE first? — РЕШЕНО (2026-05-25)

**Ответ пользователя:** **A. EPF first**

**Что это значит:**
- M-K3 начинаем с EPF (`АналитикLite.epf` ~3 MB) — quick start без правки конфигурации
- CFE (`АналитикПлюс.cfe` ~8 MB) строится **поверх** EPF инкрементально:
  - Общие модули EPF → переиспользуются в CFE
  - Capability response → общая инфраструктура
  - Migration EPF→CFE без потери истории сессий
- Time-to-demo: ~2 недели после M-K0 (vs ~4 недель для CFE-first)
- Onboarding step 1.5 (выбор EPF/CFE) — EPF как default-selected

**Влияет на:**
- M-K3 декомпозиция: Phase 13a (EPF) до Phase 13b (CFE)
- Frontend onboarding text: «Начни с .epf — установка 5 секунд»
- Marketing pitch: «Скачай файл, открой в 1С — за минуту получи AI-чат»

### ✅ Q6. Бизнес-модель / лицензирование? — РЕШЕНО (2026-05-25)

**Ответ пользователя:** **C. Dual license**

**Что это значит:**

| Компонент | Лицензия | Где живёт |
|-----------|----------|-----------|
| Core: Multi-MCP, RAG, BSL LS, Knowledge Layer | **Apache 2.0** | `backend/app/*`, `frontend/*` |
| EPF (`АналитикLite.epf`) | **Proprietary** | `epf-src/АналитикLite/` |
| CFE (`АналитикПлюс.cfe`) | **Proprietary** | `cfe-src/АналитикПлюс/` |
| Reference Configurations Library (L6-3) | **Proprietary** | M-K5 |
| Diagnose rulebook (L4-1 YAML) | **Proprietary** | `backend/app/knowledge/rulebook/` |
| `tools_ui_1c` обработки (GPL-3.0) | **Opt-in** | Установка отдельно через UI «Расширить EPF» |

**Действия:**
- Создать LICENSE-CORE (Apache 2.0) для backend/ frontend/ knowledge/
- Создать LICENSE-EPF, LICENSE-CFE (proprietary) для EPF/CFE папок
- Создать NOTICE с list атрибуций (БСП CC-BY-4.0, OnesTemplates, sfaqer/v8std, etc.)
- В EPF/CFE installer — отдельная checkbox «Включить tools_ui_1c (GPL-3.0)» с
  явным warning что это сделает их GPL-3.0 (виральная заразность)
- Marketing: «Open core + commercial extensions» как USP

**Влияет на:**
- Структура репо в M-K1 (LICENSE-* файлы + NOTICE)
- M-K3 EPF/CFE installer UX (opt-in checkbox)
- Public README (открыть GitHub репо как Apache 2.0)

### Дополнительные вопросы (не блокирующие):

- **Q4. MetaVision CLI fork vs GUI integration?** Рекомендация: **A** (fork)
  с fallback на C (кнопка «Открыть в MetaVision») если CLI не получится за неделю.
- **Q5. Code-signing cert?** Рекомендация: **B** для MVP (self-signed +
  README инструкция SmartScreen), **A** (~$300/год Sectigo OV) для commerce.
  Уже включил `DEVOPS-1 EV cert` в M-K0, но это **не блокирующий** — можно
  отложить до v2.0 release.
- **Q7. Соло или команда?** Принимаю по умолчанию **A соло** — мой текущий
  режим работы.

---

## ❌ Отклонено с обоснованием

### Reject 1: Новая нумерация фаз (Phase 12-18)

**Что предлагал handoff:** перейти на Phase 12-18 (как у них).

**Почему отклонил:** уже создал `phases/M-K0-stabilization/`, `phases/M-K1/`,
есть STATE.md, ссылки в commit messages (7 коммитов в M-K0.1). Менять = ломать
historical trail.

**Решение:** оставляем M-K0..M-K6 нумерацию. M6 фазы 12-18 **мапятся** на
M-K1..M-K5 через таблицу в M6-INTEGRATED-PLAN.md.

### Reject 2: «Тройной RAG» обязательно все 3 источника к M-K2 done

**Что предлагал handoff:** v8std + БСП + .hbk parser — все 3 в Phase 14.

**Почему отклонил:** .hbk файл платформы — закрытый формат 1С, парсер сложен
(R2 в `06-RISKS-AND-MITIGATION.md` помечен MEDIUM risk). Готовый sfaqer/v8std
покрывает 317 стандартов — для MVP «Объяснитель» этого достаточно.

**Решение:** .hbk parser отдаётся в **M-K2.4 (под риском)**. Если за 1 неделю
не получится — отдаём в backlog M-K4. v8std + БСП достаточно для core flow.

### Reject 3: 5 MCP сразу обязательно

**Что предлагал handoff:** Toolkit + 1c-buddy + mcp-bsl-context + METR +
EDT-MCP — все 5 одновременно в M-K1.

**Почему отклонил частично:** EDT-MCP требует запущенного EDT (Eclipse-based
IDE для 1С разработчиков). Обычный аналитик его не использует. METR
(test runner) — нишевый для разработчиков тестов.

**Решение:** в M-K1 включаем 3 MCP (Toolkit + 1c-buddy + mcp-bsl-context),
METR + EDT-MCP — **disabled by default**, активируются если пользователь
включает в Settings. Архитектура (Orchestrator) готова для всех 5 — это
покрывает «5 MCP параллельно» технически.

---

## Diff vs предыдущей версии KL плана

### Изменения в `knowledge-layer-2026-05-24/PLAN.md` v1.1 → v1.2:

- **+1 milestone-секция:** «Связь с M6 Handoff» — ссылается на этот документ
- **Срок M-K1:** 1-2 нед → 2-3 нед (Multi-MCP добавлен)
- **Срок M-K2:** 3-4 нед → 4-5 нед (Triple RAG добавлен)
- **Срок M-K3:** 4-6 нед → 6-8 нед (EPF/CFE + BSL LS streaming добавлены)
- **Финальная дата M-K5:** 20.12.2026 → 15.01.2027 (+1.5 мес суммарно)
- **Архитектурные принципы +1:** Capability-based UI (ADR-004 в M-K1)
- **Anti-goals без изменений** (work-modes ban остаётся)

### Новые файлы:

- `M6-INTEGRATED-PLAN.md` (этот же каталог) — unified roadmap
- `INTEGRATION-DECISIONS.md` (этот файл) — что принято/отклонено
- `M6-handoff-source/` (рекомендую копию zip распакованную для аудита)

### Файлы которые НЕ меняются:

- `phases/M-K0-stabilization/` — milestone в работе, не трогаем
- `phases/M-K1/M-K1-PLAN.md` — будет обновлён ПОСЛЕ M-K0 кода с учётом Q3/Q6
- `Knowledge_Layer_*.xlsx` — 63 finding'а остаются, добавим колонку
  «M6 Phase mapping» в следующей пересборке

---

## Чек-лист для пользователя

Прочитай этот документ и:

- [ ] Ответь на **Q3** (EPF first или CFE first) — блокирующий
- [ ] Ответь на **Q6** (лицензия) — блокирующий
- [ ] (опц.) Ответь на Q1 (CFE именование) — иначе по умолчанию C
- [ ] (опц.) Ответь на Q2 (типовые) — иначе по умолчанию C (УТ+ERP+КА)
- [ ] (опц.) Ответь на Q4 (MetaVision подход) — иначе A
- [ ] (опц.) Подтверди Q7 (соло) — иначе уточни команду
- [ ] Дай **«go»** на M-K0.2 Wave 1 Backend Quality (или сначала фикс
  чего-то другого)

После ответов — я обновлю `phases/M-K1/M-K1-PLAN.md` с конкретикой и продолжу
M-K0 Wave 1.

---

## История

- **2026-05-25 v1.1**: Получены ответы пользователя на Q1, Q2, Q4, Q-NEW (Напарник)
  после ревизии планов через `AUDIT-GAPS.md`. Все блокирующие вопросы M-K1/M-K3
  закрыты. Срок M-K3 +2 нед (Q2=D добавил БГУ/ЗУП), финал M-K5: 30.01.2027.
  Q5/Q7 не блокируют и отложены.
- **2026-05-25 v1.0**: Создан после получения и разбора `M6-Handoff-2026-05-25.zip`.
  9 accepted + 6 merged + 4 ждут пользователя + 3 rejected = 22 решения.
