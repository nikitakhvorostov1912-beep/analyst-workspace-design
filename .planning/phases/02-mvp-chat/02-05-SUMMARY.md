---
phase: 02-mvp-chat
plan: 05
subsystem: trace-panel
tags: [trace, json-tree, tool-calls, collapsible, vitest, typescript]
dependency_graph:
  requires: [02-01-orchestrator, 02-02-cards, 02-03-sessions]
  provides: [tool-trace-ui, json-tree-component, format-duration-utility]
  affects: []
tech_stack:
  added: []
  patterns:
    - Рекурсивный компонент JsonTree без внешних зависимостей (~130 строк TSX)
    - Circular reference detection через try/catch JSON.stringify
    - CollapsibleNode как внутренний sub-компонент (не экспортируется)
    - plural_ru функция для pluralTools (1/2-4/5+)
    - details/summary HTML для lazy mount result panel
key_files:
  created:
    - frontend/lib/format-duration.ts
    - frontend/lib/json-tree.tsx
    - frontend/components/chat/ToolTrace.tsx
    - frontend/components/chat/__tests__/JsonTree.test.tsx
    - frontend/components/chat/__tests__/ToolTrace.test.tsx
  modified:
    - frontend/components/chat/AssistantMessage.tsx — убран trace-placeholder, добавлен ToolTrace
decisions:
  - "JsonTree: рекурсия через сам компонент (не visitor pattern) — Karpathy Simplicity First"
  - "Circular detection: try/catch JSON.stringify (достаточно для MVP, без WeakSet)"
  - "defaultExpanded=1 для args, =0 для result — пользователь видит ключи args сразу, result открывает сам"
  - "details/summary для result — lazy mount (не рендерим JsonTree пока не открыто)"
  - "TRACE-03 намеренно отсутствует — Phase 3 OOS"
  - "pluralTools: 1='инструмент', 2-4='инструмента', 5+='инструментов'"
metrics:
  duration: "~20 мин"
  completed: "2026-05-14"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 1
---

# Phase 02 Plan 05: Trace Panel — JsonTree + ToolTrace

Рекурсивный JSON viewer + collapsible trace panel под каждым assistant сообщением. Аналитик может раскрыть «N инструментов, X мс» и увидеть все tool calls с args/result/error.

## Что сделано

### Task 1 — JsonTree + formatDuration + unit-тесты (коммит `3873b9e`)

**lib/format-duration.ts:**
- `formatDuration(ms)` → `"450 мс"` / `"1.2 с"` / `"2 мин 30 с"`
- null/undefined/negative → пустая строка

**lib/json-tree.tsx** (~130 строк TSX, без внешних зависимостей):
- Рекурсивный рендер: string (green-300), number (orange-300), boolean/null (purple-300), keys (fg-muted)
- Объекты `{N}` и массивы `[N]` collapsible через `CollapsibleNode` (внутренний sub-компонент)
- `defaultExpanded` depth: 0=всё свёрнуто, 1=верхний уровень, Infinity=всё открыто
- Пустые `{}` и `[]` без кнопки collapse
- Строки обрезаются до 200 символов с маркером `⋯`
- Циклические ссылки: `try JSON.stringify catch` → `[Circular]` text-red-400

**__tests__/JsonTree.test.tsx:** 12 кейсов (все зелёные):
- Primitive: string, number, boolean, null
- Объект свёрнут (defaultExpanded=0) и раскрыт (defaultExpanded=1)
- Массив свёрнут, click → раскрытие
- Вложенность с defaultExpanded=2
- Пустые {} и []
- Circular reference без crash

### Task 2 — ToolTrace + интеграция в AssistantMessage + unit-тесты (коммит `e753427`)

