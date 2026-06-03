---
plan_version: 1.7
milestone: M-K3
milestone_name: "Relational + Behavioral + EPF/CFE Delivery"
status: in_progress  # M-K0/K1/K2 ✅. M-K3 active (EPF-скелет). Часть M-K4 авансом. 2026-05-29.
last_updated: "2026-05-29T10:30:00Z"
unified_roadmap: "../ROADMAP-2026-05-29.md"  # единый форвард-источник (2026-05-29)
m6_handoff_integrated: true
m6_handoff_doc: "../milestones/M6-INTEGRATED-PLAN.md"
m6_handoff_decisions: "../milestones/INTEGRATION-DECISIONS.md"
progress:
  m_k0_total: 28
  m_k0_done: 28         # ✅ закрыт SUMMARY 2026-05-25
  m_k1_total: 17        # пересмотрен (было 9 — изменилось при детализации)
  m_k1_done: 15         # +SUMMARY (M-K1.17). 2 deferred (1.9, 1.16)
  m_k2_total: 13        # 11 content + smoke + SUMMARY
  m_k2_done: 12         # 11 content + SUMMARY done; M-K2.smoke deferred → M-K3.smoke
  m_k3_total: 16
  m_k3_done: 0
  m_k4_total: 10
  m_k4_done: 0
  m_k5_total: 10
  m_k5_done: 0
  m_k6_total: 7
  m_k6_done: 0
  knowledge_layer_total: 73  # 17 M-K1 + 13 M-K2 + 16 + 10 + 10 + 7
  stabilization_total: 28
  grand_total: 101           # 73 KL + 28 M-K0
  done: 55                   # 28 M-K0 + 15 M-K1 + 12 M-K2
  percent: 54
---

# STATE — Knowledge Layer + Stabilization

## Где мы сейчас

