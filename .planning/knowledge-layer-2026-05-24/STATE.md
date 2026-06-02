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
