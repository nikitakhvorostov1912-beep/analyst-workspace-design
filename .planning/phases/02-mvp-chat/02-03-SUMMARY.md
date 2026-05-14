---
phase: 02-mvp-chat
plan: 03
subsystem: sessions + history UI + URL routing + chat wire-up
tags: [sessions, crud, auto-title, sidebar, url-routing, useChatStream, sse, sqlite, pydantic-v2]
dependency_graph:
  requires: [02-01-orchestrator-sse-contract, 02-02-cards-ui]
  provides: [sessions-crud, history-ui, url-routing, useChatStream, auto-title, SessionList]
  affects: [02-04-channel, 02-05-trace]
tech_stack:
  added: []
  patterns:
    - Python datetime grouping в persistence.py (today/yesterday/this_week/earlier)
    - asyncio.create_task для auto-title background task без блокировки main loop
    - React useState + useCallback owner-component pattern (без Zustand)
    - useChatStream hook: SSE stream → immutable messages state (prev => [...])
    - Lazy session creation: «Новый чат» создаёт сессию сразу, no cleanup task
    - window.confirm для delete (MVP; shadcn AlertDialog — Phase 3)
key_files:
  created:
    - backend/app/orchestrator/title.py
    - backend/tests/test_orchestrator_title.py
    - backend/tests/test_sessions_route.py
    - frontend/lib/sessions-store.ts
    - frontend/components/shell/SessionList.tsx
    - frontend/components/chat/useChatStream.ts
    - frontend/app/sessions/[id]/page.tsx
    - frontend/components/shell/__tests__/SessionList.test.tsx
    - frontend/components/chat/__tests__/useChatStream.test.tsx
  modified:
    - backend/app/models.py — SessionCreate/List/Grouped/Detail/Messages/Patch models
    - backend/app/orchestrator/persistence.py — list_sessions_grouped, get_session, get_session_messages, delete_session, update_session_title, count_session_messages
    - backend/app/routes/sessions.py — полный CRUD (был только POST)
    - backend/app/orchestrator/loop.py — auto-title background task after first user message
    - frontend/lib/types.ts — SessionListItem/Grouped/Detail/MessageRow types
    - frontend/lib/api.ts — createSession/fetchSessions/fetchSessionDetail/fetchSessionMessages/deleteSession/patchSessionTitle
    - frontend/components/shell/Sidebar.tsx — props-based (grouped/activeId/onCreateNew/onDelete)
    - frontend/components/shell/AppShell.tsx — пробрасывает grouped/activeId/onCreateNew/onDeleteSession в Sidebar
    - frontend/components/chat/Thread.tsx — auto-scroll to bottom (useRef + useEffect)
    - frontend/components/chat/Input.tsx — disabled prop
    - frontend/app/page.tsx — реальный store, кнопка Новый чат с router.push
decisions:
  - "auto-title: asyncio.create_task (fire-and-forget) — не блокирует SSE стрим; при ошибке log warning, title остаётся null → UI показывает «Новый чат»"
  - "«Новый чат» создаёт сессию сразу при клике (не при первом сообщении) — проще, не нужен /sessions/new специальный URL и cleanup"
  - "Date grouping в Python (datetime.now()) — избегаем TZ-проблемы SQLite DATE('now','localtime')"
  - "SessionsStore без Zustand — useState + useCallback, owner-page pattern; drilling только 1 уровень (page → AppShell → Sidebar)"
  - "useChatStream: immutable prev => [...prev.slice(0,-1), updatedAssistant] для каждого SSE события"
  - "MessageRow → ChatMessage конвертация: content null → empty string; tool_calls/cards null → []"
metrics:
  duration: "~90 мин"
  completed: "2026-05-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 9
  files_modified: 11
---

# Phase 02 Plan 03: Sessions CRUD + History UI + URL Routing + Chat Wire-up

Sessions CRUD с group_by_date, auto-title background task, useChatStream hook для реального SSE-стрима, SessionList с 4 датовыми группами, динамический маршрут /sessions/[id] с восстановлением истории.

## Что сделано

### Task 1 — Backend sessions CRUD + auto-title (коммит `b4a179a`)

- **models.py**: SessionCreate, SessionListItem, SessionsGrouped, SessionDetail, MessageRow, SessionMessages, SessionPatch — все с `extra="forbid"`.
- **persistence.py**: 6 новых функций — `list_sessions_grouped` (Python datetime grouping), `get_session`, `get_session_messages` (десериализация JSON tool_calls/cards, cap 500), `delete_session`, `update_session_title`, `count_session_messages`.
- **title.py**: `heuristic_title` (первые 7 слов до знака препинания, cap 60 символов, fallback «Новый чат») + `generate_title` (async LLM call с fallback на heuristic).
- **sessions.py**: полный CRUD — POST/GET/PATCH/DELETE /sessions + GET /sessions/{id}/messages.
- **loop.py**: после `save_user_message`, если `msg_count_before == 0` → `asyncio.create_task(_run_auto_title())`. Не блокирует SSE поток.
- 32 новых теста: 15 title + 17 sessions. **111 passed** (был 79).

### Task 2 — Frontend sessions store + SessionList + useChatStream (коммит `9989db3`)

