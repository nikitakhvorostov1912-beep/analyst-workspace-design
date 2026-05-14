---
phase: 03-production-ready
plan: "04"
subsystem: docs-and-polish
tags: [trace, devx, docs, log-card, curl, backend, frontend]
dependency_graph:
  requires: [03-01, 03-02]
  provides: [TRACE-03, DEVX-04, DEVX-05, CARD-03-cursor-fetch]
  affects: [README.md, ARCHITECTURE.md, frontend/ToolTrace, frontend/LogCard, backend/routes/log_cards]
tech_stack:
  added: [curl-builder.ts, card_states table (v3)]
  patterns: [stateful cursor fetch, clipboard API, SSE event 8-matrix]
key_files:
  created:
    - backend/app/routes/log_cards.py
    - backend/tests/test_log_cards_route.py
    - frontend/lib/curl-builder.ts
    - frontend/lib/__tests__/curl-builder.test.ts
    - docs/USER.md
    - docs/API.md
    - docs/CURL.md
  modified:
    - backend/app/storage/migrations.py
    - backend/app/orchestrator/persistence.py
    - backend/app/orchestrator/cards.py
    - backend/app/orchestrator/loop.py
    - backend/app/models.py
    - backend/app/main.py
    - frontend/components/chat/ToolTrace.tsx
    - frontend/components/chat/AssistantMessage.tsx
    - frontend/components/cards/LogCard.tsx
    - frontend/components/cards/CardRenderer.tsx
    - frontend/lib/api.ts
    - frontend/lib/types.ts
    - frontend/components/chat/__tests__/ToolTrace.test.tsx
    - frontend/components/cards/__tests__/LogCard.test.tsx
    - README.md
    - ARCHITECTURE.md
decisions:
  - "card_states — отдельная таблица v3 (не колонка в messages): проще миграция, нет ALTER TABLE"
  - "card_id генерируется в _build_log_card, сохраняется в loop после save_assistant_message (message_id уже известен)"
  - "mcpEndpoint в curl — из localStorage активного канала, undefined → placeholder <MCP_ENDPOINT>"
  - "Mcp-Session-Id не включается в curl (не хранится на фронте) — описано в CURL.md как known limitation"
  - "load-more state не персистируется (after page reload entries теряются) — v2"
metrics:
  duration: "~2h (основная часть уже была реализована предыдущим агентом)"
  completed_date: "2026-05-14"
  tasks_completed: 3
  files_changed: 20
---

# Phase 3 Plan 04: Docs + TRACE-03 + LogCard load-more Summary

**Финал Phase 3.** TRACE-03, DEVX-04, DEVX-05 закрыты. LogCard cursor-fetch endpoint (Phase 2 deferred) закрыт. Полная документация добавлена.

---

## Что сделано

### Task 1: Backend — LogCard load-more endpoint

**Миграция v3** (`storage/migrations.py`):
- Новая таблица `card_states` (card_id PK, session_id, message_id, tool_name, original_args JSON, channel_id)
- Идемпотентная: `CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE INTO schema_version`

**Persistence** (`orchestrator/persistence.py`):
- `save_card_state(db, *, card_id, session_id, message_id, tool_name, original_args, channel_id)`
- `get_card_state(db, card_id) → dict | None`

**Cards** (`orchestrator/cards.py`):
- `_build_log_card` генерирует `card_id = str(uuid4())` и помещает в `LogCardPayload.card_id`

**Loop** (`orchestrator/loop.py`):
- После `save_assistant_message` итерирует `accumulated_cards`, для type=log → `save_card_state` с реальным message_id

**Route** (`routes/log_cards.py`):
- `POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more`
- Ownership check: `state.session_id == sid AND state.message_id == mid`
- 404 если card не найдена; 502 если канал недоступен или MCP ошибка
- `LoadMoreRequest(cursor: str, strict=True)` → 422 при int

**Models** (`models.py`):
- `LoadMoreRequest(cursor: str, min_length=1, strict=True)`
- `LogPagePayload(entries: list[dict], next_cursor: str | None)`

**Тесты** — 15 тестов в `test_log_cards_route.py`, все зелёные:
- migration v3 создаёт таблицу + idempotency
- save/get card_state
- build_card_from_tool_result возвращает card_id (UUID4, уникальный)
- loop сохраняет card_state в БД
- POST load-more: 200 + entries; 404 unknown card; 502 unknown channel; 502 MCP error; 422 strict type; 404 sid mismatch

### Task 2: Frontend — Copy as curl + LogCard wire-up

**curl-builder.ts** (`lib/curl-builder.ts`, ~45 строк):
- `buildCurlCommand(toolCall, mcpEndpoint, mcpSessionId?) → string`
- Пустой endpoint → `<MCP_ENDPOINT>` placeholder
- Экранирование single quotes: `replace(/'/g, "'\\''")`
- 4 теста в `curl-builder.test.ts` — все зелёные

**ToolTrace.tsx**:
- Prop `mcpEndpoint?: string; mcpSessionId?: string`
- Кнопка `<Copy size={12} /> Скопировать как curl` в каждой tool-row
- `handleCopyCurl` — try/catch: success → `publishToast({type:"info", message:"Скопировано"})`, catch → error toast
- 3 новых теста в `ToolTrace.test.tsx`: рендер кнопки, clipboard.writeText вызван, ошибка → error toast

