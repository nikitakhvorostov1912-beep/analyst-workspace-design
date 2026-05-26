---
plan_version: 1.3
milestone: M-K1
milestone_name: "Foundation — capability-aware multi-MCP shell"
status: complete  # M-K1 закрыт SUMMARY 2026-05-26, готов handoff в M-K2
last_updated: "2026-05-26T09:00:00Z"
m6_handoff_integrated: true
m6_handoff_doc: "../milestones/M6-INTEGRATED-PLAN.md"
m6_handoff_decisions: "../milestones/INTEGRATION-DECISIONS.md"
progress:
  m_k0_total: 28
  m_k0_done: 28         # ✅ закрыт SUMMARY 2026-05-25
  m_k1_total: 17        # пересмотрен (было 9 — изменилось при детализации)
  m_k1_done: 15         # +SUMMARY (M-K1.17). 2 deferred (1.9, 1.16)
  m_k2_total: 11
  m_k2_done: 0
  m_k3_total: 16
  m_k3_done: 0
  m_k4_total: 10
  m_k4_done: 0
  m_k5_total: 10
  m_k5_done: 0
  m_k6_total: 7
  m_k6_done: 0
  knowledge_layer_total: 71  # пересмотрено: 17 M-K1 (было 9) + 11 + 16 + 10 + 10 + 7
  stabilization_total: 28
  grand_total: 99            # 71 KL + 28 M-K0
  done: 43                   # 28 M-K0 + 15 M-K1
  percent: 43
---

# STATE — Knowledge Layer + Stabilization

## Где мы сейчас

**Active milestone:** **M-K2 Knowledge Foundation + Triple RAG** (kickoff pending).

**Predecessors closed:**
- ✅ M-K0 Stabilization (28/28) — SUMMARY 2026-05-25
- ✅ M-K1 Foundation (15/17, 2 deferred) — SUMMARY 2026-05-26

**Last update:** 2026-05-26 — M-K1 закрыт, готов handoff в M-K2.

## Подсказка для следующей сессии Claude

Открой `CLAUDE-RESUME.md`. Дальше — `phases/M-K2/M-K2-PLAN.md`  
для wave'ов M-K2 (indexer + Triple RAG + DDL v12 если потребуется).

Перед стартом M-K2 — прочитать `phases/M-K1/SUMMARY.md` (handoff section)
+ `phases/M-K2/M-K2-PLAN.md` если уже создан.

Backend tests: 1121 passed. Frontend: 345 passed. Coverage: 87.3%.
Branch: main (последний коммит после M-K1.17 SUMMARY).

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