- **types.ts**: SessionListItem, SessionsGrouped, SessionDetail, MessageRow.
- **api.ts**: createSession, fetchSessions, fetchSessionDetail (null при 404), fetchSessionMessages, deleteSession, patchSessionTitle.
- **sessions-store.ts**: `useSessionsStore()` — refresh/createNew/remove/renameLocal через useState + useCallback. Оптимистичное удаление (фильтр без roundtrip).
- **SessionList.tsx**: GroupSection + SessionItem, 4 группы, пустые группы скрываются, title=null → «Новый чат» italic, meta строка (N сообщ. · relative time), кнопка trash (hidden до hover, confirm → onDelete).
- **Sidebar.tsx**: переделан под props-based; AppShell.tsx пробрасывает props.
- **useChatStream.ts**: 7 SSE events — status (пропуск), delta (контент +=), tool_call (push), tool_result (update by id), card (push), done (id/duration update), error (setError + break).
- **Thread.tsx**: auto-scroll (bottomRef + useEffect[messages]).
- **Input.tsx**: disabled prop (readOnly textarea, disabled button).
- 16 новых vitest тестов: 8 SessionList + 8 useChatStream. **32 frontend tests passed**.

### Task 3 — URL routing + интеграция (коммит `ae32e6e`)

- **app/sessions/[id]/page.tsx**: dynamic route — `fetchSessionDetail` (404 → router.replace("/")), `fetchSessionMessages` → `messageRowToChat`, `store.refresh()` параллельно. `useChatStream` с initialMessages. Sidebar подключён с реальными данными. Delete текущей сессии → router.push("/").
- **app/page.tsx**: `useSessionsStore().refresh()` при mount. «Новый чат» → `store.createNew(ch)` → `router.push(/sessions/${id})`. Sidebar получает реальный grouped.
- **build success**: / (197kB), /sessions/[id] dynamic (198kB).

## Результаты верификации

```
pytest backend/ -v → 111 passed (0 failed)
pnpm type-check → 0 errors
pnpm lint → No ESLint warnings or errors
pnpm test --run → 32 passed (4 test files)
pnpm build → success (/sessions/[id] dynamic route)
```

## Архитектурные решения

### Auto-title pattern
```python
if msg_count_before == 0:
    async def _run_auto_title() -> None:
        try:
            llm = LLMClient(...)
            new_title = await generate_title(request.message, llm, api_key)
            await update_session_title(db, session_id, new_title)
        except Exception:
            logger.warning("Auto-title failed for session %s", session_id)
    asyncio.create_task(_run_auto_title())
```
Не блокирует main loop. aiosqlite с WAL mode поддерживает конкурентные операции.

### Lazy session create (resolved Risk #5 from plan)
Решение: создаём сессию при клике «Новый чат», а не при первом сообщении. Это проще (нет /sessions/new URL, нет cleanup task). Пустые сессии без messages — в sidebar виден «Новый чат» italic, удаляются вручную.

### Date grouping location
Группировка в Python (persistence.py), а не в SQL — избегаем `DATE('now','localtime')` TZ-проблем SQLite. Для single-user MVP достаточно.

## Known Stubs

Нет. Все компоненты подключены к реальным данным.

## Отклонения от плана

### [Rule 1 - Bug] Неверная попытка импортировать DB_PATH
- **Найдено при:** Task 1 — первый запуск тестов
- **Проблема:** `from app.storage.db import DB_PATH` — DB_PATH не экспортируется из db.py (db path хранится в settings)
- **Исправление:** в тесте используем `app.state.db` напрямую
- **Коммит:** `b4a179a`

### [Rule 1 - Bug] test_long_message_truncated — неверный input
- **Найдено при:** Task 1 — первый запуск тестов
- **Проблема:** "Очень длинное сообщение " × 20 = 7 слов × 3 символа ≈ 48 chars — не превышает 60, не обрезается
- **Исправление:** Используем "А" × 100 — одно слово 100 символов, гарантированно > 60
- **Коммит:** `b4a179a`

### [Rule 1 - Bug] Тест SessionList — конфликт getByText("Сегодня")
- **Найдено при:** Task 2 — первый запуск vitest
- **Проблема:** title item тоже называлась "Сегодня", getByText нашёл оба элемента
- **Исправление:** Переименованы тестовые данные в "Чат-1".."Чат-4", группа Сегодня ищется с `{ selector: "div.uppercase" }`
- **Коммит:** `9989db3`

## Threat Surface Scan

- GET /sessions возвращает все сессии — без auth (Phase 2 scope, MVP single-user). Новый network endpoint, но в threat model Phase 2 явный выбор: auth — Phase 3.
- DELETE /sessions/{id} без auth — любой может удалить. Аналогично.

## Self-Check: PASSED

- backend/app/routes/sessions.py — FOUND
- backend/app/orchestrator/title.py — FOUND
- backend/app/orchestrator/persistence.py — FOUND
- backend/app/models.py — FOUND
- backend/tests/test_sessions_route.py — FOUND
- backend/tests/test_orchestrator_title.py — FOUND
- frontend/lib/sessions-store.ts — FOUND
- frontend/components/shell/SessionList.tsx — FOUND
- frontend/components/chat/useChatStream.ts — FOUND
- frontend/app/sessions/[id]/page.tsx — FOUND
- commit b4a179a — FOUND
- commit 9989db3 — FOUND
- commit ae32e6e — FOUND
- backend 111 passed — VERIFIED
- frontend 32 passed — VERIFIED
- type-check 0 errors — VERIFIED
- lint 0 warnings — VERIFIED
- build success — VERIFIED
