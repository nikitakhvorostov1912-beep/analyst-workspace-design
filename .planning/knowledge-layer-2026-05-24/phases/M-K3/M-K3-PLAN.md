# M-K3 — Relational + Behavioral + EPF/CFE Delivery

**Milestone:** M-K3
**Срок:** 8-10 недель (расширено M6 handoff + Q2 5 типовых), до **30.10.2026**
**Parent plan:** `../../PLAN.md` v1.2
**Integrated plan:** `../../../milestones/M6-INTEGRATED-PLAN.md`
**Branch:** `feature/m-k3-relational-cfe` (создаётся при kickoff)

## Зафиксированные решения пользователя

- **Q1 CFE именование**: подсистема `АналитикПлюс` + префикс `АП_` для критичных
  (общих модулей)
- **Q2 типовые**: УТ + ERP + КА + БГУ + ЗУП (5 на БСП 3.1+) → +2 нед vs исходного
- **Q3 EPF first**: Phase 13a (EPF) до Phase 13b (CFE)
- **Q5 BSL LS scope** (G5): **detector first** (M-K3.5), **streaming в M-K4**
  как отдельный enhancement — не блокирует EPF/CFE delivery

## Цель милстоуна

Доставить **EPF `АналитикLite.epf`** и **CFE `АналитикПлюс.cfe`** с capability
discovery, RLS-tracer, Knowledge Graph (TreeSitter+SQLite+CTE), BSL LS antipattern
detector, и top-5 use cases (RLS-tracer, report-tracer, цепочка вызовов, impact
analysis, query optimizer).

## Definition of Done всего милстоуна

- [ ] `АналитикLite.epf` (~3 MB) собирается через `epf-build` и работает на УТ 11.5
- [ ] `АналитикПлюс.cfe` (~8 MB) собирается через `cfe-validate` и применяется на УТ/ERP/КА/БГУ/ЗУП
- [ ] Capability response (ADR-004) возвращает реальный список features per канал
- [ ] Knowledge Graph для типовой УТ: ~5K nodes, ~50K edges, traversal 5 levels ≤ 300ms
- [ ] BSL Parser TreeSitter работает на 95% реального кода БСП 3.1.10
- [ ] Antipattern Detector ловит A1-A11 (см. `rules/1c/1c-anti-patterns.md`)
- [ ] Topp-5 use cases работают в chat за ≤ 8 сек cold
- [ ] Onboarding step 1.5 (выбор EPF/CFE) live
- [ ] Migration EPF→CFE не теряет историю сессий
- [ ] PowerShell installer для CFE подписан (или явное self-signed README)
- [ ] `phases/M-K3/SUMMARY.md` написан

## Phases внутри M-K3

```
Phase 13a — EPF Delivery (10-14 дней)
13a.0 EPF skeleton + epf-init                  [0.5d]  pending
13a.1 АналитикLite manifest + manifest.json    [0.5d]  pending
13a.2 Capability response в EPF (8 base caps)  [1.5d]  pending  (ADR-004)
13a.3 Общие модули АП_* (HMAC, Capability)     [2.0d]  pending  (Q1)
13a.4 HTTP service EPF (port 6011) + initialize [2.0d] pending
13a.5 Onboarding step 1.5: «Скачать EPF»       [1.0d]  pending
13a.6 Smoke EPF на УТ 11.5                     [1.0d]  pending
13a.7 Smoke EPF на ERP 2.5                     [0.5d]  pending
13a.8 Smoke EPF на КА 2.5                      [0.5d]  pending
13a.9 EPF installer (PowerShell + manual)      [1.0d]  pending
13a.10 EPF release notes                       [0.5d]  pending
                                                ───
                                                10.5d

Phase 13b — CFE Delivery (15-21 день + 2 нед БГУ/ЗУП)
13b.0 feature-detection per configuration       [0.5d]  pending  (R-04 mitigation)
13b.1.1 CFE skeleton + cfe-init                 [0.5d]  pending
13b.1.2 Подсистема АналитикПлюс                 [0.5d]  pending  (Q1)
13b.1.3 Заимствование 3 общих модулей          [1.0d]  pending
13b.2 Activity Stream подписки                  [2.0d]  pending  → M-K4 visualization
13b.3 Posting Trace на ПередЗаписью документов  [2.0d]  pending  → M-K4 visualization
13b.4 BSL LS diagnostics через CFE              [3.0d]  pending  (G5: detector mode)
13b.4.1 HMAC SSO между EPF и CFE                [1.0d]  pending
13b.5 Capability response extended (23 caps)    [1.0d]  pending  (ADR-004 full)
13b.5.1 Migration EPF→CFE (preserve sessions)   [1.5d]  pending
13b.5.2 Smoke на 5 типовых (Q2)                 [3.0d]  pending  (УТ/ERP/КА/БГУ/ЗУП)
13b.6 CFE installer + PowerShell signed         [1.5d]  pending  (DEVOPS-1 cert)
                                                ───
                                                17.5d

Phase 15 — BSL LS Detector (5 дней, G5 resolved as detector)
15.1 BSL LS jar download (or bundle) + JRE      [1.0d]  pending  (R-05 mitigation)
15.2 Backend subprocess wrapper                 [1.0d]  pending
15.3 Antipattern Detector pipeline              [1.0d]  pending
15.4 A1-A11 rules adapter                       [1.0d]  pending
15.5 BSLDiagnostics card в chat                 [1.0d]  pending
(WebSocket streaming — deferred to M-K4 if cycle позволит)

Phase 17 — Top-5 Use Cases (15 дней)
17.1 Knowledge Graph: TreeSitter+SQLite+CTE     [3.0d]  pending  (ADR-002)
17.2 RLS-tracer use case                        [2.0d]  pending
17.3 Report-tracer use case                     [2.0d]  pending
17.4 Цепочка вызовов use case                   [2.0d]  pending
17.5 Impact analysis use case                   [2.0d]  pending
17.6 Query optimizer use case                   [2.0d]  pending
17.7 GraphCard (React Flow) + DiagnoseCard      [2.0d]  pending  (G11 cards registry)
                                                ───
                                                15.0d

M-K3.99 SUMMARY + handoff to M-K4               [1.0d]  pending
                                                ───
                                                ~48d total (~8-10 weeks)
```

