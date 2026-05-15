---
phase: 04-demo-refine
plan: "02"
subsystem: advanced-cards
tags: [cards, prismjs, sparkline, bsl-grammar, metric, references, code]
dependency_graph:
  requires: [04-01]
  provides: [CARD-04, CARD-05, CARD-06]
  affects: [frontend/components/cards, frontend/lib, backend/orchestrator/cards]
tech_stack:
  added: [prismjs@1.30.0, @types/prismjs@1.26.6]
  patterns: [discriminated union cards, prism grammar, inline SVG sparkline, Cyrillic word boundary regex]
key_files:
  created:
    - backend/app/orchestrator/cards.py          # extended — SparklinePoint, MetricCardPayload, ReferenceGroup, CodeCardPayload + new builders
    - backend/tests/test_cards_advanced.py        # 34 new tests, cards.py coverage 87.8%
    - frontend/components/cards/Sparkline.tsx     # inline SVG sparkline ~65 lines
    - frontend/components/cards/MetricCard.tsx    # large value + label + delta + sparkline
    - frontend/components/cards/ReferencesCard.tsx # grouped by usage_kind + filter input
    - frontend/components/cards/CodeCard.tsx       # prismjs highlight + copy + result toggle
    - frontend/lib/bsl-grammar.ts                 # Prism grammar for BSL (Cyrillic word boundaries)
    - frontend/lib/highlight.ts                   # highlight() function wrapping prismjs
    - frontend/lib/highlight.test.ts              # 7 tests
    - frontend/app/prism.css                      # token colors for dark theme
  modified:
    - backend/app/orchestrator/loop.py            # extend _TOOL_FOR_CARD_TYPE for 3 new card types
    - backend/tests/test_orchestrator_cards.py    # update 2 tests for new behavior
    - frontend/lib/types.ts                       # add 6 new types + extend CardEnvelope union
    - frontend/components/cards/CardRenderer.tsx  # add cases for metric/references/code + sendMessage
    - frontend/components/chat/Markdown.tsx       # fenced bsl/sql/json blocks → CodeCard
    - frontend/app/layout.tsx                     # import prism.css
decisions:
  - "prismjs over shiki: ~10kb gzip vs WASM, simpler integration, no SSR issues"
  - "BSL grammar uses lookahead/lookbehind instead of \\b — Cyrillic chars not matched by \\w in JS"
  - "Sparkline pure SVG ~65 lines — no recharts/chart.js"
  - "_dispatch_query_card single function for metric/timeline/table dispatch — no separate builders"
  - "MetricCard false positive mitigation: ID-like column names excluded (id/ссылка/reference)"
  - "ReferencesCard group order: фиксированный порядок ['Реквизит', 'Подчинённый', 'Шаблон', 'Подписка', 'Право', 'Прочее']"
metrics:
  duration: "~45 minutes"
  completed: "2026-05-15"
  tasks_completed: 2
  tests_added: 34 backend + 33 frontend
  files_modified: 22
---

# Phase 4 Plan 2: Advanced Cards (CARD-04..06) Summary

Расширены inline cards с 3 до 6 типов: MetricCard (крупное число + sparkline), ReferencesCard (группы по usage_kind), CodeCard (prismjs highlight для BSL/SQL/JSON).

## What Was Built

### Backend (cards.py)

**Новые Pydantic-модели:**
- `SparklinePoint(label, value)` — точка спарклайна
- `MetricCardPayload(value, label, unit, sparkline, delta, card_id)`
- `ReferenceItem(object_type, name, navigation_link, full_path)`
- `ReferenceGroup(kind, items)`
- `ReferencesCardPayload(groups, total, card_id)`
- `CodeCardPayload(language, code, executable, result, card_id)`

**Новые builders:**

`_dispatch_query_card` — единая функция диспетчеризации для `execute_query`:
- Path A (single metric): 1 строка + numeric cols → MetricCard. Исключаются ID-like колонки (`id/ссылка/reference`).
- Path B (timeline): 1 < rows ≤ 100 + period column (`Период/Дата/Месяц/Date/Period`) + numeric → MetricCard со sparkline и delta. `delta.percent_value` не вычисляется если first=0 (zero-division safe).
- Fallback: TableCard (текущее поведение).

`_build_references_card` (переписан) — группировка по `usage_kind` с фиксированным порядком. Fallback для legacy `list[str]`. Возвращает None для пустого списка.