> ⚡ **АКТУАЛЬНО 2026-05-29 (сессия M-K3 graph/UC) — единый форвард-источник: [`../ROADMAP-2026-05-29.md`](../ROADMAP-2026-05-29.md).**
>
> M-K0 ✅ · M-K1 ✅ · M-K2 ✅ · **M-K2.5 ✅ ЗАВЕРШЁН (2026-06-01)** · **M-K3 🟡 ACTIVE**.
>
> **✅ 2026-06-02 — ГРУНТИНГ В ЧАТЕ ПОЛНОСТЬЮ РАБОТАЕТ (3/3 слоя верифицированы live, MiMo):**
> - **Граф ✅** — чат зовёт `trace_typical_movements` → 44 документа из графа (флагман-метрика).
> - **Карточки ✅** — `explain_typical_object` → полная карточка (реквизиты/движения/связи/сценарии).
> - **ИТС ✅ ПОЧИНЕНО** — был баг: чат использовал `MCPPool` (primary toolkit + aux **только** bsl-context), buddy туда вообще не подключался → `buddy.search_its` не доходил до LLM. Фикс: `BuddyAuxClient` (HTTP-aux с префиксом `buddy.` + #40-телеметрия) в `mcp_pool.py`, `build_aux_clients` теперь добавляет Напарника. Live: чат зовёт `buddy.search_its` → `buddy.fetch_its` → ответ с живыми ссылками `its.1c.ru` (телеметрия /health: calls_total>0, status up). 86 тестов затронутых областей зелёные.
> - **DB durability ✅** — `up.ps1` теперь ставит `DATABASE_URL → pilot.db` на каждый `/awd-dev-up` (раньше backend читал пустую `/data/app.db`). 4 конфига / 63 207 карточек отдаются. (`.env` мне недоступен по правам — durability через launch-скрипт.) Коммит `8cbd96c`.
>
> **✅ 2026-06-02 — USER-FACING СЛОЙ «3 ИСТОЧНИКА ЗНАНИЙ» (P0+P1+P2, frontend):**
> Проблема: пользователь не понимал, что за продукт, что работает и как пользоваться — гайд/онбординг описывали старый MCP-toolkit, ИТС/типовые были невидимы, бейдж «ИТС 0» врал при живом Напарнике, `/status` про buddy/типовую не знал. Введена единая модель **Ваша база / Типовая / ИТС·Напарник**, повторённая в 5 местах.
> - **P0 честный статус:** бейдж шапки «ИТС 0·БСП 0» → «●●● Источники» (live-статус, попап, ссылки); секция «Источники знаний» на `/status`; хук `useSourcesStatus`; `BuddyHealth` в `/health` тип фронта.
> - **P1 discoverability/freshness:** чипы пустого экрана сгруппированы по источникам + «Как это работает →»; 2 новых раздела гайда (Типовые конфигурации, ИТС и Напарник — с честным предупреждением о латентности 1–3 мин); блок «Что я умею» в онбординге; убран дрейф моделей (DeepSeek V4 Flash → модель-агностично).
> - **P2 in-context:** ярлык-источник под ответом (`AnswerSources` — **реализует G0.2 «метка источника»**) по именам вызванных tools; пояснение в селекторе «Типовая».
> - **Проверка:** `next build` зелёный, 11 unit-тестов, live в Chrome (бейдж/статус/пустой экран/гайд/ярлыки). Коммит (frontend, 15 файлов).
>
> **✅ 2026-06-02/03 — РЕДИЗАЙН «Дизайн-система 2.0» по ТЗ (`.planning/redesign-2026-06-02/`):**
> 12 находок аудита (F-01..F-12) → 4 спринта. Сделано (ветка `feature/m-k3-relational-cfe`):
> - **Спринт 1** ✅: дизайн-токены 2.0 (тёплая палитра, текст 3 ступени, семантика без неона, light-акцент #e8551f, мёртвые темы удалены) · голос «вы» + глоссарий (канал→база, обучение→память, backend→сервис) · единый `Alert` (emoji ⚠ убран, 5 систем ошибок → одна) · композер (счётчик токенов→полоса, hint /·@) · трейс без «радуги» (ok/error).
> - **Спринт 2** ✅: **«Грунт ответа»** (`AnswerProvenance` — провенанс первым классом, «показать» → реальные запросы к источнику; критичный F-02) · лицо ответа (аватар-глиф/время/длительность/копировать) · карточка-результат (один заголовок, усечение-чип, зебра).
> - **Спринт 3** ✅: шапка (3 иконки справки → меню `?` с подписями) · единый источник примеров (`EXAMPLE_PROMPTS`) · eyebrow-трекинг 0.18→0.1em.
> - **Спринт 4** 🟡: сайдбар-поиск ✅ · онбординг — экран ценности перед настройкой ✅.
> - **Проверка:** `next build` зелёный, **395 frontend-тестов зелёные**, обе темы (dark `rgb(12,13,16)` / light `rgb(241,239,232)`), live в Chrome.
> - **✅ РЕДИЗАЙН ПОЛНОСТЬЮ ЗАВЕРШЁН (2026-06-03):** все 12 находок + все carryover'ы.
>   Спринты 1-4 done. Carryover закрыт: ✅ «Повторить ответ» · ✅ переименование чатов
>   (inline-edit) · ✅ свёрнутый-сайдбар-иконки · ✅ F-07 развилка ролей (value→role→steps,
>   «настроил ИТ» → финал) · ✅ закрепление чатов (миграция v23 `pinned` + sort + UI,
>   smoke на pilot.db) · ✅ F-05 (декор-оранжевого нет, удовлетворён токенами) ·
>   ✅ a11y (клавиатурные заголовки таблицы + aria/focus новых компонентов).
>   **Итог:** `next build`/`tsc` чисты, **395 frontend + сессионные backend-тесты зелёные**,
>   live в обеих темах. Ветка `feature/m-k3-relational-cfe` — НЕ пушено (~20 коммитов).
> - **Грабли (зафиксировано):** `next build` НЕЛЬЗЯ запускать при живом `next dev` — делят `.next`, dev-сервер падает в 500. Верификация — `tsc --noEmit` + `vitest` (не трогают `.next`).
>
> **▶ НАПРАВЛЕНИЕ:** редизайн по ТЗ (см. выше) почти закрыт. Дальше: carryover'ы
> редизайна (опц.) · релизный гейт (golden-set G1 + слепой тест G3 — нужен пользователь).
>
> **✅ РЕДИЗАЙН ОБОЛОЧКИ shell v3 (2026-06-03, ТЗ `ТЗ-Redesign-Shell-v3.md`, ветка `feature/m-k3-relational-cfe`):**
> Перекомпоновка хедера в 3 зоны + единый статус. 7 коммитов (3c7e46f..7ef2727):
> - **§1 Header** → flex 3 зоны: [toggle+бренд+ChannelSelector+TypicalSelector] | spacer
>   | [Search ⌘K · StatusCapsule · OverflowMenu]. Центральная «свалка справа» убрана.
> - **§2 StatusCapsule** (новый): капсула (агрег.точка+модель+латентность) → поповер
>   База 1С/Модель/Анонимизация. Поглотил ModelBadge+AnonymizationStatus+KnowledgeBadge.
> - **§3 OverflowMenu «⋯»** (новый): подписанные пункты (тема/диагностика/гайд/навыки/
>   память/о приложении/настройки). Поглотил HelpMenu+ThemeToggle+Settings.
> - **§4 ChannelSelector** влево: min-w-320 убран, EnvBadge (ПРОД/ТЕСТ/ДЕМО) в чипе+dropdown.
> - **§5 environment** (Вариант B — localStorage, backend не отличает prod/test): тип +
>   get/setConnectionEnvironment + select в форме. **§6** окружение в welcome eyebrow.
> - **§7 InspectorDrawer** (новый): drawer объекта справа (radix Dialog, slide+Esc+focus-trap),
>   открытие событийно (window `open-inspector`, не prop-drill). §8 onOpenCmdK проброшен.
> - **Решения (флаги):** TypicalSelector сохранён в Зоне 1 (ТЗ опускал); быстрый свитч
>   модели из шапки убран (модель read-only в капсуле, смена в Настройках) — следствие §2.
> - **Проверка:** 404 frontend-теста зелёные, tsc baseline (5 пре-существующих, 0 новых),
>   live Chrome обе темы: Header/StatusCapsule/OverflowMenu/EnvBadge ПРОД/InspectorDrawer.
>   design-v2.spec.ts переписан под новую раскладку (Playwright не прогонялся — нет dev-stack).
>
> **✅ BUG-FIX СЕССИЯ 2026-06-03 (ветка `feature/m-k3-relational-cfe`):**
> - **✅ `@`-mention ПОЧИНЕН** (`d062a42`): корень — `metadata_suggest` звал
>   `bulk_refresh_metadata_cache` с `get_metadata({"detail":False})` = summary-режим
>   (типы+счётчики), парсер не извлекал имён → 0 строк в кэш, popover всегда пуст.
>   Фикс: `live_metadata_suggest(meta_type="*", name_mask=q)` — нативный 1C
>   substring-поиск (для 20 653 объектов точнее балк-кэша), + парсер ПолноеИмя/
>   Синоним/data-обёртка, + route live-first с warm-кэшем (повтор 0.47с→0.017с).
>   Verified live в Chrome: `@Номе` → 6 объектов. Чинит и prefetch при отправке
>   `@Тип.Имя` (get_dossier читает подогретый кэш). 175 тестов зелёные.
> - **✅ ИТС-латентность ПОЧИНЕНА** (`0e2d3fe`): кэш buddy.search_its/fetch_its
>   (CACHEABLE_TOOLS, TTL 2мин) + лимит `MAX_BUDDY_CALLS_PER_TURN=3` в loop.py +
>   промпт-нудж «Напарник медленный, 1 точный search достаточно». 330 тестов зелёные.
> - **✅ КА Демо :6012** — решение владельца (2026-06-03): **оставить как есть**
>   (не удалять демо-подключение; «1 из 2» на /status — ожидаемо).
> - **✅ Тех-долг частично:** F841 в loop.py убран; cp1251-flaky — системный фикс
>   (conftest форсит UTF-8 stdout/stderr ДО тестов). E501 в loop.py (17 шт) — ВСЕ
>   внутри `SYSTEM_PROMPT` (русская проза, line-length 120): не реклоучу (порча
>   промпта), не код-долг. MetricCard→CardHeader / SMOKE-NIM-REBUILD.md — отложены.
>
> **🐞 ОСТАЛОСЬ В БЭКЛОГЕ:**
> - **`.claude/CLAUDE.md` snapshot (2026-05-30)** устарел — правка заблокирована
>   auto-mode (agent config), нужен ручной апдейт пользователя (текст замены — в чате).
> - **Гигиена релиза:** git-тег v1.5.0 не ставился (smoke VM + cert pending),
>   3 Playwright spec не прогнаны.
> - **Тех-долг (опц.):** MetricCard→CardHeader (1/6 cards refactor), I001 import-sort
>   в loop.py (pre-existing), UP017 datetime в indexer.py (pre-existing).
>
> **✅ M-K2.5 — РЕБИЛД КАРТОЧЕК ЗАВЕРШЁН (2026-06-01):**
> - **63 207 карточек, 100% `is_mock=0`** по 4 каналам (БП 3.0 11 713 / УТ 11.5 11 783 / КА 2.5 19 685 / ЕРП 2.5 20 026).
> - **Качество: 99.9% score 5.0** (структурный аудит `audit_cards.py`); остаток 62 (0.1%) — мелкие огрехи отдельных карточек, без галлюцинаций. Остановлено по правилу 3 итераций (дальше — whack-a-mole).
> - Слои генерации: NIM qwen3.5-122b (основная масса) + Claude Haiku (часть erp25) + **Claude Sonnet** (231 упрямых + полировка 2175 карточек <4.5 до 5.0).
> - Аудит сделан **kind-aware** (graph-aware): не штрафует корректные карточки объектов без реквизитов/сценариев → метрика честная, не подогнана.
> - Инструментарий закоммичен `8bf1c5c` (push'нут). `pilot.db` — на диске (gitignored).
> - **🔓 СНЯТ ГЛАВНЫЙ БЛОКЕР:** `pilot.db` больше НЕ залочена NIM — свободна для пост-NIM пересборки графов (следующий шаг M-K3).
>
> **Сделано в M-K3 (ветка `feature/m-k3-relational-cfe`, в remote НЕ запушено):**
> - **17.1 L2-граф** ✅ верифицирован на реальной УТ 11.5 (62.7K nodes / 69.4K edges) + **перф-фикс traversal 384→30мс** (visited-set BFS вместо CTE, `d7fce26`).
> - **17.4 цепочка вызовов / 17.5 impact** ✅ — tools `trace_typical_calls` (out/in) уже были, **проверены на реальной УТ** (`e242246`).
> - **17.7 GraphCard** ✅ **E2E**: `get_subgraph` (`75c2f5e`) + REST `/knowledge/{ch}/graph/{qname}` (`864d579`) + React Flow GraphCard (`e66f9fa`) + backend-эмит из trace_typical_calls (`4f75ca2`).
> - **17.2 RLS-tracer** ✅ **end-to-end на типовых**: R1 `parse_rights_xml` (`fce67e3`) → R2 граф Phase E (521 роль / 2103 RESTRICTS-ребра на УТ, `3ad30b5`) → R3 LLM-tool `explain_rls_restrictions` (`c86f1e2`).
> - Аванс M-K4 (hybrid retrieval + guardrails G2) ✅ закоммичен, на паузе до углубления L4.
> - Гигиена: единый `ROADMAP-2026-05-29` + Workflow xlsx (`bc35cd8`), 3 STATE синхронизированы (`60e1e44`), CHANGELOG секция KL по стандарту.
>
> **🔀 АРХИТЕКТУРНЫЙ ПИВОТ 2026-05-29 (обсуждение с Никитой):**
> - **Граф = backend grounding-индекс по ТИПОВЫМ конфам.** Не user-facing «фича с картинкой», а подложка знаний (структурный близнец NIM-карточек: NIM=семантика «что это», граф=структура «что что вызывает»). LLM грунтует структурные ответы (цепочки/impact/RLS) текстом/таблицами.
> - **GraphCard визуал — ЗАМОРОЖЕН** (решение «только backend, без картинки»). Редизайн откатан, dev-роут удалён. Emit graph-card в `loop.py` — отключить при рефакторинге grounding (pending).
> - **#30 build_live_graph — ОТМЕНЁН.** Код клиента НЕ берём (приватность + MCP не отдаёт BSL-исходник). Источник графа = наши выгрузки типовых.
> - **Сейчас:** сборка graph-index по 4 конфам (УТ 11.5 / ERP 2.5 / КА 2.5 / БП 3.0) в `data/graph-index/` (фон `bkq2yte8t`, NIM-safe). Прод-консолидация в `pilot.db` (1 БД / 4 channel_id) — ПОСЛЕ NIM.
> - Дальше по UC: 17.3 report-tracer, 17.6 query-opt — как backend grounding (без обязательной картинки). RLS — таблица с условием, не граф.

> **✅ ВАЛИДАЦИЯ ТОЧНОСТИ ГРАФА 2026-05-30 (сессия после пивота) — все 4 киллер-UC доказаны на УТ ground-truth vs исходник:**
> - **Цепочка вызовов / impact** ✅ — cross-module CALLS был сломан (28% → 100%): фикс резолва CommonModule (`cefeb41`) + менеджеров Документы/Регистры.X.Метод (`86bfa77`). impact: 46 документов на общий метод проведения. CALLS 480K→704K. Tool-layer proof + регрессия (`32bb949`).
> - **READS_FROM** ✅ — 3/3 ground-truth (ТоварыНаСкладах), 5250 методов / 1312 объектов, physical+virtual. Зрелый query-парсер, не трогался.
> - **Движения (WRITES_TO)** ✅ — было: флагман ТоварыНаСкладах = 0 писателей (BSL `Движения.X` ловил лишь легаси direct-add). Решение (ресёрч): метаданные `<RegisterRecords>` документа. Phase F `_build_register_records_edges`. WRITES_TO 94→2485; ТоварыНаСкладах 0→44 документа (`afd3fbd`).
> - **RLS per-right** ✅ — было: 419 пар (35%) с разными условиями Read/Update схлопывались (дедуп insert_edge). Решение: список `[{right,condition}]` в ребре. Объектный резолв был 100% (1188 пар). (`afd3fbd`)
> - **Граф достоверен для grounding по ВСЕМ киллер-UC.** UC-traverse (CALLS depth=4) = 222ms.
> - **✅ ПЕРЕСБОРКА ГРАФОВ В `pilot.db` ЗАВЕРШЕНА (2026-06-01)** — все 4 канала с фиксами (CALLS cross-module + Phase F движения + RLS-v2 per-right). Процедура: `wipe_channel_graph.py` (обязательный per-channel wipe, билдер сам не чистит) → `typical_graph_pilot.py`. Валидация: WRITES_TO ut115 2485 / erp25 8602 / ka2 7672 / bp30 2969 (везде ≠0); RLS 1188/3808/3845/1888. Карточки забэкаплены (`pilot_cards_backup_2026-06-01.db`).
> - **✅ GROUNDING СВЕДЁН (2026-06-01):** живой чат `loop.py` уже импортирует typical-инструменты (list/search/explain/trace_calls/trace_movements/compare) — wire был на месте. Доделано:
>   - **read-path фикс** `card_context.py`: движения уровня объекта (Phase F) теперь в `writes_to` (демо: Реализация 1→44). Демо end-to-end на 2 конфигах (УТ продажи / ЕРП кадры), 5 типов вопросов — `scripts/demo_grounding.py`.
>   - **#38 закрыт:** системный промпт — гайд по qname метода + «не молчать до лимита, отвечать по фактам»; убран устаревший каркас «is_mock=true» (карточки реальны); правило «числа из графа, не из прозы карточки». `grounding.py` MAX_ROUNDS 6→10 (живой чат уже 100). Тесты 57/57.
>   - **#39 golden-set:** каркас `phases/M-K3/GOLDEN-SET.md` засеян 8 проверенными эталонами (S1–S8, вкл. 2 G0-ловушки).
> - **✅ LIVE-ПРОГОН НА PILOT.DB ЧЕРЕЗ MiMo (2026-06-01)** — `grounding_harness.py` (GROUNDING_DB=pilot.db, ключ через env). Все 3 киллер-UC зелёные на реальном LLM + прод-данных:
>   - Движения: ТоварыНаСкладах → 44 документа (таблица, с пруфом trace_typical_movements);
>   - **Цепочка/impact (#38 — был «молчит до лимита») ЗАКРЫТ ВЖИВУЮ:** ИИ навигировал ObjectModule.ОбработкаПроведения → CommonModule.ПроведениеДокументов (in), дал impact 50+ док, без зацикливания;
>   - RLS: ВнешниеПользователи → роль БСП + Read/Update условия + честная G0-оговорка «для юзера нужен MCP».
>   - Гейты: G2 grounding ✓ на 3/3 UC; G0 честность ✓ (граф vs живая база разграничены); галлюцинаций 0.
> - **🟡 ОСТАЛОСЬ ВЛАДЕЛЬЦУ (приёмка):** наполнить golden-set #39 реальными вопросами из практики (15–20; засеяно 8 эталонов S1–S8, теперь и LIVE-подтверждены) → прогнать гейты G0–G3 на полном наборе для формальной приёмки «Объяснителя».
>
> **✅ #40 — 1c-buddy (живая ИТС L5) ВНЕДРЁН (2026-06-01):** buddy уже был включён (buddy_mcp_enabled=True, MCP :6002, промпт-приоритет). Доделано:
>   - **Healthcheck + circuit-breaker** (`buddy_monitor.py`): 30s ping, 3 фейла → degraded, статус в `/health.buddy` (фронт показывает предупреждение). 6 тестов. Коммит `2d1f3ba`.
>   - **Usage-телеметрия** (`_BuddyTelemetryClient` в mcp_factory): calls_total/ok/fail в `/health.buddy` — данные для lifecycle-решения. Коммит `e365b65`.
>   - **Autostart** — проверен: Startup-ярлык `1C Buddy.lnk` + `start-1c-buddy-silent.vbs` на месте (наст. 26.05), buddy :6002 жив (MCP `1C.ai Gateway MCP v1.0.0`).
>   - **🟡 lifecycle-решение** (платить Напарнику vs свой RAG к 01.10.2026) — за владельцем, теперь по факту использования (телеметрия), не вслепую.

**Active milestone (история до 2026-05-26):** ✅ **M-K2 Knowledge Foundation + Triple RAG — CLOSED SUMMARY 2026-05-26** (12/13 done + 1 deferred).

**Closed phases:** 2.1, 2.2, 2.3 (Incremental), 2.4 (MCP Cache), 2.5, 2.6, 2.7 (ИТС), 2.8 (БСП), 2.9, 2.10, 2.11 (Privacy badge), **2.SUMMARY**.  
**Deferred:** M-K2.smoke → M-K3.smoke (требует CI + live backend).

**Next milestone:** **M-K3 Relational + Behavioral** (16 phases planned).

**Predecessors closed:**
- ✅ M-K0 Stabilization (28/28) — SUMMARY 2026-05-25
- ✅ M-K1 Foundation (15/17, 2 deferred) — SUMMARY 2026-05-26

**M-K2 final session (2026-05-26):** закрыты 6 phases подряд в одной сессии:
M-K2.7 ИТС RAG (6 коммитов, +114 тестов, migration v14) → M-K2.8 БСП Pattern
Index (3 коммита, +75 тестов, migration v15) → M-K2.4 MCP Cache (+34 теста)
→ M-K2.3 Incremental refresh (+15 тестов) → M-K2.11 Privacy badge UI
(+17 vitest) → M-K2.SUMMARY.

## Подсказка для следующей сессии Claude

Открой `phases/M-K2/SUMMARY.md` для полного handoff'а в M-K3.

Backend tests: 1472. Frontend: 378. Coverage: ≥87%.
Branch: main.

**Следующая фаза: M-K3.1 TreeSitter BSL setup** — AST extractor для
Knowledge Graph (L2). См. ADR-002 для дизайн-решений по graph storage
(SQLite + CTE вместо Neo4j).

M-K3 milestone план — 16 phases, ~5-6 weeks. Стартовать с research
последних TreeSitter BSL grammar статей + Spike интеграции.

---

## Snapshot — что готово, что нет

### Готово (до старта M-K0)

- ✅ Глубокий research (deep-researcher агент)
- ✅ Inventory существующей инфраструктуры (general-purpose агент)
- ✅ Knowledge Layer Excel — 63 findings
- ✅ Общий audit Excel — 99 findings
- ✅ PLAN.md v1.1 — стратегия и roadmap (M-K0 → M-K6)
- ✅ Модель уровней L0-L6
- ✅ 25 killer use cases
- ✅ M-K0-PLAN.md — детальный план Stabilization (10 phases)
- ✅ M-K1-PLAN.md — детальный план Foundation (9 phases)
- ✅ CLAUDE-RESUME.md — operational protocol

### Не начато

- ⏸ M-K0 kickoff (ждём explicit approval от Никиты)
- ⏸ Branch `feature/m-k0-stabilization`
- ⏸ Все 10 phases M-K0

### Blocked

Ничего на сейчас.  
**Единственный блокер: explicit kickoff approval от Никиты.**

---

## Активный милстоун (M-K0) — раскладка

См. полный план: `phases/M-K0-stabilization/M-K0-PLAN.md`

| Phase | Wave | Subject | Findings | Est | Status |
|-------|------|---------|----------|-----|--------|
| M-K0.1 | 0 — Security | SEC-1..7, SEC-12 | 8 | 5d | pending |
| M-K0.2 | 1 — Backend | BE-1..6 | 6 | 4d | pending |
| M-K0.3 | 2 — Performance | PERF-1..3 | 3 | 3d | pending |
| M-K0.4 | 3 — Prompts | PROMPT-1..3 | 3 | 3d | pending |
| M-K0.5 | 4 — Frontend | FE-1, FE-3, FE-4 | 3 | 1.5d | pending |
| M-K0.6 | 5 — Architecture | ARCH-2 (только globals) | 1 | 2d | pending |
| M-K0.7 | 6 — Docs+DevOps | DOC-1/2, DEVOPS-1/5 | 4 | 2d | pending |
| M-K0.8 | — | Coverage push 60%+ real | — | 3d | pending |
| M-K0.9 | — | Security re-audit | — | 1d | pending |
| M-K0.10 | — | SUMMARY + handoff to M-K1 | — | 1d | pending |

**Итого:** ~25.5d + 5.5d буфер = ~31 рабочий день ≈ **3-4 календарных недели**  
с параллелизацией waves 0+1+4+6.

**Параллелизация:**
- Week 1: M-K0.1 (Security) + M-K0.2 (Backend) одновременно
- Week 2: M-K0.3 + M-K0.4 + M-K0.5 одновременно
- Week 3: M-K0.6 + M-K0.7 одновременно
- Week 3-4: M-K0.8 + M-K0.9 + M-K0.10

---

## Прогресс по милстоунам

```
M-K0 Stabilization          [          ]   0%   (0/28)   ← PENDING KICKOFF
M-K1 Foundation             [          ]   0%   (0/9)
M-K2 Knowledge Foundation   [          ]   0%   (0/11)
M-K3 Relational + Behav     [          ]   0%   (0/16)
M-K4 Normative + Hybrid     [          ]   0%   (0/10)
M-K5 Predictive (8.5-Ready) [          ]   0%   (0/10)
M-K6 Predictive++ Enterprise[          ]   0%   (0/7)
────────────────────────────────────────────────
TOTAL (Stab+KL)             [          ]   0%   (0/91)
```

## Календарный roadmap (после M-K0 kickoff)

```
2026-05-25  ─ план готов, ждём kickoff
2026-06-20  ─ M-K0 done (Stabilization)        ←  ВАЖНЫЙ MILESTONE
2026-07-05  ─ M-K1 done (Foundation + Quick Wins)
2026-08-05  ─ M-K2 done (Knowledge Foundation)
2026-09-20  ─ M-K3 done (Relational + Behavioral) → MVP «Объяснитель»
2026-10-25  ─ M-K4 done (Normative) → готовность к INFOSTART A&PM EVENT октябрь
2026-12-20  ─ M-K5 done (8.5-Ready Assessment) → revenue trigger
2027-02-28  ─ M-K6 done (Enterprise)
```

---

## Артефакты для kickoff M-K0

Перед стартом первой phase нужно:

1. **Approval Никиты** — «начинаем M-K0»
2. Создать branch `feature/m-k0-stabilization`
3. Создать `phases/M-K0-stabilization/STATE.md`
4. Запустить параллельно sub-branches:
   - `feature/m-k0-wave0-security`
   - `feature/m-k0-wave1-backend`
5. Прочитать `M-K0-PLAN.md` ещё раз и подтвердить acceptance criteria

После этого — M-K0.1 Security Wave 0 + M-K0.2 Backend Wave 1 параллельно.

---

## Что НЕ верифицировано (из основного проекта, релевантно нашему плану)

Из основного `STATE.md` основного проекта:
- ContextCompressor на длинном диалоге (>100k tokens)
- background_review с реальным aux LLM
- prompt_caching на Anthropic Claude

**При работе с Knowledge Layer (после M-K0) — тестировать end-to-end  
с реальным LLM, не только unit-тестами.**

---

## Что отложено в backlog (НЕ в M-K0)

Из 99 общих findings — в M-K0 закрываем 28, остальные **71** в backlog:

- MEDIUM/LOW backend (BE-7..12) — параллельно с M-K1..M-K6
- MEDIUM/LOW perf (PERF-4..12) — после Knowledge Layer
- MEDIUM/LOW prompts (PROMPT-4..15) — после Knowledge Layer integration
- Frontend MEDIUM/LOW (FE-5..11) — параллельно с UX задачами M-K3
- All Testing (QA-1..6) — параллельно
- All DevOps кроме DEVOPS-1/5 — после EV cert
- All Product/GTM — перед commerce launch M-K3
- All Compliance — closer to enterprise M-K6
- MEDIUM/LOW security (SEC-8..11, SEC-13) — параллельно по приоритету

Все в Excel `План_развития_1С_Аналитик_2026-05-24.xlsx` с пустой колонкой  
«Комментарий пользователя» для приоритезации.

---

## История изменений STATE

- **2026-05-25**: Добавлен M-K0 Stabilization как первый милстоун. Active  
  переключён с M-K1 на M-K0. Прогресс-бары и календарь обновлены.
- **2026-05-25**: Создан STATE.md, план составлен, ждём kickoff M-K1.
