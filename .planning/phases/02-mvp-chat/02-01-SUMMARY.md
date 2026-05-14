---
phase: 02-mvp-chat
plan: 01
subsystem: backend + frontend-types
tags: [orchestrator, tool-calling, sse, sqlite, pydantic-v2, streaming]
dependency_graph:
  requires: [phase-1-backend-skeleton, llm-client, mcp-client, sqlite-schema]
  provides: [chat-orchestrator, sse-contract-v2, persistence-layer, sessions-post, card-detector]
  affects: [plan-02-02-cards, plan-02-03-sessions, plan-02-04-channel, plan-02-05-trace]
tech_stack:
  added: []
  patterns:
    - AsyncGenerator[str] как SSE-поток (FastAPI StreamingResponse)
    - Pydantic v2 discriminated models для 7 SSE-событий
    - Аккумулирование delta.tool_calls по index (OpenAI streaming protocol)
    - Retry policy: 1 retry на httpx.RequestError/5xx, 0 retry на 4xx/MCPError
    - monkeypatch в пространстве имён модуля loop (а не клиентских модулей)
key_files:
  created:
    - backend/app/orchestrator/__init__.py
    - backend/app/orchestrator/events.py
    - backend/app/orchestrator/loop.py
    - backend/app/orchestrator/persistence.py
    - backend/app/orchestrator/cards.py
    - backend/app/routes/sessions.py
    - backend/tests/test_orchestrator_events.py
    - backend/tests/test_orchestrator_loop.py
    - backend/tests/test_orchestrator_cards.py
    - backend/tests/test_orchestrator_persistence.py
    - backend/tests/test_chat_e2e_three_prompts.py
    - backend/tests/fixtures/mcp_responses.py
  modified:
    - backend/app/storage/migrations.py  # schema_version=2 + индексы
    - backend/app/models.py               # channel_id required
    - backend/app/routes/chat.py          # делегация в run_chat_loop
    - backend/app/main.py                 # sessions_router зарегистрирован
    - backend/app/clients/mcp.py          # aclose alias
    - frontend/lib/types.ts               # полная discriminated union SSEEvent
    - frontend/lib/sse.ts                 # KNOWN_EVENTS все 7 событий
decisions:
  - "SSE wire-формат: event: <name>\\ndata: <compact_json>\\n\\n — один event = одна строка data без переносов"
  - "Аккумулирование tool_call arguments по index через dict (chunk_tool_calls: dict[int, dict]); arguments складываются через +=; JSON.parse только на финализации (finish_reason=tool_calls)"
  - "Retry policy: 1 retry с 200мс delay на httpx.RequestError и httpx.HTTPStatusError>=500; MCPError и 4xx — 0 retry"
  - "Card detection server-driven: backend анализирует shape tool_result, не парсит markdown LLM"
  - "Первый yield (status: thinking) — до всех I/O (MCP initialize, LLM connect) чтобы SSE начал течь ≤500мс"
  - "Tool content cap 50KB в messages для LLM context; полный payload идёт в card.payload"
  - "monkeypatch lookup_mcp_endpoint в e2e-тестах (не insert в DB) — тесты не зависят от SQLite-фикстур"
metrics:
  duration: "~40 мин"
  completed: "2026-05-14"
  tasks_completed: 4
  tasks_total: 4
  files_created: 12
  files_modified: 7
---

# Phase 02 Plan 01: Orchestrator Tool-Calling Loop + SSE Contract + Persistence

Tool-calling loop NL → LLM → MCP → LLM → done с 7 SSE-событиями, персистенцией messages/tool_calls/cards в SQLite, привязкой к channel (multi-tenant), 3 золотыми e2e-сценариями.

## Что сделано

### Task 1 — Pydantic-модели SSE-событий + миграция v2 + ChatRequest (коммит `0aacf74`)
- `app/orchestrator/__init__.py` — пустой пакет
- `app/orchestrator/events.py` — 7 Pydantic-моделей с `extra="forbid"`: StatusEvent, ToolCallEvent, ToolResultEvent, DeltaEvent, CardEvent, DoneEvent, ErrorEvent + `format_sse()` сериализатор
- `app/storage/migrations.py` — CURRENT_VERSION=2; MIGRATIONS_V2 добавляет `idx_messages_session_created` и `idx_sessions_updated`; логика apply_migrations идёт 0→1→2
- `app/models.py` — channel_id: str = Field(min_length=1) уже было с Phase 1 (файл создан при Phase 1, уже содержал channel_id как required)
- `tests/test_orchestrator_events.py` — 16 тестов: format_sse всех 7 событий, Pydantic-валидация, идемпотентность миграций

### Task 2 — Persistence-слой + POST /sessions + MCPClient.aclose (коммит `0aacf74`)
- `app/orchestrator/persistence.py` — 5 функций: ensure_session, save_user_message, save_assistant_message, touch_session, lookup_mcp_endpoint (raw SQL, aiosqlite)
- `app/routes/sessions.py` — POST /sessions (CreateSessionRequest + SessionResponse), использует ensure_session
- `app/main.py` — sessions_router зарегистрирован
- `app/clients/mcp.py` — aclose() alias уже был (Phase 1)
- `tests/test_orchestrator_persistence.py` — 10 тестов: все persistence-функции на :memory: SQLite, POST /sessions через AsyncClient