`_build_code_card` (новый) — для `execute_code` + `get_bsl_syntax_help`. Детектирует язык по эвристике (ВЫБРАТЬ→sql, Процедура/Функция→bsl, {→json). Усечение кода до 50k символов (T-04-12 DoS protection).

`_CARD_BUILDERS` расширен с 4 до 6 entries.

**loop.py:** `_TOOL_FOR_CARD_TYPE` расширен для metric/references/code card states.

### Frontend

**lib/bsl-grammar.ts** — Prism.js grammar для BSL:
- Ключевые слова, встроенные функции, строки, числа, комментарии
- Директивы (`&НаКлиенте`) и области (`#Область`)
- Использует lookahead/lookbehind вместо `\b` — JS `\b` не работает с кириллицей

**lib/highlight.ts** — `highlight(code, language)` — единственное место импорта prismjs. Fallback: `escapeHtml()` для `"text"` language.

**Sparkline.tsx** — inline SVG ~65 строк. Нет зависимостей кроме React. Fill area + polyline. aria-label с min/max.

**MetricCard.tsx** — value (Intl.NumberFormat ru-RU), label, unit, delta (ArrowUp/Down + emerald/rose), Sparkline.

**ReferencesCard.tsx** — группы с иконками по kind, collapsible (первые 2 открыты), filter input с debounce-like (controlled state), clickable items → onLinkClick.

**CodeCard.tsx** — language badge, copy button, code с `dangerouslySetInnerHTML` (prismjs output — только token spans с class, без inline style), result toggle для executable.

**CardRenderer.tsx** — добавлены cases `metric`, `references`, `code`. `sendMessage` prop для ReferencesCard click (`Покажи {name}`).

**Markdown.tsx** — fenced ` ```bsl `, ` ```sql `, ` ```json ` → CodeCard вместо plain `<pre>`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] \b не работает с кириллицей в BSL grammar**
- **Found during:** Task 2 — highlight tests failing
- **Issue:** JavaScript `\b` word boundary не распознаёт кириллические символы как word chars (`\w`). `\b` в начале кириллического слова всегда false.
- **Fix:** Заменил `\b...\b` на lookahead/lookbehind `(?<![а-яёА-ЯЁa-zA-Z_\d])...(? ![а-яёА-ЯЁa-zA-Z_\d])` через вспомогательную функцию `wb(pattern)`.
- **Files modified:** `frontend/lib/bsl-grammar.ts`
- **Commit:** d8b7bbd

**2. [Rule 1 - Bug] Multi-line regex в bsl-grammar.ts вызывал parse error**
- **Found during:** Task 2 — oxc parser error "Unterminated regular expression"
- **Issue:** Первоначальный вариант файла содержал regex-литерал с переносом строки внутри (для читаемости), что не валидно в JS.
- **Fix:** Вынес паттерны в именованные константы с одной строкой regex.
- **Files modified:** `frontend/lib/bsl-grammar.ts`
- **Commit:** d8b7bbd

**3. [Rule 2 - Missing] DoS protection в CodeCard (frontend)**
- **Found during:** Task 2 — T-04-12 в threat_model
- **Issue:** CodeCard не ограничивал длину кода — потенциально длинный markdown fenced block мог тормозить prismjs.
- **Fix:** Добавил `CODE_TRUNCATE = 50_000` константу + усечение в CodeCard (дополнительно к backend truncation).
- **Files modified:** `frontend/components/cards/CodeCard.tsx`
- **Commit:** d8b7bbd

**4. [Rule 1 - Bug] test_execute_query_type_inference_from_rows ожидал TableCard**
- **Found during:** Task 1 — existing test incompatibility
- **Issue:** Старый тест проверял `card["payload"]["columns"]` для single-row result — теперь это MetricCard.
- **Fix:** Изменён тест на multi-row result, assertion обобщён до `card["type"] in ("table", "metric")`.
- **Files modified:** `backend/tests/test_orchestrator_cards.py`
- **Commit:** c5c984d

**5. [Rule 1 - Bug] test_find_references_direct_rows и test_execute_code_returns_none устарели**
- **Found during:** Task 1 — tests expected old behavior
- **Issue:** find_references_to_object теперь возвращает ReferencesCard, execute_code — CodeCard.
- **Fix:** Обновлены тесты под новые типы.
- **Files modified:** `backend/tests/test_orchestrator_cards.py`
- **Commit:** c5c984d

## Known Stubs

Нет стабов — все компоненты полностью функциональны.

## Pre-existing Issues (Out of Scope)

`useChatStream.test.tsx` — 11 failing tests в Pre-existing состоянии. Подтверждено стэш-тестом: те же 11 failures существовали до этого плана.

## Threat Flags

Нет новых поверхностей не в threat_model.

## Test Counts

| Module | Count | Pass |
|--------|-------|------|
| backend test_cards_advanced.py | 34 | 34 |
| backend test_orchestrator_cards.py | 19 | 19 |
| frontend lib/highlight.test.ts | 7 | 7 |
| frontend Sparkline.test.tsx | 5 | 5 |
| frontend MetricCard.test.tsx | 7 | 7 |
| frontend ReferencesCard.test.tsx | 6 | 6 |
| frontend CodeCard.test.tsx | 6 | 6 |
| **Total new** | **50** | **50** |

## Notes (Karpathy)

- Sparkline — 65 строк inline SVG, без recharts/chart.js (out_of_scope соблюдено)
- prismjs 10kb gzip vs shiki WASM (decision задокументировано)
- BSL grammar охватывает ~30 ключевых слов + ~40 builtins — не полный синтаксис 1С. Достаточно для demo. Post-MVP расширение по feedback.
- `_dispatch_query_card` — одна функция vs 2 отдельных (metric/table) — Simplicity First

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| backend/app/orchestrator/cards.py | FOUND |
| backend/tests/test_cards_advanced.py | FOUND |
| frontend/components/cards/MetricCard.tsx | FOUND |
| frontend/components/cards/ReferencesCard.tsx | FOUND |
| frontend/components/cards/CodeCard.tsx | FOUND |
| frontend/components/cards/Sparkline.tsx | FOUND |
| frontend/lib/bsl-grammar.ts | FOUND |
| frontend/lib/highlight.ts | FOUND |
| frontend/app/prism.css | FOUND |
| commit c5c984d (backend) | FOUND |
| commit d8b7bbd (frontend) | FOUND |
| backend 53 tests pass | PASS |
| cards.py coverage 87.8% (> 85%) | PASS |
| frontend 33 plan-tests pass | PASS |
| pnpm build | PASS |
| pnpm type-check | PASS |
| pnpm lint | PASS |
| 0 recharts/chart.js/shiki | PASS |
| prismjs only in lib/ (0 in components/) | PASS |
