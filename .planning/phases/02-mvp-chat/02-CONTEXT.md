# Phase 2: MVP Chat — Context

**Gathered:** 2026-05-14
**Status:** Ready for planning
**Source:** Direct extraction from ROADMAP.md + REQUIREMENTS.md (yolo mode, discuss-phase skipped — пользователь явно сказал «продолжай полноценно»)

<domain>
## Phase Boundary

Что эта фаза доставляет:
- **End-to-end chat работает с реальной 1С**: пользовательский вопрос на NL → backend оркестрирует tool-calling loop (LLM ↔ MCP) → ответ с inline-карточкой (Table / Object / Log) + trace
- **Sessions**: история сохраняется в SQLite, отображается в sidebar grouped by date, переключение каналов (баз 1С)
- **Trace panel**: под каждым ответом видны вызванные tools и их результаты

Что эта фаза НЕ доставляет (deferred):
- Error states (MCP disconnected, LLM rate limit, retry-after) — Phase 3
- Анонимизация — Phase 3
- E2E Playwright, 80% coverage — Phase 3
- Quick prompts, slash-commands, @-mentions, Cmd-K — Out of Scope для MVP
- TRACE-03 (Copy as curl) — Phase 3

Вход в Phase 2 (что уже работает после Phase 1):
- Backend skeleton: GET /health, POST /chat (SSE), POST /mcp/{id}/ping, SQLite миграции 5 таблиц включая `mcp_connections` + `llm_settings` + `sessions` + `messages` + `cards`
- Frontend skeleton: AppShell, тёмная тема, IBM Plex, lib/api.ts, lib/sse.ts, lib/storage.ts
- LLM-клиент с streaming, MCP-клиент с Mcp-Session-Id
- SSE контракт: `event: <name>\ndata: <json>\n\n` — events `status`, `delta`, `done`, `error`

</domain>

<decisions>
## Implementation Decisions

### Mode
- **MVP mode (vertical slices)**: каждый план — конец-в-конец фича через все слои (UI → API → DB). НЕ horizontal split (всё API сначала, потом всё UI).
- Источник: ROADMAP.md Phase 2 `**Mode:** mvp`.

### Orchestrator (Plan 2.1)
- **Tool-calling loop**: NL → LLM → tool_call → MCP → result → LLM → … → done. Поддержка множественных tool calls в одном ответе (CHAT-04, до 2-3 последовательных).
- **SSE events расширяются**: к `status`/`delta`/`done`/`error` (из Phase 1) добавляются `tool_call` (когда LLM решает вызвать tool), `tool_result` (когда MCP вернул), `card` (когда детектирован inline-card).
- **Card detection**: парсер ответа LLM ищет fenced JSON-блоки определённой структуры ИЛИ events `card` от backend. Решение: используем events `card` от backend (server-driven), это надёжнее чем парсинг markdown.
- **Persistence**: каждое сообщение (user/assistant), каждый tool_call (input/output/duration), каждая card — сохраняется в SQLite сразу при completion.
- **Streaming требования**: первый chunk ≤ 500 мс (NFR-1 наследуется), повторение каждые ≤ 200 мс.
- **Limits**: один request → до 10 tool calls в loop (safety net), max 50 KB суммарной payload tools.

### Cards (Plan 2.2)
- **3 типа**: TableCard, ObjectCard, LogCard. Только эти три в Phase 2 (CARD-04..06 deferred к v2).
- **TableCard**: пагинация (50 строк / страница), сортировка по любой колонке (client-side для ≤ 1000 строк), экспорт CSV (download).
- **ObjectCard**: header (имя, тип, путь по метаданным) + 4 секции — реквизиты / табличные части / формы / макеты. Из get_metadata(detail=full) или get_object_by_link.
- **LogCard**: timeline записей с уровнями (Info/Warning/Error/Critical), цветовая разметка, курсор-пагинация (load more).
- **Источник данных карточек**: backend строит card payload и шлёт через SSE event `card` с JSON содержимым; frontend рендерит соответствующий компонент по `card.type`.
- **Markdown в TL;DR**: только safe markdown (react-markdown + remark-gfm), без HTML.

