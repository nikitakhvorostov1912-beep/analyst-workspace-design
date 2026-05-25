# M-K4 — Visual + Activity Stream + Reasoning

**Milestone:** M-K4
**Срок:** 6-8 недель (включая MetaVision Spike), до **15.12.2026**
**Parent plan:** `../../PLAN.md` v1.2
**Branch:** `feature/m-k4-visual-activity` (создаётся при kickoff)

## Зафиксированные решения

- **Q4 MetaVision**: Spike 3 дня в Phase 16.0 → go/no-go gate
- **G8 Activity Stream связан с L4**: Activity Stream → Posting Trace → «почему
  этот документ записался?» reasoning

## Цель милстоуна

Доставить **визуальный analyst experience** через MetaVisionGraph + Activity
Stream sidebar + DiagnoseCard + L4 behavioral reasoning. Top-3 use cases:
- Deadlock-tracer (L4-4)
- «Почему документ так записался?» (L4-1 reasoning + Posting Trace)
- Compliance check (L5-4)

## Definition of Done всего милстоуна

- [ ] MetaVision Spike (Phase 16.0) завершён с go/no-go decision
- [ ] Если go — MetaVisionGraph card работает на 1+ типовой
- [ ] Если no-go — наш GraphCard (M-K3) используется как primary visualization
- [ ] Activity Stream sidebar показывает real-time events из CFE
- [ ] Posting Trace card отображается при просмотре документа
- [ ] L4 reasoning отвечает «почему документ записался» с подсчётом движений
- [ ] L5-4 Compliance check работает на основе rulebook YAML
- [ ] OPS-2 Telemetry собирает метрики retrieval source (для Q-NEW R-01 решения)
- [ ] BSL LS streaming (если cycle позволит) — bonus enhancement
- [ ] `phases/M-K4/SUMMARY.md` написан

## Phases внутри M-K4

```
Phase 16.0 — MetaVision Spike (3 days, hard gate)        [3.0d]  pending  (G6 + Q4)
  Decision gate:
    - GO  → Phase 16.1-16.5 full integration (17-25 дней)
    - NO-GO → Phase 16.1' lightweight (8-10 дней, наш граф primary)

Phase 16.1 — MetaVision CLI fork (GO path)              [5.0d]  pending
Phase 16.2 — Java subprocess wrapper                    [2.0d]  pending
Phase 16.3 — MetaVisionGraph card + D3.js               [4.0d]  pending
Phase 16.4 — Integration с нашим L2 graph              [2.0d]  pending
Phase 16.5 — Bundle MetaVision в Electron              [2.0d]  pending
                                                        ───
                                                        15d (GO path)

Phase 16.1' — наш граф как primary (NO-GO path)         [3.0d]  pending
Phase 16.2' — кнопка «Открыть в MetaVision desktop»     [1.0d]  pending
Phase 16.3' — улучшение GraphCard (M-K3 17.7)           [2.0d]  pending
                                                        ───
                                                        6d (NO-GO path)

Phase 16.A — Activity Stream sidebar (10 дней)
16.A.1 Backend SSE endpoint для CFE events             [2.0d]  pending
16.A.2 Frontend sidebar component                      [3.0d]  pending
16.A.3 Event aggregation (debounce, batching)          [1.0d]  pending
16.A.4 TimelineCard render                             [2.0d]  pending
16.A.5 Smoke на CFE с реальными events                 [2.0d]  pending

Phase 16.B — Posting Trace (8 дней, G8)
16.B.1 CFE подписка ПередЗаписью документов            [2.0d]  pending
16.B.2 Trace storage в knowledge.db                    [1.0d]  pending
16.B.3 PostingTrace card                               [2.0d]  pending
16.B.4 Связь с L4 «почему документ записался»          [3.0d]  pending

Phase 17.A — L4 Behavioral Reasoning (12 дней)
17.A.1 Diagnose Engine YAML rulebook                   [3.0d]  pending
17.A.2 Hypothesis reasoning chain                      [3.0d]  pending
17.A.3 Deadlock-tracer L4-4                            [2.0d]  pending
17.A.4 Compliance check L5-4                           [2.0d]  pending
17.A.5 Refactor planner L5-5                           [2.0d]  pending

OPS-2 — Telemetry для build vs buy решения (3 дня, R-01)
OPS-2.1 Retrieval source metric                        [1.0d]  pending
OPS-2.2 Hit rate per source                            [1.0d]  pending
OPS-2.3 Dashboard (sqlite + sparkline)                 [1.0d]  pending

Phase 15.A — BSL LS streaming (5 дней, optional)
15.A.1 WebSocket endpoint для diagnostics              [2.0d]  pending
15.A.2 Frontend live highlighting                      [2.0d]  pending
15.A.3 Debounce 500ms                                  [1.0d]  pending
(если cycle позволит — иначе пропускаем)

M-K4.99 SUMMARY + handoff to M-K5                       [1.0d]  pending
                                                        ───
                                                        ~42-55d (6-8 weeks)
```

## Decisions / Risks

### G6 (MetaVision) — Phase 16.0 Spike
**Acceptance criterion для go:**
- PoC CLI runs `metavision analyze project.cf --json` без X11/Swing
- Output: valid JSON с nodes/edges
- Время на конфигурацию УТ 11.5 ≤ 60 sec

**Если не получается за 3 дня (no-go):**
- Phase 16 сокращается с 15d до 6d
- Наш GraphCard (M-K3 17.7) становится primary
- M-K4 общий срок: ~33d (~5 нед) вместо 42-55d

### G8 (Activity Stream + L4 связь)
Phase 16.B.4 явно связывает Posting Trace с L4 reasoning:
- Activity Stream показывает «факт» (документ записан с движениями X, Y, Z)
- L4 объясняет «почему» (rulebook + цепочка причин)

### R-02 (MetaVision Spike risk)
Hard timebox 3 дня + jump на fallback план без обсуждения.

### R-01 (Напарник lifecycle)
OPS-2 Telemetry собирает данные за 2-3 месяца до 01.10.2026 deadline для
build vs buy решения в M-K5.

## Cards registry — добавляются в M-K4

| Card | Phase | Notes |
|---|---|---|
| TimelineCard | 16.A.4 | Activity Stream events |
| PostingTrace | 16.B.3 | Per-document trace |
| DiagnoseCard | 17.A.1 | Diagnose Engine output |
| ProcessCard | 17.A.2 | Hypothesis chain |
| Metrics | OPS-2.3 | Telemetry dashboard |
| StandardsCitation, ITSArticle, BSPMethod, PlatformHelp | M-K3 17.7 ref | L5 source citation |

## Готовые ресурсы

- MetaVision: `tools/MetaVision/` (есть, GUI-only)
- L4 rulebook template: будет создан в M-K3 17.7 как stub
- v8std для citations: `tools/v8std/`
- БСП исходники для compliance check: `tools/ssl_3_2/src/`

## SUMMARY скелет

См. `../M-K0-stabilization/SUMMARY.md` образец format.
