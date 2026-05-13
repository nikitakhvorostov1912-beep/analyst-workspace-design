# ARCHITECTURE — 1С Аналитик

## High-level topology

```
┌────────────────────────────────────────────────────────────────┐
│ Browser (localhost:3010)                                        │
│                                                                 │
│  Next.js 15 App Router                                          │
│   ├─ app/layout.tsx       — AppShell (header + sidebar + main) │
│   ├─ app/page.tsx         — main chat                          │
│   ├─ app/settings/        — LLM + MCP connections              │
│   └─ components/                                                │
│      ├─ ChatThread        — messages stream                    │
│      ├─ ChatInput         — textarea + @-mentions + commands   │
│      ├─ Card{Table,Object,Log,Metric,References,Code}          │
│      ├─ ToolTrace         — collapsible "▸ N tool calls"       │
│      ├─ ChannelSelector   — multi-tenant dropdown              │
│      └─ ModelBadge        — Xiaomi MiMo / others               │
└──────────────────────────────────┬─────────────────────────────┘
                                   │ HTTP/SSE
                                   │ (CORS allowed only localhost)
┌──────────────────────────────────▼─────────────────────────────┐
│ FastAPI Backend (localhost:8010)                                │
│                                                                 │
│  app/main.py                                                    │
│   ├─ /chat               POST SSE        — orchestrator        │
│   ├─ /sessions           CRUD            — session storage     │
│   ├─ /connections        CRUD            — MCP endpoints       │
│   ├─ /llm                POST validate   — test API key        │
│   └─ /mcp/{conn_id}/ping GET             — health check        │
│                                                                 │
│  app/orchestrator.py     — main loop                            │
│   1. load tools schema for active channel                       │
│   2. stream LLM completion with function-calling enabled        │
│   3. on tool_call → invoke MCP → append to messages             │
│   4. continue LLM until natural stop                            │
│   5. emit SSE events: status, tool_call, result, content        │
│                                                                 │
│  app/clients/                                                   │
│   ├─ llm.py              — OpenAI-compat httpx client           │
│   └─ mcp.py              — MCP Streamable HTTP client           │
│                                                                 │
│  app/storage/                                                   │
│   ├─ db.py               — SQLite via aiosqlite                 │
│   ├─ sessions.py         — sessions / messages                  │
│   ├─ connections.py      — MCP endpoints                        │
│   └─ settings.py         — LLM config (no api keys)             │
└─────────────────────┬─────────────────────┬─────────────────────┘
                      │                     │
              ┌───────▼────────┐    ┌──────▼─────────────────┐
              │ LLM Provider   │    │ 1С MCP Toolkit         │
              │ (configurable) │    │ (one per channel)      │
              │                │    │                        │
              │ Xiaomi MiMo    │    │ EPF в 1С :6010 / :6003 │
              │ OpenAI-compat  │    │ HTTP Streamable        │
              │ sk-... key     │    │ 10 tools               │
              │                │    │                        │
              └────────────────┘    └────────┬───────────────┘
                                             │
                                    ┌────────▼────────────────┐
                                    │ База 1С клиента         │
                                    │ (Информационная база)   │
                                    └─────────────────────────┘
```

## Data flow: один запрос юзера

```
[Browser]                                                   [Backend]
─────────                                                   ────────
ChatInput.send("покажи 32 ОПП без шапки")
   │
   │  POST /chat
   │  { message, sessionId, channelId }
   ├──────────────────────────────────────────────────────▶ /chat handler
                                                            │
                                                            │ load session messages from SQLite
                                                            │ load MCP tools schema for channelId
                                                            │ build LLM payload {system, history, tools}
                                                            │
                                                            ├──▶ stream LLM (function calling)
                                                            │
                                                            │ ◀── chunk: tool_call="execute_query"
                                                            │     args={"query":"ВЫБРАТЬ ...", limit:100}
                                                            │
   ◀── SSE: event=tool_call name="execute_query" args={...}
                                                            │
                                                            ├──▶ POST MCP /api/execute_query
                                                            │
                                                            │ ◀── {"success":true, "data":[32 rows]}
                                                            │
   ◀── SSE: event=tool_result name="execute_query" rows=32
                                                            │
                                                            ├──▶ continue LLM with tool result
                                                            │
                                                            │ ◀── chunk: "Нашёл 32 документа..."
   ◀── SSE: event=delta content="Нашёл 32 ..."
                                                            │ ◀── chunk: "[render Table card]"
   ◀── SSE: event=card type="table" payload={...}
                                                            │ ◀── stop
   ◀── SSE: event=done
                                                            │
                                                            │ save messages to SQLite
                                                            ▼
[Browser]
ChatThread renders: TL;DR text + Table card
                  + collapsed ToolTrace ("▸ 1 tool: execute_query 134ms")
```

## Storage Schema (SQLite)