### Sessions (Plan 2.3)
- **REST endpoints**: `POST /sessions` (создание), `GET /sessions` (список с group_by_date), `GET /sessions/{id}` (полная история), `DELETE /sessions/{id}`, `GET /sessions/{id}/messages`.
- **Auto-title**: после первого сообщения user → cheap LLM call (gpt-4o-mini class или эвристика: первые 5-7 слов до знака препинания); fallback на «Новый чат» если LLM недоступен.
- **URL routing**: `/sessions/{id}` через App Router dynamic segment; `/` ведёт на актуальную сессию или empty state.
- **Sidebar groups**: Сегодня / Вчера / На этой неделе / Раньше. Сортировка внутри группы — по `updated_at` DESC.
- **Persistence**: SQLite таблицы `sessions`, `messages` уже есть в migrations (Phase 1).

### Channel Selector (Plan 2.4)
- **Header dropdown**: shadcn DropdownMenu, показывает name + green/red dot статуса (last ping). Refresh статуса вручную (кнопка «↻») и при открытии dropdown.
- **Switching effect**: меняет `activeChannelId` в Zustand store (или React context), persistance в localStorage. Текущий чат при switch — обнуляется (новый /sessions URL).
- **Tools schema reload**: при switching backend получает `?channelId=` параметр в `/chat` и инициализирует MCP-сессию для соответствующего connection.
- **Min connections to function**: ≥ 1; если 0 — empty state «Настроить подключение» (STATE-01 наследуется из Phase 1).

### Trace Panel (Plan 2.5)
- **Под каждым assistant сообщением**: collapsed строка `▸ N tools, X мс` (если tools были вызваны); если 0 — не показывать.
- **Expanded view**: список вызовов:
  - Каждый row: tool name, args (JSON tree component, фолд по умолчанию), result (collapsed, expand on click), duration, error если был
  - Используем `lib/json-tree.tsx` (новый компонент с минимальным API: name+value, рекурсия, colored types)
- **Persistence**: tool_calls хранятся в DB (привязка к message_id), при загрузке истории — восстанавливаются.
- **TRACE-03 (curl)**: НЕ в Phase 2 — отложено на Phase 3.

### Stack additions (over Phase 1)
- Backend: ничего нового; используем existing httpx, FastAPI streaming.
- Frontend: `react-markdown` + `remark-gfm` для TL;DR; никаких новых state libs (Zustand можно добавить если context провисает).
- Никаких ORM поверх aiosqlite; raw SQL остаётся.

### Claude's Discretion
- Конкретный JSON-schema для cards events — на усмотрение планера, но обязан быть документирован в первом плане где появляется (Plan 2.1) и переиспользован в Plan 2.2.
- Структура tool_call event payload — на усмотрение планера.
- Стратегия retry / exponential backoff на LLM/MCP ошибки — определить, документировать в Plan 2.1. Default: 1 retry на network errors, 0 retry на 4xx.
- Расположение «+ Новый чат» кнопки — sidebar top или header. Default: sidebar top, как в Claude/ChatGPT.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project documentation (must-read)
- `PROJECT.md` — vision, концепция (chat-first, аналог ChatGPT для 1С)
- `ARCHITECTURE.md` — топология frontend ↔ backend ↔ LLM/MCP
- `REQUIREMENTS.md` — все REQ-IDs (CHAT-01..05, CARD-01..03, HIST-01..04, TRACE-01..02, CONN-03)
- `ROADMAP.md` — Phase 2 секция с success criteria
- `CLAUDE.md` — workflow одного запроса, явные баны, стек
- `docs/00b-mcp-capability-map.md` — actual MCP tools (10 операций 1С MCP Toolkit v1.7.0)

### Phase 1 artifacts (контракты, на которых строимся)
- `.planning/phases/01-foundation/01-01-SUMMARY.md` — backend контракты (SSE event format, header X-LLM-API-Key, ChatRequest snake_case)
- `.planning/phases/01-foundation/01-02-SUMMARY.md` — frontend контракты (lib/api.ts, lib/sse.ts, lib/storage.ts)
- `.planning/phases/01-foundation/VERIFICATION.md` — что реально работает после Phase 1

### Existing code to integrate with (важнейшие точки)
- `backend/app/routes/chat.py` — текущий SSE-генератор; Phase 2 расширяет его tool-calling loop
- `backend/app/clients/llm.py` — `LLMClient.stream_chat_completion(messages, tools, api_key)` — `tools` параметр уже в сигнатуре, но не используется
- `backend/app/clients/mcp.py` — `MCPClient.initialize/list_tools/call_tool`
- `backend/app/storage/migrations.py` — таблицы `sessions/messages/cards` уже есть
- `frontend/lib/sse.ts` — `parseSSEStream` принимает `KNOWN_EVENTS` runtime-проверку → расширить
- `frontend/lib/api.ts` — `fetchChat` использует только X-LLM-API-Key; mcp ping готов