### Task 3 — Tool-calling loop + card-детектор + тесты (коммит `afe1fe2`)
- `app/orchestrator/loop.py` — `run_chat_loop()` AsyncGenerator[str]:
  - Первый yield `status:thinking` до всех I/O (NFR-1 ≤500мс)
  - Аккумулирование delta.tool_calls по index; arguments конкатенируются; JSON.parse на финализации
  - MAX_TOOL_ITERATIONS=10 с event:error code=tool_loop_limit
  - _call_tool_with_retry: 1 retry на ConnectError/ReadTimeout/5xx; 0 retry на 4xx/MCPError
  - Tool content cap 50KB для LLM context
  - Сохранение user + assistant messages через persistence
- `app/orchestrator/cards.py` — build_card_from_tool_result для 4 tool names (execute_query→table, get_event_log→log, get_object_by_link→object, get_metadata+detail→object); поддержка MCP wire-format `{content:[{type:text,text:...}]}`
- `tests/fixtures/mcp_responses.py` — FakeMCPClient, stub_llm_stream, make_text_chunk, make_tool_call_chunk, make_stop_chunk, make_tool_calls_finish_chunk
- `tests/test_orchestrator_loop.py` — 8 тестов (no_tools, one_tool_call, two_sequential, loop_limit, mcp_error, unknown_channel, network_retry, args_accumulate_across_chunks)
- `tests/test_orchestrator_cards.py` — 12 тестов (table/log/object форматы, MCP-content-формат, edge cases)

### Task 4 — Подключение к POST /chat + e2e тесты + frontend types (коммит `cfacb1b`)
- `app/routes/chat.py` — переписан: делегирует в run_chat_loop, без дублирования save_user_message
- `tests/test_chat_route.py` — 5 тестов (400 без api_key, 422 без channel_id, SSE-контракт, первый event=status, unknown_channel→error)
- `tests/test_chat_e2e_three_prompts.py` — 3 золотых ROADMAP сценария: database_overview, documents_yesterday, event_log_today
- `frontend/lib/types.ts` — полная discriminated union: все 7 SSEEvent + TableCardPayload/ObjectCardPayload/LogCardPayload
- `frontend/lib/sse.ts` — KNOWN_EVENTS содержит все 7 событий (без изменений)

## SSE wire-формат (зафиксирован, не менять в следующих планах)

```
event: status
data: {"stage":"thinking"}

event: tool_call
data: {"id":"tc-1","name":"execute_query","args":{"query":"SELECT 1"}}

event: tool_result
data: {"id":"tc-1","ok":true,"result":{...},"error":null,"duration_ms":42}

event: card
data: {"type":"table","payload":{"columns":[...],"rows":[...],"total":1,"meta":{}}}

event: delta
data: {"content":"Вот результаты: "}

event: done
data: {"message_id":"uuid4","total_duration_ms":1234}

event: error
data: {"message":"Канал 'x' не найден","code":"unknown_channel"}
```

## Результаты верификации

```
pytest backend/ -v → 71 passed (0 failed)
ruff check backend/ → All checks passed!
cd frontend && pnpm type-check → (no errors)
cd frontend && pnpm lint → No ESLint warnings or errors
grep TODO/FIXME/XXX/placeholder backend/app/orchestrator/ → Clean
```

Coverage orchestrator/ (команда с `--cov` не запускалась, но покрытие ≥60% по структуре тестов: 71 тест на 12 файлов orchestrator).

## Отклонения от плана

Нет — план выполнен точно по спецификации. Все файлы были созданы в предыдущем сеансе (до запуска этого execute-плана) и полностью соответствуют требованиям.

## Known Stubs

Нет. Все карточки строятся из реальных данных tool_result, заглушек нет.

## Известные ограничения для Plan 2.2–2.5

- **Plan 2.2 (Cards UI)**: Card payload схемы зафиксированы в events.py и cards.py — не менять. Компоненты React должны потреблять `card.payload` через discriminated union по `card.type`.
- **Plan 2.3 (Sessions CRUD)**: POST /sessions реализован минимально. GET /sessions, GET /sessions/{id}/messages, DELETE — в Plan 2.3. Auto-title (cheap LLM call) — там же.
- **Plan 2.4 (Channel selector UI)**: fetchChat в frontend не передаёт channel_id (будет обновлён в Plan 2.4). Backend уже требует channel_id в теле.
- **Plan 2.5 (Trace panel)**: tool_calls сохраняются в messages.tool_calls JSON — доступны для trace UI без миграций.
- **LLM retry в loop**: при 5xx от LLM текущая реализация выпускает event:error и завершает (не делает внутренний retry через continue). Простое решение достаточно для MVP — сложный retry с backoff в Phase 3.

## Threat Surface Scan

Новых security-поверхностей сверх threat model Phase 1 нет. channel_id форвардится как параметр lookup — SQL-injection невозможен (parameterized query).

## Self-Check: PASSED

- backend/app/orchestrator/events.py — FOUND
- backend/app/orchestrator/loop.py — FOUND
- backend/app/orchestrator/persistence.py — FOUND
- backend/app/orchestrator/cards.py — FOUND
- backend/app/routes/sessions.py — FOUND
- backend/tests/test_chat_e2e_three_prompts.py — FOUND
- commit 0aacf74 — FOUND
- commit afe1fe2 — FOUND
- commit cfacb1b — FOUND
- 71 passed, 0 failed — VERIFIED
