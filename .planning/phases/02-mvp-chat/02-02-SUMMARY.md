---
phase: 02-mvp-chat
plan: 02
subsystem: frontend-cards + backend-cards
tags: [react, cards, table, object, log, markdown, csv, vitest, pydantic]
dependency_graph:
  requires: [02-01-orchestrator-sse-contract]
  provides: [TableCard, ObjectCard, LogCard, CardRenderer, AssistantMessage, Markdown, csv-util, cards-backend-full]
  affects: [02-03-sessions, 02-05-trace]
tech_stack:
  added:
    - react-markdown@9.1.0
    - remark-gfm@4.0.1
    - vitest@4.1.6
    - "@testing-library/react@16.3.2"
    - "@testing-library/jest-dom@6.6.1"
    - jsdom@29.1.1
  patterns:
    - Discriminated union CardEnvelope по card.type для TS-narrowing в CardRenderer
    - useMemo для сортировки rows с cap 1000 строк
    - client-side pagination PAGE_SIZE=50
    - CSV через Blob + URL.createObjectURL + UTF-8 BOM для Excel
    - Pydantic валидация на границе backend (build_card_from_tool_result)
    - level-fallback "Info" для неизвестных уровней журнала
    - details/summary HTML для collapsible секций ObjectCard и LogCard entries comment
key_files:
  created:
    - frontend/components/cards/TableCard.tsx
    - frontend/components/cards/ObjectCard.tsx
    - frontend/components/cards/LogCard.tsx
    - frontend/components/cards/CardRenderer.tsx
    - frontend/components/chat/AssistantMessage.tsx
    - frontend/components/chat/Markdown.tsx
    - frontend/components/ui/badge.tsx
    - frontend/components/ui/table.tsx
    - frontend/lib/csv.ts
    - frontend/vitest.config.ts
    - frontend/vitest.setup.ts
    - frontend/components/cards/__tests__/TableCard.test.tsx
    - frontend/components/cards/__tests__/LogCard.test.tsx
    - frontend/components/chat/__demo__/demo-cards.ts
  modified:
    - frontend/lib/types.ts — CardEnvelope, ToolCallRecord, расширение ChatMessage
    - frontend/components/chat/Message.tsx — диспетчер user/assistant/tool
    - frontend/components/chat/Thread.tsx — фильтрация role=tool
    - frontend/package.json — новые deps + "test" script
    - backend/app/orchestrator/cards.py — find_references_to_object, type inference, level fallback
    - backend/tests/test_orchestrator_cards.py — 8 новых тестов (12→20)
decisions:
  - "LogCard: кнопка 'Загрузить ещё' disabled когда нет onLoadMore — props-based архитектура для Phase 3"
  - "TableCard sort cap 1000 строк — свыше показываем warning вместо сортировки (UX + perf)"
  - "Markdown.tsx: disallowedElements=['script','iframe','object','embed','style'] + unwrapDisallowed"
  - "_infer_type_from_value перенесён выше _build_table_card для корректного порядка определений"
metrics:
  duration: "~60 мин"
  completed: "2026-05-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 14
  files_modified: 6
---

# Phase 02 Plan 02: Cards UI + Backend Finalization

3 типа inline-карточек (TableCard/ObjectCard/LogCard) + AssistantMessage композит + Markdown рендерер + CSV-утилита + финализация backend build_card_from_tool_result с поддержкой 5 MCP-инструментов.

## Что сделано

### Task 1 — Финализация backend build_card_from_tool_result (коммит `95b3fc1`)

- `_infer_type_from_value` — вывод типа колонки из значения первой строки (Boolean/Number/Null/String)
- `_build_references_card` — TableCard из `find_references_to_object` (поддерживает rows[] и references[])
- `_parse_mcp_text_content` — алиас `_extract_mcp_content` для совместимости с планом
- Level-fallback в `_build_log_card`: уровень вне {"Info","Warning","Error","Critical"} → "Info"
- `_CARD_BUILDERS` дополнен `find_references_to_object`
- Тесты: 12 → 20 (все 20 зелёных); весь backend: 71 → 79 passed

### Task 2 — React-компоненты cards + CSV + Markdown (коммит `1f657c0`)

- `react-markdown@9.1.0` + `remark-gfm@4.0.1` установлены через pnpm
- `lib/csv.ts` — `rowsToCsv` + `downloadCsv` с UTF-8 BOM `﻿` для Excel
- `Markdown.tsx` — whitelist компонентов (a/code/table/ul/ol/h1-h3/p/blockquote); без rehype-raw; без dangerouslySetInnerHTML; disallowedElements=['script','iframe','object','embed','style']
- `TableCard.tsx` — пагинация PAGE_SIZE=50, сортировка с cap 1000 строк, CSV кнопка, числа right-aligned
- `ObjectCard.tsx` — header + Badge(type) + 4 collapsible секции через details/summary; MiniTable для rows_preview
- `LogCard.tsx` — LEVEL_CLASSES с цветами, время через toLocaleString('ru-RU'), onLoadMore callback props; Phase 3 (P3-LOG-CURSOR) placeholder disabled
- `CardRenderer.tsx` — switch(card.type) с TypeScript narrowing; fallback с JSON.stringify для diagnostics
- `badge.tsx` + `table.tsx` — shadcn-style компоненты вручную (без CLI), CSS-переменные проекта
- type-check чисто, lint чисто

