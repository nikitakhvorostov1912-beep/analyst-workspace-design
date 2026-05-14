# ARCHITECTURE — 1С Аналитик

*Актуально: Phase 3 (Production Ready). Предыдущие фазы: see `.planning/phases/`.*

---

## High-level topology

```
┌────────────────────────────────────────────────────────────────┐
│ Browser (localhost:3010)                                        │
│                                                                 │
│  Next.js 15 App Router                                          │
│   ├─ app/layout.tsx              AppShell (header + sidebar)   │
│   ├─ app/page.tsx                главный чат                   │
│   ├─ app/sessions/[id]/page.tsx  история сессии                │
│   └─ components/                                                │
│      ├─ chat/    Thread · Message · AssistantMessage           │
│      │           ToolTrace · StreamingIndicator                │
│      │           ConfirmExecuteDialog · ConnectionStatusBanner │
│      ├─ cards/   TableCard · ObjectCard · LogCard              │
│      │           CardRenderer                                   │
│      ├─ shell/   Header · Sidebar · ChannelSelector · AppShell │
│      └─ ui/      shadcn primitives                             │
│                                                                 │
│  lib/  api.ts · sse.ts · types.ts · storage.ts · toast.ts      │
│        curl-builder.ts · json-tree.tsx · format-duration.ts    │
└──────────────────────────────────┬─────────────────────────────┘
                                   │ HTTP/SSE
                                   │ CORS: только BACKEND_ALLOWED_ORIGINS
┌──────────────────────────────────▼─────────────────────────────┐
│ FastAPI Backend (localhost:8010)                                │
│                                                                 │
│  routes/                                                        │
│   ├─ chat.py         POST /chat (SSE stream)                   │
│   │                  POST /chat/confirm (SEC-01)               │
│   ├─ sessions.py     GET/POST/PATCH/DELETE /sessions           │
│   │                  GET /sessions/{id}/messages               │
│   ├─ connections.py  CRUD /connections + POST /ping            │
│   ├─ log_cards.py    POST /sessions/{sid}/…/cards/{cid}/load-more │
│   ├─ mcp.py          POST /mcp/_/ping                          │
│   └─ health.py       GET /health                               │
│                                                                 │
│  orchestrator/                                                  │
│   ├─ loop.py         tool-calling loop (MAX 10 итераций)       │
│   ├─ events.py       SSE-модели + format_sse()                 │
│   ├─ cards.py        build_card_from_tool_result()             │
│   ├─ persistence.py  save/get sessions · messages · card_states│
│   ├─ safety.py       scan_for_dangerous() + asyncio.Event      │
│   └─ title.py        auto-title через LLM                      │
│                                                                 │
│  clients/                                                       │
│   ├─ llm.py          OpenAI-compat httpx streaming             │
│   └─ mcp.py          MCP Streamable HTTP + initialize          │
│                                                                 │
│  storage/                                                       │
│   ├─ db.py           aiosqlite init + lifespan                 │
│   └─ migrations.py   schema_version=3 (idempotent)             │
└─────────────────────┬─────────────────────┬─────────────────────┘
                      │                     │
              ┌───────▼────────┐    ┌──────▼─────────────────┐
              │ LLM Provider   │    │ 1С MCP Toolkit         │
              │ (configurable) │    │ (per channel)          │
              │                │    │                        │
              │ Xiaomi MiMo    │    │ EPF на :6010 / :6003   │
              │ OpenAI-compat  │    │ MCP Streamable HTTP    │
              │ X-LLM-API-Key  │    │ 10 инструментов        │
              └────────────────┘    └────────┬───────────────┘
                                             │
                                    ┌────────▼────────────────┐
                                    │ База 1С клиента         │
                                    └─────────────────────────┘
```

---

## Data flow: один запрос

```
[Browser]                                                [Backend]
───────────────────────────────────────────────────────────────
Пользователь: «Покажи 32 ОПП за 30.04 без шапки»

POST /chat {message, sessionId, channelId}
   + X-LLM-API-Key: sk-...
   + X-LLM-Endpoint / X-LLM-Model
   ────────────────────────────────────────────────────▶

   ◀── SSE: event=status {stage:"thinking"}

   ensure_session(), save_user_message()
   lookup_mcp_endpoint(channelId)
   MCPClient.initialize() → list_tools()
   LLMClient.stream_chat_completion(messages + tools)

   ◀── SSE: event=status {stage:"calling_tool"}
   ◀── SSE: event=tool_call {name:"execute_query", args:{...}}

   [опц.] scan_for_dangerous → event=confirm_required
          → ждать POST /chat/confirm

   MCPClient.call_tool("execute_query", args)

   ◀── SSE: event=tool_result {ok:true, result:{rows:[...]}}
   ◀── SSE: event=card {type:"table", payload:{...}}

   continue LLM with tool result

   ◀── SSE: event=status {stage:"formatting"}
   ◀── SSE: event=delta {content:"Нашёл 32 документа..."}
   ◀── SSE: event=done {message_id, total_duration_ms}

   save_assistant_message()  ← реальный message_id
   save_card_state() for каждой LogCard
   touch_session()
```

---

## SSE Events Matrix

| Event | Payload | Когда |
|-------|---------|-------|
| `status` | `{stage: "thinking"\|"calling_tool"\|"formatting"}` | Каждую итерацию loop |
| `tool_call` | `{id, name, args}` | LLM решила вызвать инструмент |
| `tool_result` | `{id, ok, result, error, duration_ms}` | После вызова MCP |
| `delta` | `{content}` | Текстовый фрагмент LLM |
| `card` | `{type, payload}` | Inline-карточка (table/object/log) |
| `done` | `{message_id, total_duration_ms}` | Стрим завершён |
| `error` | `{message, code, retry_after_s?}` | Ошибка, стрим закрыт |
| `confirm_required` | `{tool_call_id, name, args, reason}` | SEC-01: требует подтверждения |