### Out-of-Scope (что НЕ делать в Phase 2)
- Error states баннеры (MCP disconnected, LLM rate limit) — Phase 3
- Анонимизация — Phase 3
- TRACE-03 «Copy as curl» — Phase 3
- E2E Playwright, 80% coverage — Phase 3
- Quick prompts / slash commands / @-mentions / Cmd-K / Export — Out of Scope (v2+)
- Theming, mobile, multi-user — Out of Scope (Out of Scope в REQUIREMENTS.md)

</canonical_refs>

<specifics>
## Specific Ideas

### SSE event matrix (для контракта Plan 2.1)
| event | data | когда |
|-------|------|-------|
| `status` | `{stage: "thinking"|"calling_tool"|"formatting"}` | каждый раз при смене стадии |
| `tool_call` | `{id, name, args}` | LLM решила вызвать tool |
| `tool_result` | `{id, ok, result?, error?, duration_ms}` | MCP вернул |
| `delta` | `{content: "<chunk>"}` | LLM генерит текст |
| `card` | `{type: "table"|"object"|"log", payload: {...}}` | backend сформировал inline card |
| `done` | `{message_id, total_duration_ms}` | финал ответа |
| `error` | `{message, code}` | ошибка orchestrator/LLM/MCP |

### 3 test prompts (acceptance из ROADMAP)
1. «Расскажи про базу» → TableCard или ObjectCard
2. «Покажи документы ОПП за вчера» → TableCard с реальными строками
3. «Что в журнале сегодня» → LogCard

Для CI/dev — должна быть возможность запустить эти 3 prompt через `pytest -k "test_e2e_three_prompts"` с замоканными MCP/LLM (respx).

### Plan 2.1 первый шаг
Tool-calling loop из ROADMAP описан как линейная цепочка. На практике LLM endpoint OpenAI-compat возвращает `tool_calls` в `choices[0].message.tool_calls` при non-streaming, ИЛИ в `delta.tool_calls` при streaming с накоплением. План должен явно описать как накапливать `tool_calls` из chunks и в какой момент пробрасывать `event: tool_call`.

### Plan 2.2 ↔ Plan 2.1 контракт
TableCard payload должен включать: `columns: [{name, type}]`, `rows: [[...]]`, `total: int`, `meta: {query?, duration_ms?}`. ObjectCard: `header: {name, type, path}`, `attributes: [...]`, `tabular_sections: [...]`, `forms: [...]`, `templates: [...]`. LogCard: `entries: [{time, level, user, event, comment?}]`, `next_cursor?`.

### Plan 2.3 group_by_date алгоритм
Группировка в backend (SQL):
- Сегодня: `DATE(updated_at) = DATE('now', 'localtime')`
- Вчера: `DATE(updated_at) = DATE('now', 'localtime', '-1 day')`
- На этой неделе: `DATE(updated_at) >= DATE('now', 'localtime', '-7 days')` AND NOT in (Today/Yesterday)
- Раньше: всё что старше

Frontend получает уже сгруппированный JSON `{today: [...], yesterday: [...], this_week: [...], earlier: [...]}`.

### Plan 2.4 ping schedule
Health-check MCP подключений: на mount Dropdown — параллельный fetch `/mcp/{id}/ping` для всех. Не background poller (избыточно). Кнопка «↻» — ручной refresh.

### Plan 2.5 JSON tree component
Минимальный API:
```tsx
<JsonTree value={anyJson} defaultExpanded={1} />
```
- Объекты/массивы collapsible
- Strings: цвет green
- Numbers: цвет orange
- Booleans/null: цвет purple
- Keys: цвет text-fg-muted

</specifics>

<deferred>
## Deferred Ideas

- **STATE-02 / STATE-03** (MCP disconnected банер, LLM rate limit) → Phase 3
- **TRACE-03** (Copy as curl) → Phase 3
- **ANON-** (анонимизация) → Phase 3 / v2
- **CARD-04..06** (Metric, References, Code cards) → v2
- **PROD-** (quick prompts, slash commands, @-mentions, Cmd-K, Export) → Out of Scope (v2+)
- **SEC-01..04** (confirm dialog, CSP, strict validation, CORS lockdown) → Phase 3
- **DEVX-02, DEVX-03** (E2E Playwright, GitHub Actions) → Phase 3

</deferred>

---

*Phase: 02-mvp-chat*
*Context gathered: 2026-05-14 — yolo mode, direct extraction from project artifacts*