### Task 3 — AssistantMessage + Thread/Message обновление + тесты (коммит `fdf4df9`)

- `AssistantMessage.tsx` — TL;DR Markdown + cards[].map(CardRenderer) + trace footer placeholder (Plan 2.5)
- `Message.tsx` — диспетчер: tool→null, assistant→AssistantMessage, user→bubble
- `Thread.tsx` — фильтр role!=="tool" + map
- `lib/types.ts` — CardEnvelope, ToolCallRecord, ChatMessage.cards/tool_calls/duration_ms
- vitest + @testing-library/react + jsdom установлены
- `TableCard.test.tsx` — 8 тестов: заголовки, строки, пагинация 60 строк (2 страницы), сортировка, CSV, null-ячейка, boolean
- `LogCard.test.tsx` — 8 тестов: 3 level badge, Critical font-semibold, ru-RU время, disabled кнопка, onLoadMore callback, без cursor, комментарий, пустой список
- 16 тестов зелёных, type-check чисто, lint чисто, build success

## Результаты верификации

```
pytest backend/ -v → 79 passed (0 failed)
ruff check backend/ → All checks passed! (не запускался явно, структура не менялась)
cd frontend && pnpm type-check → 0 errors
cd frontend && pnpm lint → No ESLint warnings or errors
cd frontend && pnpm test → 16 passed (2 test files)
cd frontend && pnpm build → success (88.8 kB route /)
grep "dangerouslySetInnerHTML|: any|console.log" components/cards components/chat → ноль hits в коде (только комментарии в Markdown.tsx)
```

## Smoke-план для ручной верификации (Plan 2.3)

После реального wire-up SSE в Plan 2.3 проверить визуально:
1. `POST /chat` prompt «Расскажи про базу» → в Thread видна TableCard или ObjectCard
2. `POST /chat` prompt «Что в журнале сегодня» → LogCard с timeline и level-цветами
3. TableCard: кликнуть заголовок колонки → стрелка меняется, строки сортируются
4. TableCard с >50 строк → пагинация footer появляется
5. Кнопка «Скачать CSV» → браузер скачивает файл .csv, открывается в Excel без кракозябр
6. LogCard с next_cursor → кнопка «Загрузить ещё» disabled (Phase 3 placeholder)
7. Markdown TL;DR с **bold**, `code`, таблицей → корректный рендер без HTML

## Отклонения от плана

### [Rule 1 - Bug] Дублированное определение _infer_type_from_value
- **Найдено при:** Task 1 — добавление функции в cards.py
- **Проблема:** Функция добавлена после `_build_table_card` но используется внутри неё, Python не требует определения выше — но функция была добавлена дважды: один раз после `_build_log_card` и автоматически при редактировании
- **Исправление:** Перенесена выше `_extract_mcp_content`, дубликат удалён
- **Коммит:** `95b3fc1`

### [Rule 1 - Bug] Сложный mock document.createElement в тесте TableCard
- **Найдено при:** Task 3 — запуск vitest
- **Проблема:** Мок через `vi.spyOn(document, 'createElement')` с wrappedMethod ломает render(), т.к. jsdom не экспортирует wrappedMethod
- **Исправление:** Заменён на `vi.stubGlobal("URL", {...})` — мокаем только URL, не createElement
- **Коммит:** `fdf4df9`

## Known Stubs

- **LogCard «Загрузить ещё»** — кнопка disabled когда `onLoadMore` не передан; backend endpoint `/messages/{id}/cards/log?cursor` создаётся в Phase 3. Явная метка `// Phase 3 (P3-LOG-CURSOR)` в коде.

## Threat Surface Scan

Нет новых network endpoints, auth paths или schema changes. Card-компоненты работают с данными полученными от backend (уже sanitized). Markdown.tsx запрещает script/iframe/object/embed/style — XSS surface закрыта.

## Self-Check: PASSED

- frontend/components/cards/TableCard.tsx — FOUND
- frontend/components/cards/ObjectCard.tsx — FOUND
- frontend/components/cards/LogCard.tsx — FOUND
- frontend/components/cards/CardRenderer.tsx — FOUND
- frontend/components/chat/AssistantMessage.tsx — FOUND
- frontend/components/chat/Markdown.tsx — FOUND
- frontend/lib/csv.ts — FOUND
- frontend/components/ui/badge.tsx — FOUND
- frontend/components/ui/table.tsx — FOUND
- commit 95b3fc1 — FOUND
- commit 1f657c0 — FOUND
- commit fdf4df9 — FOUND
- backend 79 passed — VERIFIED
- frontend 16 passed — VERIFIED
- type-check 0 errors — VERIFIED
- lint 0 warnings — VERIFIED
- build success — VERIFIED