## Decisions / Risks этого milestone

### G4 (.hbk fallback) — закрыт в M-K2.4
Решение: spike 3 дня в M-K2.4. Если не получится → fallback на v8std + БСП.
Это **не блокирует** M-K3 (L4 reasoning использует L2 graph + L3 patterns).

### G5 (BSL LS scope) — решён как **detector first**
- M-K3 Phase 15: **detector mode** (after-the-fact, через subprocess)
- M-K4 (если cycle позволит): WebSocket streaming как enhancement
- Обоснование: detector закрывает 80% UX value (analyst видит warning после
  генерации). Streaming дает «live» feedback но 5x scope (10 vs 2 дней).
  Решение пересмотреть если в M-K3 detector окажется недостаточно.

### G6 (MetaVision) — Spike в M-K4 Phase 16.0
Не блокирует M-K3 — наш граф (Phase 17.1 TreeSitter+SQLite+CTE) делается всегда.

### R-04 (БГУ/ЗУП конфликты)
Mitigation: Phase 13b.0 feature-detection per configuration. Smoke tests
разделены на 5 наборов в Phase 13b.5.2.

### R-05 (BSL LS bundle size)
Mitigation: Phase 15.1 — bundled JRE через `jlink` (~30-40 MB вместо 80) +
proguard для BSL LS jar (~50 MB вместо 113). Если installer > 200 MB →
download-on-demand (как BGE-M3 в ADR-003).

## Dependencies

```
M-K2 → 13a.0 → 13a.1 → 13a.2 (capability) → ...

13a.* (EPF done) → 13b.0 (feature-detect) → 13b.1.* → 13b.2/3/4
                                                          │
                              Phase 15 (BSL LS) ──────────┤
                                                          │
                              Phase 17 (Top-5 UC) ────────┤
                                                          │
                                              13b.5 → 13b.5.1/2 → 13b.6
                                                          │
                                                          M-K3.99 SUMMARY
```

## Cards registry (G11)

В Phase 17.7 создаётся `frontend/lib/card-registry.ts` с типизированным реестром
19 типов:

| Type | Source | Phase |
|---|---|---|
| table, object, log, metric, references, code | existing | — |
| GraphCard | L2 | 17.7 |
| DiagnoseCard | L4 (M-K4) | M-K4 |
| ComparisonCard | L5 | M-K5 |
| TimelineCard | Activity Stream | M-K4 |
| ProcessCard | L4 reasoning | M-K4 |
| BSLDiagnostics | Phase 15 | 15.5 |
| StandardsCitation, ITSArticle, BSPMethod, PlatformHelp | L5 | M-K4 |
| MetaVisionGraph | Phase 16 | M-K4 |
| Antipattern | Phase 15.4 | 15.5 |
| Metrics | OPS-2 | M-K4 |

## Готовые ресурсы (использовать)

- `tools/v8std/` — sfaqer 317 ИТС стандартов (Knowledge для L5)
- `tools/ssl_3_1/`, `tools/ssl_3_2/` — БСП исходники (Apache 2.0 атрибуция)
- `tools/OnesTemplates/` — BSL сниппеты по стандартам ИТС
- `tools/bsl-language-server-0.29.0-exec.jar` — для Phase 15
- Глобальные skills `cfe-*`, `epf-*`, `form-*` для генерации артефактов
- Метаданные tools — `bsl-context` MCP (бесплатно, без Java setup)

## Метрики Phase 17.1 Knowledge Graph

| Метрика | Target | Verify |
|---|---|---|
| Nodes для УТ 11.5 typical | ~5000 | smoke import + count |
| Edges | ~50000 | smoke import + count |
| Indexed traversal 5 levels | ≤ 100 ms | benchmark CTE query |
| BSL Parser coverage реального кода БСП 3.1 | ≥ 95% | parse +1000 файлов БСП |

## SUMMARY скелет (заполняется в конце)

См. `../M-K0-stabilization/SUMMARY.md` как образец format.

Обязательные секции:
- TL;DR (EPF + CFE доставлены, 5 типовых протестированы)
- Метрики Knowledge Graph + BSL LS coverage
- Все Phase 13a/13b/15/17 закрыты с commit hashes
- Pre-flight для M-K4 (M-K3 → M-K4 handoff items)
- Open risks (Activity Stream visualization в M-K4)