**Итого: 8 events.**

---

## Error Codes

| Код | Источник |
|-----|---------|
| `llm_rate_limit` | LLM 429 |
| `llm_invalid_key` | LLM 401/403 |
| `llm_network_error` | httpx.RequestError |
| `llm_server_error` | LLM 5xx |
| `mcp_disconnected` | MCPDisconnectedError |
| `mcp_connect_error` | MCP init failed |
| `tool_loop_limit` | MAX_TOOL_ITERATIONS=10 |
| `unknown_channel` | channel_id не найден |
| `init_error` | ошибка инициализации |
| `internal_error` | непредвиденная ошибка |
| `user_declined` | пользователь нажал «Отменить» |
| `dangerous_keyword_blocked` | confirm timeout |

**Итого: 12 ErrorCode.**

---

## Persistence Layer (SQLite)

### Схема v3 (current)

```sql
-- v1: базовые таблицы
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  title TEXT,
  channel_id TEXT NOT NULL,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL,            -- user | assistant | tool
  content TEXT,
  tool_calls JSON,               -- [{id, name, args, result, error, duration_ms}]
  tool_call_id TEXT,
  cards JSON,                    -- [{type, payload}] snapshot
  created_at TIMESTAMP,
  duration_ms INTEGER
);

CREATE TABLE mcp_connections (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  endpoint TEXT NOT NULL,        -- http://localhost:6010/mcp
  channel TEXT,
  anon_enabled BOOLEAN DEFAULT 0,
  last_seen_at TIMESTAMP,
  created_at TIMESTAMP
);

CREATE TABLE llm_settings (
  id INTEGER PRIMARY KEY,
  endpoint TEXT NOT NULL,
  model TEXT NOT NULL,
  temperature REAL DEFAULT 0.3,
  max_tokens INTEGER DEFAULT 4096,
  updated_at TIMESTAMP
);

-- v2: индексы
CREATE INDEX idx_messages_session_created ON messages(session_id, created_at);
CREATE INDEX idx_sessions_updated ON sessions(updated_at DESC);

-- v3: card_states для LogCard load-more (Plan 03-04)
CREATE TABLE card_states (
  card_id TEXT PRIMARY KEY,      -- UUID4, хранится в card.payload.card_id
  session_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  tool_name TEXT NOT NULL,       -- "get_event_log"
  original_args TEXT NOT NULL,   -- JSON исходных аргументов
  channel_id TEXT NOT NULL,
  created_at TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

Миграции идемпотентны (`apply_migrations()`). Запускаются при старте backend.

---

## Security

| Механизм | Реализация |
|----------|-----------|
| API ключи | Только в localStorage браузера. Backend НЕ хранит. Forward через X-LLM-API-Key header |
| Confirm dialog (SEC-01) | scan_for_dangerous() на args execute_code → asyncio.Event пауза loop |
| CSP (SEC-02) | next.config.ts headers() в production. default-src 'self', connect-src backend-url |
| Pydantic strict (SEC-03) | Все Request models: `ConfigDict(extra="forbid", strict=True)` |
| CORS (SEC-04) | BACKEND_ALLOWED_ORIGINS env (fail-secure: пустой в prod = warning) |
| Ownership check | POST load-more: state.session_id == sid, state.message_id == mid |

---

## Frontend Architecture

```
app/
├── layout.tsx              AppShell + Toaster + CSP meta
├── page.tsx                main chat — useChatStream hook
└── sessions/[id]/page.tsx  история загружается fetchSessionMessages

lib/
├── api.ts          fetch wrappers (BACKEND = NEXT_PUBLIC_BACKEND_URL)
├── sse.ts          parseSSEStream — ReadableStream → AsyncIterable<SSEEvent>
├── types.ts        зеркало Pydantic models (SSEEvent, CardEnvelope, ...)
├── storage.ts      localStorage (LLMConfig, MCPConnections, activeChannelId)
├── toast.ts        publishToast() — CustomEvent "app:toast" → Toaster
├── curl-builder.ts buildCurlCommand(toolCall, mcpEndpoint) → shell string
├── json-tree.tsx   рекурсивный JSON renderer
└── format-duration.ts  мс → "1.2 сек" / "842 мс"
```

---

## Phase Summaries

| Фаза | Summary |
|------|---------|
| Phase 1 (Foundation) | `.planning/phases/01-foundation/PHASE-summary.md` |
| Phase 2 (MVP Chat) | `.planning/phases/02-mvp-chat/PHASE-summary.md` |
| Phase 3 Plan 01 | `.planning/phases/03-production-ready/03-01-SUMMARY.md` |
| Phase 3 Plan 02 | `.planning/phases/03-production-ready/03-02-SUMMARY.md` |
| Phase 3 Plan 03 | `.planning/phases/03-production-ready/03-03-SUMMARY.md` |
| Phase 3 Plan 04 | `.planning/phases/03-production-ready/03-04-SUMMARY.md` |

---

## Historical: legacy mockups

`mockups/_legacy/v0-object-ide/` — исторические макеты v0 (Object-IDE, tree + AI-rail).
`docs/_archive-v0-object-ide/` — архив документов v0 workflow-editor.
Не используются в текущей реализации.