**AssistantMessage.tsx**:
- `getActiveChannelId()` + `getMCPConnections().find(c => c.id === activeChannelId)?.endpoint`
- `CardContext { sessionId, messageId, mcpEndpoint }` → передаётся в `CardRenderer`
- `<ToolTrace mcpEndpoint={mcpEndpoint} />`

**CardRenderer.tsx**:
- Prop `context?: CardContext`
- Для type=log: `cardId = logPayload.card_id` → если есть + `context.sessionId/messageId` → `onLoadMore = (cursor) => loadMoreLogEntries(sid, mid, cardId, cursor)`

**LogCard.tsx**:
- `onLoadMore` передаётся через `CardRenderer`, кнопка enabled при `currentCursor != null && onLoadMore`
- При успехе append entries в `extraEntries`, обновить cursor
- При ошибке — `publishToast({type:"error"})`
- 2 новых теста в `LogCard.test.tsx`: append success + error toast

**api.ts**:
- `loadMoreLogEntries(sid, mid, cid, cursor) → Promise<{entries, next_cursor}>`

**types.ts**:
- `LogCardPayload.card_id?: string | null` (уже был)
- `CardContext = {sessionId, messageId, mcpEndpoint?, mcpSessionId?}` (уже был)

### Task 3: Документация

**README.md** (~130 строк):
- Установка / Быстрый старт / Конфигурация / docker compose up / Тестирование / CI / Troubleshooting
- Ссылки на docs/

**docs/USER.md** (~150 строк):
- Подключаем 1С (пошагово), Подключаем LLM, Задаём первый вопрос
- Читаем trace, Копируем как curl, Confirm dialog, Если 1С не отвечает
- FAQ — 8 вопросов

**docs/API.md** (~135 строк):
- 13 endpoints (все)
- SSE events matrix — 8 событий
- Error codes — 12 кодов
- Ссылка на Swagger UI + OpenAPI JSON команда
- Примеры curl

**docs/CURL.md** (~75 строк):
- Формат команды + пример
- Пошаговое использование (initialize + tools/call)
- Known limitation: Mcp-Session-Id не включается

**ARCHITECTURE.md** (~275 строк):
- Актуальная ASCII-топология (Phase 3 компоненты)
- Полный data flow диаграмма (8 SSE events)
- SSE events matrix 8 events
- 12 ErrorCode
- Persistence schema v3 с card_states
- Security table (5 механизмов)
- Frontend libs
- Phase summaries таблица
- Legacy явно отмечен: `mockups/_legacy/` и `docs/_archive-v0-object-ide/`

---

## Метрики

- Backend новых тестов: **15** (`test_log_cards_route.py`)
- Frontend новых тестов: **9** (4 curl-builder + 3 ToolTrace + 2 LogCard)
- Итого новых тестов: **24**
- Frontend всего: **97 vitest** — все зелёные
- type-check, lint: чисто
- Docs: 5 файлов, 769 строк суммарно (≤ 1100) — 0 TODO/FIXME/placeholder

---

## Deviations from Plan

None — план выполнен точно как написано. Основная реализация Task 1 и Task 2 была
уже завершена предыдущим агентом и закоммичена (commits `c24c498`, `f296b12`, `697a502`, `4a994ae`).
Данный агент верифицировал корректность реализации (все тесты зелёные) и выполнил Task 3.

---

## Known Stubs

Нет.

---

## Threat Flags

Нет новых незарегистрированных поверхностей. Все угрозы покрыты в `<threat_model>` плана:
- T-03-18 (curl clipboard): accept — tool args не содержат API ключи
- T-03-19 (load-more cursor tampering): mitigate — Pydantic strict + MCP валидация
- T-03-20 (load-more без auth): accept — MVP single-user, ownership check present
- T-03-21 (DoS load-more): accept — rate limiting v2

---

## Commits

| Hash | Тип | Описание |
|------|-----|---------|
| `c24c498` | test(03-04) | RED: backend tests for log cards route |
| `f296b12` | feat(03-04) | GREEN: migration v3 + card_states + POST endpoint |
| `697a502` | test(03-04) | RED: frontend curl-builder + ToolTrace + LogCard tests |
| `4a994ae` | feat(03-04) | GREEN: frontend copy-curl + LogCard load-more wired |
| `d07d4d0` | feat(03-04) | docs: README + USER.md + API.md + CURL.md + ARCHITECTURE.md |

---

## Self-Check: PASSED

- [x] `docs/USER.md` — создан (150 строк, FAQ 8 вопросов)
- [x] `docs/API.md` — создан (136 строк, 13 endpoints, 8 events, 12 ErrorCode)
- [x] `docs/CURL.md` — создан (76 строк, known limitation описано)
- [x] `ARCHITECTURE.md` — обновлён (275 строк, confirm_required, persistence v3, legacy отмечен)
- [x] `README.md` — обновлён (132 строки, docker compose up, troubleshooting)
- [x] backend/app/routes/log_cards.py — существует
- [x] frontend/lib/curl-builder.ts — существует
- [x] 15 backend тестов — зелёные
- [x] 97 frontend тестов — зелёные
- [x] 0 TODO/FIXME/placeholder в docs