```sql
-- Sessions (chat threads)
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,            -- UUID v4
  title TEXT,                     -- auto-generated from first message
  channel_id TEXT NOT NULL,       -- which MCP connection
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Messages within sessions
CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL,             -- user | assistant | tool
  content TEXT,                   -- markdown or null for tool
  tool_calls JSON,                -- when role=assistant with tool calls
  tool_call_id TEXT,              -- when role=tool
  cards JSON,                     -- rendered inline cards (table/object/...)
  created_at TIMESTAMP,
  duration_ms INTEGER             -- for assistant messages
);

-- MCP connections (multi-tenant)
CREATE TABLE mcp_connections (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,             -- "Русский Транзит prod"
  endpoint TEXT NOT NULL,         -- http://localhost:6010/mcp
  channel TEXT,                   -- ?channel=... param
  anon_enabled BOOLEAN DEFAULT 0,
  last_seen_at TIMESTAMP,
  created_at TIMESTAMP
);

-- LLM settings (only metadata, NOT keys — keys в localStorage)
CREATE TABLE llm_settings (
  id INTEGER PRIMARY KEY,
  endpoint TEXT NOT NULL,         -- https://api.xiaomi.com/v1
  model TEXT NOT NULL,            -- mimo-32b
  temperature REAL DEFAULT 0.3,
  max_tokens INTEGER DEFAULT 4096,
  -- api_key стораджится только в frontend localStorage,
  -- forward'ится с каждым /chat запросом через header
  updated_at TIMESTAMP
);
```

## Key Design Decisions

### 1. API ключи только в localStorage браузера
**Why:** безопасность. Backend никогда не персистит ключи. Каждый /chat запрос содержит ключ в header `X-LLM-API-Key`. Backend форвардит к LLM provider'у и забывает.

**Tradeoff:** ключ загружается при каждой странице. Решается через secure storage browser API или crypto.subtle для encryption-at-rest.

### 2. SSE для streaming, не WebSocket
**Why:** SSE проще (unidirectional), достаточно для chat. WebSocket нужен только для realtime collaboration — это вне MVP.

### 3. Один MCP endpoint = один channel
**Why:** аналитик подключает базы клиентов индивидуально. Channel selector в header — это просто переключение `connection_id`.

### 4. LLM tools schema генерится из MCP capabilities
**Why:** не дублируем определения tools. Backend при init дёргает `tools/list` к MCP, конвертирует в OpenAI function calling format.

### 5. Metadata cache в SQLite на стороне backend
**Why:** `get_metadata` запросы могут быть медленными для больших конфигураций. Кэш с TTL (1 час) + manual invalidation через UI кнопку.

### 6. Анонимизация — pass-through
**Why:** анонимизация делается на стороне MCP Toolkit (EPF в 1С). Backend только устанавливает заголовок / parameter, ответ MCP уже anonymized. `submit_for_deanonymization` вызывается явно через UI toggle.

## Module Layout

```
backend/
├── pyproject.toml
├── app/
│   ├── __init__.py
│   ├── main.py                 ← FastAPI app + routes
│   ├── config.py               ← env, defaults
│   ├── models.py               ← Pydantic models (Session, Message, ...)
│   ├── orchestrator.py         ← chat orchestration loop
│   ├── clients/
│   │   ├── llm.py              ← OpenAI-compat client
│   │   └── mcp.py              ← MCP Streamable HTTP client
│   ├── storage/
│   │   ├── db.py               ← aiosqlite init + migrations
│   │   ├── sessions.py
│   │   ├── messages.py
│   │   ├── connections.py
│   │   └── settings.py
│   └── routes/
│       ├── chat.py
│       ├── sessions.py
│       ├── connections.py
│       ├── settings.py
│       └── health.py
└── tests/
    ├── test_orchestrator.py
    ├── test_mcp_client.py
    └── test_llm_client.py

frontend/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── app/
│   ├── layout.tsx              ← AppShell (header + sidebar + main)
│   ├── page.tsx                ← /chat (главный экран)
│   ├── settings/
│   │   ├── page.tsx
│   │   ├── llm/page.tsx        ← LLM endpoint + key + model
│   │   └── connections/page.tsx ← MCP endpoints CRUD
│   └── api/                    ← (опц.) Next.js API routes для proxy
├── components/
│   ├── chat/
│   │   ├── thread.tsx
│   │   ├── input.tsx
│   │   ├── message.tsx
│   │   └── trace.tsx
│   ├── cards/
│   │   ├── table.tsx
│   │   ├── object.tsx
│   │   ├── log.tsx
│   │   ├── metric.tsx
│   │   ├── references.tsx
│   │   └── code.tsx
│   ├── shell/
│   │   ├── header.tsx
│   │   ├── sidebar.tsx
│   │   ├── channel-selector.tsx
│   │   └── model-badge.tsx
│   └── ui/                     ← shadcn primitives
├── lib/
│   ├── api.ts                  ← fetch wrappers
│   ├── sse.ts                  ← SSE event parsing
│   ├── storage.ts              ← localStorage (api keys, prefs)
│   └── types.ts                ← shared types
└── tests/
```

## Security Considerations

- API ключи → localStorage only, never backend storage
- MCP endpoints — обычно localhost, но при self-host надо authenticate
- CORS — backend разрешает только `http://localhost:3010` в dev, configurable для prod
- Content Security Policy — Strict
- Input validation — Pydantic на backend, Zod на frontend
- BSL `execute_code` — dangerous keywords blocked by MCP, UI должен ещё раз confirm

## Performance Targets

- `/chat` first byte (SSE start): ≤ 500 мс
- Tool call roundtrip (LLM → MCP → LLM): ≤ 3 сек (зависит от tool)
- Metadata cache TTL: 1 час
- Concurrent sessions per backend: 10 (single-user)
- Sessions retention: до 1000 в SQLite

## Deployment (later)

- Dev: `docker compose up`
- Prod: self-host через Docker Compose, no SaaS в MVP
