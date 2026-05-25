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

---

## Updates after M-K0 Stabilization (2026-05-25)

Этот раздел добавляет описание новых модулей и существенных изменений
поверх описанного выше. См. `.planning/knowledge-layer-2026-05-24/phases/
M-K0-stabilization/` для детального audit + summary.

### Новые модули backend

| Модуль | Назначение | Когда добавлен |
|---|---|---|
| `backend/app/storage/pool.py` | ConnectionPool из 5 aiosqlite соединений + acquire/release context manager. WAL + busy_timeout=10s. Для :memory: схлопывается до 1 conn. | M-K0.3 PERF-1 |
| `backend/app/context.py` | session_id_var + request_id_var (ContextVar) + ContextFilter logging filter. Используется для structured logs (per-request тэгирование). | M-K0.6 ARCH-2 |
| `backend/app/security/mcp_endpoint_validator.py` | SSRF guard для пользовательского MCP endpoint: scheme whitelist, hostname/IP блокировка приватных/loopback/link-local/multicast/reserved через `ipaddress` модуль. Localhost разрешён. | M-K0.1 SEC-1 |
| `backend/app/orchestrator/safety.py` *(модификация)* | `_pending` использует `asyncio.Future` вместо `Event` + сохраняет loop для `call_soon_threadsafe` (thread-safe resolve из другого worker'а). | M-K0.2 BE-1 |
| `backend/app/orchestrator/clarify.py` *(модификация)* | Аналогично BE-1 — Future + `call_soon_threadsafe` для thread-safe ответа на pending clarify. | M-K0.2 BE-1 |

### Изменения flow

**SQLite connection lifecycle (PERF-1, M-K0.3):**
```
Старо: app.state.db = aiosqlite.Connection (один thread queue на всё)
Ново:  app.state.db_pool = ConnectionPool(size=5)
       get_db dependency → async with pool.acquire() as conn → yield
       app.state.db = primary (backward-compat для прямых обращений)
```

**LLMClient lifecycle (PERF-2, M-K0.3):**
```
Старо: новый LLMClient(endpoint, model) ВНУТРИ while True цикла итераций
Ново:  один LLMClient ДО outer try, переиспользуется на всех итерациях,
       закрывается в outer finally
```

**SSE request_id трассировка (ARCH-2, M-K0.6):**
```
Middleware (_request_id_middleware) на каждый incoming HTTP request →
  request_id_var.set(uuid12 или incoming X-Request-Id) →
    все logger.* внутри получают request_id в JSON-поле "request"
      (через ContextFilter)
        response.headers["X-Request-Id"] устанавливается для downstream
```

### System prompt расширения (M-K0.4 Wave 3 Prompts)

`SYSTEM_PROMPT` в `loop.py` получил три новых блока:

1. **«Эспертная база знаний 1С»** — антипаттерны запросов + BSL правила + типы метаданных
2. **«ПРИМЕРЫ ВЫБОРА TOOL (few-shot)»** (PROMPT-1) — 19 примеров «Q → A: <tool>()» + 4 анти-паттерна. Decision tree для 8 классов tools.
3. **«ПАМЯТЬ (memory_append / memory_remove) — КОГДА ЗАПИСЫВАТЬ»** (PROMPT-3) — 6 правил с примерами: read first, when append, when NOT append, when remove, namespaces, anti-patterns.

`SYSTEM_PROMPT` теперь ~24.5k символов (под лимитом 25k, см. `test_system_prompt_*` тесты).

### Frontend изменения

| Модуль | Что | Когда |
|---|---|---|
| `frontend/lib/config-cache.tsx` | React Context кэш для `llm-config` + `connections` с invalidate. Раньше каждый send делал 2 лишних HTTP roundtrip (`-100..300мс/msg`). | M-K0.3 PERF-3 |
| `frontend/styles/design-tokens.css` *(модификация)* | Universal `@media (prefers-reduced-motion: reduce)` kill switch (FE-1). Solid colors для `--fg-2/3/4` в light theme — WCAG AA contrast (FE-3, ratio 4.7..12.4:1). | M-K0.5 FE-1/3 |
| `desktop/main.js` *(модификация)* | CSP + sandbox + webSecurity для всех окон (SEC-2). `shell:open-path` whitelist через `app.getPath('userData')`/`logs` (SEC-5). `setWindowOpenHandler` deny + `will-navigate` guard. SemverGt downgrade attack guard в `updater:install` handler (DEVOPS-5). | M-K0.1 SEC-2/5, M-K0.7 DEVOPS-5 |

### Verification metric updates (2026-05-25 после M-K0.1-0.7)

- **Backend pytest:** **~970 passed** (847 base + ~123 новых от M-K0 = 31 SSRF + 6 SQL validator + 1 rate-limit + 2 deprecation + 6 homoglyph + 6 SEC-3 + 11 pool + 8 context + 17 tool_selection + 10 memory_recall + остальные мелкие). 0 регрессий. 1 deselected (test_chat_llm_429_returns_rate_limit_with_retry_after_s — pre-existing SSRF/DNS issue от Windows resolver, не от M-K0).
- **Backend coverage (на критичных модулях):** loop.py 81%+ сохраняется, новые pool.py + context.py покрыты 100% базовыми тестами.
- **Frontend vitest:** **322 / 322 passed** (42 файла) — +1 файл `config-cache.test.tsx` (7 новых тестов).
- **Backend file sizes (post M-K0.1-0.7):**
  - `loop.py` ~1835 строк (vs 870 → 689 в P1.2; PROMPT-1+PROMPT-3+ARCH-2 + few-shot блоки добавили ~250 строк)
  - `pool.py` 155 строк (новый)
  - `context.py` 60 строк (новый)
  - `mcp_endpoint_validator.py` 218 строк (новый)
- **Branch:** `feature/m-k0-stabilization` — ~25 commits, готов к merge после Wave 6 + M-K0.8 (coverage push) + M-K0.9 (re-audit) + M-K0.10 (summary).

### Связь с M6 Quality Expansion

`.planning/handoff/m6-quality-expansion/` (12 файлов handoff от параллельной
сессии) интегрирован через:

- `.planning/milestones/M6-INTEGRATED-PLAN.md` — unified roadmap M-K + M6
- `.planning/milestones/INTEGRATION-DECISIONS.md` — 22 решения, 6 user
  resolutions (Q1=C подсистема+АП_, Q2=D 5 типовых, Q3=A EPF first,
  Q4=C MetaVision spike, Q6=C Dual license, Q-NEW=B Напарник primary)
- `.planning/milestones/AUDIT-GAPS.md` — найдены 15 gap'ов после ревизии,
  привязаны к M-K1..M-K5 фазам через 13 новых задач (G1-G15)

После M-K0 (commerce baseline) → M-K1 (Multi-MCP Orchestrator + Capabilities) →
M-K2 (Triple RAG: v8std + БСП + .hbk) → M-K3 (EPF/CFE delivery, BSL LS live) →
M-K4 (MetaVision graph + Activity Stream/Posting Trace) → M-K5 (Distribution
v2.0 + 8.5-Ready Assessment as paid service) → M-K6 (NL2SQL + Enterprise).
