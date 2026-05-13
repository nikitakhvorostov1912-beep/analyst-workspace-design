# ROADMAP — 1С Аналитик

> GSD-style phased roadmap. Каждая phase = atomic deliverable + acceptance criteria.

## Milestones

```
M1 — Foundation              (1 неделя)
   ↓
M2 — MVP Chat                (2 недели)
   ↓
M3 — Production Ready        (1 неделя)
   ↓
M4 — Demo & Refine           (1 неделя)
```

---

## Milestone 1 — Foundation

**Goal:** инфраструктура — backend + frontend booting, SQLite, базовая интеграция с MCP и LLM.

### Phase 1.1 — Backend Skeleton
- FastAPI app, routes scaffolding, Pydantic models
- SQLite через aiosqlite, migrations
- pyproject.toml + ruff + pytest
- Dockerfile + docker-compose.yml (backend only)

**Acceptance:** `docker compose up backend` → `GET /health` returns 200.

### Phase 1.2 — Frontend Skeleton
- Next.js 15 + Tailwind 4 + shadcn/ui init
- AppShell (header + sidebar + main + bottom)
- Тёмная тема, IBM Plex шрифты, русский UI
- API client (lib/api.ts) с типизацией

**Acceptance:** `pnpm dev` → главная страница рендерится с AppShell + dummy chat thread.

### Phase 1.3 — LLM Client + Tool Calling Loop
- OpenAI-compat httpx client с streaming
- Function calling parser (tool_calls в response)
- Smoke test: minimal chat без MCP (just LLM)

**Acceptance:** `POST /chat` с тестовым сообщением → SSE stream с content chunks.

### Phase 1.4 — MCP Client
- HTTP Streamable transport
- `initialize` → session ID
- `tools/list` → schema discovery
- `tools/call` → invoke
- Health check endpoint

**Acceptance:** `POST /mcp/{id}/ping` → возвращает MCP version + tool count.

---

## Milestone 2 — MVP Chat

**Goal:** работающий чат от и до — NL → LLM → MCP → cards в UI.

### Phase 2.1 — Orchestrator
- Loop: NL → LLM → tool_call → MCP → LLM continue → done
- SSE events: `status`, `tool_call`, `tool_result`, `delta`, `card`, `done`, `error`
- Сохранение message + tool_calls + cards в SQLite

**Acceptance:** реальный prompt «расскажи про базу» через 1С MCP → корректный ответ с таблицей.

### Phase 2.2 — Inline Cards (3 types)
- TableCard — для execute_query результатов
- ObjectCard — для get_metadata(detail) / get_object_by_link
- LogCard — для get_event_log
- Card detection: парсер ответа LLM ищет JSON-блоки определённой структуры

**Acceptance:** 3 prompt'а активируют все 3 типа cards с правильными данными.

### Phase 2.3 — Sessions + History
- POST /sessions (create)
- GET /sessions (list, grouped by date)
- DELETE /sessions/{id}
- Sidebar в UI: сессии grouped, click → загрузка
- Auto-title generation из первого сообщения

**Acceptance:** ≥ 5 сессий в UI, переключение работает, история сохраняется после refresh.

### Phase 2.4 — Settings (Connections + LLM)
- Settings modal с двумя tabs: Connections / LLM
- Connections: CRUD MCP endpoints, ping test
- LLM: endpoint + API key (localStorage) + model + temperature
- Channel selector в header работает

**Acceptance:** аналитик настраивает с нуля → ≥ 2 MCP подключения, ≥ 1 LLM, переключение работает.

### Phase 2.5 — Trace Panel
- Collapsible ToolTrace под ответом ассистента
- Раскрывает: tool name + args (JSON tree) + result (collapsed by default) + duration
- Кнопка «Скопировать как curl»

**Acceptance:** на любом ответе видна свёрнутая строка trace, click разворачивает все детали.

---

## Milestone 3 — Production Ready

**Goal:** надёжность, безопасность, состояния, эдж-кейсы.

### Phase 3.1 — Error States + Streaming States
- MCP disconnected — баннер + retry
- LLM rate limit — toast с retry-after
- Streaming stages: «Анализирую → Вызываю tool → Формирую ответ»
- LLM error — readable message, не stack trace

**Acceptance:** все 5 error/streaming состояний воспроизводятся через тесты.

### Phase 3.2 — Анонимизация
- Toggle в header
- Backend forward'ит anon mode в MCP при включении
- `submit_for_deanonymization` через UI кнопку «Раскрыть»
- Visual indicator токенов `[ORG-001]` в ответах

**Acceptance:** диалог с anon ON → ответы содержат токены, click «Раскрыть» → реальные значения.

### Phase 3.3 — Security Hardening
- CORS lockdown
- LLM API key только в localStorage + per-request header
- Confirm dialog для `execute_code` (dangerous keywords)
- Input validation Pydantic strict
- CSP headers

**Acceptance:** security audit passes (security-reviewer agent).

### Phase 3.4 — Tests + CI
- Unit tests orchestrator, MCP client, LLM client (≥ 80% coverage)
- E2E Playwright: 3 ключевых flow
- GitHub Actions: lint + test on PR

**Acceptance:** CI green, coverage ≥ 80% backend.

### Phase 3.5 — Docs
- README с docker-compose usage
- ARCHITECTURE.md (уже есть, обновить)
- API.md (OpenAPI spec)
- USER.md (для аналитиков-пользователей)

**Acceptance:** новый юзер по README + USER.md поднимает + использует за 15 минут.

---

## Milestone 4 — Demo & Refine

**Goal:** показать другому аналитику, собрать feedback, итерировать.

### Phase 4.1 — Quick Prompts + Slash Commands + Mentions
- Chips «Обзор базы / Ошибки за сутки / ...» над input
- Slash commands: `/sql`, `/journal`, `/find`, `/audit`, `/clear`
- @-mentions объектов из metadata cache

### Phase 4.2 — Дополнительные Cards
- MetricCard, ReferencesCard, CodeCard
- Авто-detection в LLM response

### Phase 4.3 — Search + Export
- Cmd-K — поиск по сессиям и messages
- Copy markdown / Export CSV / Export PDF

### Phase 4.4 — Demo session с реальным аналитиком
- Live использование на проекте Русский Транзит или УСО
- Запись pain points
- Backlog feedback

---

## Out of Roadmap (явно)

- Mobile UI
- Multi-user
- RAG / vector search
- Voice input/output
- Real-time collaboration
- Theming light/custom
- Direct 1С data editing
- 1С management (deploy, restart)