**components/chat/ToolTrace.tsx:**
- `if toolCalls.length === 0 → return null` (нет fake-empty trace)
- Collapsed: ChevronRight + «N инструментов[а/ов], X мс»
- Expanded: список tool calls с:
  - `name` (font-mono, data-testid="tool-name")
  - `· duration` если есть
  - `· ошибка` badge если `ok=false` (red-400)
  - `<details>Аргументы</details>` → JsonTree(args, defaultExpanded=1)
  - `<details>Результат</details>` → JsonTree(result, defaultExpanded=0), только если result !== undefined
  - `error` текст если есть (red-400 font-mono)
- TRACE-03 (Copy as curl) — намеренно отсутствует, Phase 3

**components/chat/AssistantMessage.tsx:**
- Удалён `<div data-testid="trace-placeholder">` из Plan 2.2
- Добавлен `<ToolTrace toolCalls={...} totalDurationMs={...} />`

**__tests__/ToolTrace.test.tsx:** 7 кейсов (все зелёные):
- null при toolCalls=[]
- заголовок с числом и duration
- expand → видны tool names
- ok=false → error badge + error text
- result → секция «Результат»
- plural forms (1/5 инструментов)

## Результаты верификации

```
pnpm type-check → 0 errors
pnpm lint       → No ESLint warnings or errors
pnpm test --run → 56 passed (7 test files)  [было 37 в 5 файлах]
pnpm build      → success (/, /sessions/[id], /settings, /_not-found)
```

Дополнительные проверки:
```
grep TODO|FIXME|placeholder ToolTrace.tsx json-tree.tsx → 0 (ничего)
grep curl ToolTrace.tsx → 0 (TRACE-03 намеренно отсутствует)
```

## Отклонения от плана

### [Rule 1 - Bug] Тест для defaultExpanded=2 — скорректирован

- **Найдено при:** первом запуске JsonTree.test.tsx
- **Проблема:** Тест ожидал видеть `c:` при `{a:{b:{c:1}}}` с `defaultExpanded=2`, но `{c:1}` на глубине 2 свёрнут (2 > 2 = false)
- **Исправление:** Тест скорректирован — проверяем что `{1}` свёрнут и `c:` не виден (что и есть корректное поведение)
- **Не регрессия** — тест описывал неверное ожидание, поведение компонента правильное

## Соответствие REQUIREMENTS

- **TRACE-01**: Под каждым assistant message где tool_calls > 0 — collapsed строка «N инструментов, X мс». Если 0 — строка отсутствует. ✓
- **TRACE-02**: Click → expand → список tool calls с name (mono) + args (JsonTree) + result (collapsed) + duration + error. ✓
- **TRACE-03**: Намеренно отсутствует — явный OOS для Phase 2, Phase 3 только. ✓
- **Persistence**: tool_calls привязаны к message_id в БД (Plan 2.1), возвращаются через GET /sessions/{id}/messages (Plan 2.3), рендерятся в ToolTrace при загрузке истории. ✓

## Не верифицировано (manual smoke)

Manual smoke: загрузить `/sessions/{id}` с историей где LLM делала tool_calls → collapsed строка → click → expanded список с args/result.

Требует живой backend + LLM endpoint. Тестовые данные можно создать через POST /chat с замоканными MCP/LLM (тест-фикстура в виде SQLite-сессии с tool_calls).

## Known Stubs

Нет. Все компоненты полностью реализованы.

## Threat Surface Scan

Нет новых network endpoints или auth paths. ToolTrace рендерит данные из уже существующей структуры messages.tool_calls — данные приходят с backend (уже существующие endpoints из Plan 2.1/2.3).

## Self-Check: PASSED

- frontend/lib/format-duration.ts — FOUND
- frontend/lib/json-tree.tsx — FOUND
- frontend/components/chat/ToolTrace.tsx — FOUND
- frontend/components/chat/__tests__/JsonTree.test.tsx — FOUND
- frontend/components/chat/__tests__/ToolTrace.test.tsx — FOUND
- commit 3873b9e — FOUND
- commit e753427 — FOUND
- 56 vitest passed — VERIFIED
- type-check 0 errors — VERIFIED
- lint 0 warnings — VERIFIED
- build success — VERIFIED
