---
phase: 02-mvp-chat
plan: 04
subsystem: channel-selector + connections-crud
tags: [channel-selector, mcp-connections, dropdown, ping, crud, sqlite, fastapi, radix-ui]
dependency_graph:
  requires: [02-01-orchestrator, 02-03-sessions]
  provides: [connections-crud-api, channel-selector-ui, ping-status-ui, channel-switching]
  affects: [02-05-trace]
tech_stack:
  added:
    - "@radix-ui/react-dropdown-menu@^2.1 (DropdownMenu wrapper)"
  patterns:
    - DropdownMenu + Portal mock в vitest (обход jsdom Portal)
    - pingAll = Promise.all + AbortController timeout 3000ms
    - Fallback localStorage при сетевой ошибке fetchConnections
    - onChannelChange → redirect на / в /sessions/[id] (избегаем confusion)
    - headerProps (опциональный) в AppShell для backward compat
    - Pydantic v2 model_post_init для endpoint URL validation
key_files:
  created:
    - backend/app/routes/connections.py
    - backend/tests/test_connections_route.py
    - frontend/components/ui/dropdown-menu.tsx
    - frontend/components/cards/__tests__/ChannelSelector.test.tsx
  modified:
    - backend/app/models.py — MCPConnectionCreate/Update/Full/List/MCPPingWithTimestampResponse
    - backend/app/main.py — connections_router зарегистрирован
    - backend/app/routes/mcp.py — backward compat Phase 1 (lookup в БД, fallback header/query)
    - frontend/components/shell/ChannelSelector.tsx — полностью переписан (dropdown + ping)
    - frontend/components/shell/Header.tsx — принимает HeaderProps (activeChannelId/onChannelChange)
    - frontend/components/shell/AppShell.tsx — headerProps опциональный prop
    - frontend/lib/api.ts — fetchConnections/create/update/delete/pingConnection
    - frontend/lib/storage.ts — syncMCPConnections
    - frontend/lib/types.ts — MCPConnection: last_seen_at + created_at
    - frontend/app/page.tsx — activeChannelId state + handleChannelChange
    - frontend/app/sessions/[id]/page.tsx — handleChannelChange → router.push("/")
decisions:
  - "При switching канала в /sessions/[id] → router.push('/') — текущая сессия привязана к старому каналу, не путаем пользователя"
  - "headerProps в AppShell — опциональный с default null/noop для backward compat с существующими тестами"
  - "pingAll на открытии dropdown — не background poller (Karpathy: избыточно), только при явном открытии"
  - "Fallback на localStorage только на сетевую ошибку; при успехе syncMCPConnections перезаписывает кеш"
  - "Portal mock в vitest — стандартный паттерн для Radix UI тестов в jsdom"
metrics:
  duration: "~11 мин"
  completed: "2026-05-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 11
---

# Phase 02 Plan 04: Channel Selector + Connections CRUD

Channel selector в header с ping-индикаторами (green/red/yellow), параллельный ping при открытии dropdown, переключение канала с редиректом на /, backend CRUD /connections с last_seen_at при пинге.

## Что сделано

### Task 1 — Backend connections CRUD + ping (коммит `6363f9d`)

- **models.py**: MCPConnectionCreate (endpoint validation http/https), MCPConnectionUpdate (all optional), MCPConnectionFull (с last_seen_at + created_at), MCPConnectionList, MCPPingWithTimestampResponse.
- **routes/connections.py**: GET/POST/PUT/DELETE /connections + POST /connections/{id}/ping. Ping обновляет last_seen_at при успехе, возвращает 502 при ошибке MCP (last_seen_at не обновляется).
- **routes/mcp.py**: backward compat — поиск conn_id в mcp_connections, fallback на X-MCP-Endpoint/query (Phase 1 паттерн). Статус 400 при отсутствии endpoint — Phase 1 тесты не сломаны.
- **main.py**: connections_router зарегистрирован.
- **test_connections_route.py**: 11 тестов (все зелёные). **122 backend тестов зелёных**.

### Task 2 — shadcn DropdownMenu + ChannelSelector (коммит `eb8d400`)

- **dropdown-menu.tsx**: DropdownMenu/Trigger/Content/Item/Label/Separator поверх @radix-ui/react-dropdown-menu. CSS vars совместимы с тёмной темой.
- **ChannelSelector.tsx**: полностью переписан:
  - fetchConnections при монтировании + syncMCPConnections; fallback на getMCPConnections при ошибке
  - При открытии dropdown: pingAll = Promise.all(connections.map(pingOne)) с AbortController timeout 3000ms
  - StatusDot: grey=unknown, yellow+pulse=checking, green=ok, red=error
  - Кнопка ↻ на каждой connection (stopPropagation, refresh single)
  - Кнопка "Обновить статус" внизу (pingAll) + ссылка "Настроить" → /settings
  - Empty state: "Подключения не настроены" + ссылка Настроить
- **api.ts**: 5 новых функций (fetchConnections, createConnection, updateConnection, deleteConnection, pingConnection)
- **storage.ts**: syncMCPConnections (алиас setMCPConnections для явного семантики)
- **types.ts**: MCPConnection расширен last_seen_at? + created_at?
- **ChannelSelector.test.tsx**: 5 vitest тестов (пустой список, 2 connections, onChange, fallback, pingAll)

### Task 3 — Header wire-up + switching behaviour (коммит `eb8d400`)

- **Header.tsx**: HeaderProps (activeChannelId, onChannelChange), передаёт в ChannelSelector
- **AppShell.tsx**: headerProps: HeaderProps (опциональный, default null/noop)
- **app/page.tsx**: activeChannelId из localStorage → useState, handleChannelChange обновляет state + localStorage + store.refresh()
- **app/sessions/[id]/page.tsx**: handleChannelChange → setActiveChannelId + router.push("/")

## Поведение switching канала в /sessions/[id]

Зафиксировано в CONTEXT.md: при переключении канала в открытой сессии → редирект на `/`. Альтернатива (остаться + warning) отвергнута. Реализация:

```typescript
function handleChannelChange(newId: string) {
  setActiveChannelId(newId);
  router.push("/");
}
```

Пользователь видит главную страницу, новый канал активен, следующий «+ Новый чат» создаётся с новым channel_id.

## Результаты верификации

```
pytest backend/ -v → 122 passed (0 failed)
pnpm type-check → 0 errors
pnpm lint → No ESLint warnings or errors
pnpm test --run → 37 passed (5 test files)
pnpm build → success (/, /sessions/[id], /settings)
```

## Отклонения от плана

### [Rule 1 - Bug] Radix DropdownMenu Portal не работает в jsdom

- **Найдено при:** Task 2 — первый запуск vitest
- **Проблема:** DropdownMenuContent рендерится в Portal вне DOM компонента — в jsdom контент не виден после fireEvent.click на trigger
- **Исправление:** Мокаем весь `@/components/ui/dropdown-menu` в тесте, заменяя на простые div-обёртки. Стандартный паттерн для Radix UI в jsdom.
- **Коммит:** `eb8d400` + `044f161`

### [Rule 2 - Missing] _onOpenChange ref для mock trigger

- **Найдено при:** Task 2 — 1 тест не мог симулировать открытие dropdown
- **Проблема:** Мокнутый DropdownMenuTrigger не вызывал onOpenChange при клике
- **Исправление:** Добавили модульную переменную `_onOpenChange` — DropdownMenu сохраняет, Trigger вызывает при onClick
- **Коммит:** `044f161`

## Known Stubs

Нет. Все компоненты работают с реальным backend API + localStorage fallback.

## Известные ограничения для Plan 2.5

- **Settings UI для CRUD connections** — отложен в Phase 3. В /settings пока нет формы для создания/редактирования подключений. ChannelSelector показывает только что есть в БД.
- **pingAll на >5 подключений** — 5+ одновременных HTTP запросов допустимо для MVP. Для Phase 3 при необходимости добавить concurrency limit (p-limit).
- **Рассинхронизация localStorage и backend** — при успешном fetchConnections кеш перезаписывается. Старый кеш используется только при сетевой ошибке.

## Threat Surface Scan

- GET /connections без auth — возвращает все endpoints MCP. MVP single-user, auth Phase 3.
- POST/PUT/DELETE /connections без auth — аналогично Phase 3.

## Self-Check: PASSED

- backend/app/routes/connections.py — FOUND
- backend/app/models.py — FOUND
- backend/tests/test_connections_route.py — FOUND
- frontend/components/ui/dropdown-menu.tsx — FOUND
- frontend/components/shell/ChannelSelector.tsx — FOUND
- frontend/components/cards/__tests__/ChannelSelector.test.tsx — FOUND
- commit 6363f9d — FOUND
- commit eb8d400 — FOUND
- commit 044f161 — FOUND
- backend 122 passed — VERIFIED
- frontend 37 passed — VERIFIED
- type-check 0 errors — VERIFIED
- lint 0 warnings — VERIFIED
- build success — VERIFIED
