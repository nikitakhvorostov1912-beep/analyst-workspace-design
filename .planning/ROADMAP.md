# Roadmap: 1С Аналитик — чат с MCP

**Created:** 2026-05-13
**Granularity:** coarse (4 phases)
**Mode:** mvp (vertical slices)

## Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Foundation | Backend + frontend booting + клиенты | CONN-01, CONN-02, CONN-04, STATE-01 | 4 |
| 2 | MVP Chat | End-to-end chat: NL → MCP → cards в UI | CHAT-*, CARD-01..03, HIST-*, TRACE-01..02, CONN-03 | 5 |
| 3 | Production Ready | Error states + security + tests + docs | STATE-02..03, TRACE-03, DEVX-* (partial) | 5 |
| 4 | Demo & Refine | Anonymization + advanced cards + productivity features (v2 subset) | ANON-*, CARD-04..06, PROD-* | 4 |

---

## Phase 1: Foundation

**Goal:** Backend + frontend booting + LLM/MCP clients + Settings UI + Empty state.

**Mode:** mvp

**Success Criteria:**
1. `docker compose up` поднимает backend (:8010) + frontend (:3010); оба отвечают на /health
2. Аналитик в UI: Settings → добавляет MCP endpoint → ping показывает green
3. Аналитик в UI: Settings → добавляет LLM endpoint + API key + model → test completion работает
4. Empty state (нет подключений) показывается корректно с CTA в Settings

**Requirements covered:** CONN-01, CONN-02, CONN-04, STATE-01

**Plans:**

### Plan 1.1: Backend Skeleton
- FastAPI app + Pydantic v2 models + routes scaffolding
- SQLite через aiosqlite + миграции (initial schema: connections, llm_settings, sessions, messages)
- pyproject.toml + ruff + pytest config
- Dockerfile + docker-compose.yml (backend slice)
- `/health` endpoint

**Acceptance:** `docker compose up backend` → `GET /health` 200 OK

### Plan 1.2: Frontend Skeleton
- Next.js 15 + Tailwind 4 + shadcn/ui init
- AppShell (header / sidebar / main / bottom strip)
- Тёмная тема by default, IBM Plex шрифты, русский UI
- API client (lib/api.ts) + типизация (lib/types.ts)
- Routing: `/` (main chat), `/settings`, `/settings/llm`, `/settings/connections`
- Empty state на `/` когда нет подключений

**Acceptance:** `pnpm dev` → главная страница рендерится корректно

### Plan 1.3: LLM Client + Settings UI
- OpenAI-compat httpx client (streaming + function calling)
- POST /llm/test endpoint (валидация ключа)
- Settings → LLM page: endpoint / key (localStorage) / model / temperature
- Smoke test: minimal chat без MCP

**Acceptance:** Settings → LLM → введён ключ → click Test → response 200 + текст completion

### Plan 1.4: MCP Client + Connections UI
- MCP Streamable HTTP client: initialize + session ID + tools/list + tools/call + ping
- CRUD endpoints `/connections`
- Settings → Connections page: список + добавить/редактировать/удалить + кнопка Ping
- Discovery tools при подключении (auto-store в DB)

**Acceptance:** Settings → Connections → добавить MCP → ping green → видны 10 tools

---

## Phase 2: MVP Chat

**Goal:** End-to-end chat работает с реальной 1С: вопрос на NL → LLM → tool calls к MCP → inline cards.

**Mode:** mvp

**Success Criteria:**
1. Тестовый prompt «Расскажи про базу» → корректный ответ с TableCard или ObjectCard
2. Тестовый prompt «Покажи документы ОПП за вчера» → TableCard с реальными строками из 1С
3. Тестовый prompt «Что в журнале сегодня» → LogCard с записями
4. История сессий сохраняется; после refresh видна в sidebar
5. Channel selector работает: переключение базы → новые tools, новый чат

**Requirements covered:** CHAT-01..05, CARD-01..03, HIST-01..04, TRACE-01..02, CONN-03

**Plans:**

### Plan 2.1: Orchestrator + SSE
- Tool calling loop (NL → LLM → tool_call → MCP → result → LLM → done)
- SSE events: `status`, `tool_call`, `tool_result`, `delta`, `card`, `done`, `error`
- POST /chat endpoint
- Saving messages + tool_calls + cards в SQLite

**Acceptance:** реальный prompt через 1С MCP → корректный SSE stream → саб final response в DB

### Plan 2.2: Inline Cards (3 types)
- TableCard component (pagination + sort + CSV export)
- ObjectCard component (реквизиты + ТЧ + meta)
- LogCard component (timeline + levels + filters)
- Card detection: парсер ответа LLM ищет JSON-блоки определённой структуры (или events `card`)

**Acceptance:** 3 prompt'а активируют все 3 типа cards правильно

### Plan 2.3: Sessions + History UI
- POST/GET/DELETE /sessions endpoints
- Sidebar: список grouped by date, click → загрузка
- Auto-title generation из первого сообщения (через cheap LLM call)
- URL routing `/sessions/{id}`
- «+ Новый чат» button

**Acceptance:** ≥5 сессий в sidebar, переключение работает, refresh не теряет историю

### Plan 2.4: Channel Selector
- Header dropdown с list MCP connections
- Switching: обновляет active connection, перезагружает tools schema
- Persistence: last active channel в localStorage
- Visual indicator статуса (green/red dot)

**Acceptance:** ≥2 подключения, переключение работает, новый чат использует новые tools

### Plan 2.5: Trace Panel
- ToolTrace component: collapsed string `▸ N tools, X ms`
- Expanded: list of tool calls с name, args JSON tree, result, duration
- Кнопка «Copy as curl»

**Acceptance:** на каждом ответе ассистента viден свёрнутый trace, expand работает

---

## Phase 3: Production Ready

**Goal:** надёжность, безопасность, error states, базовое покрытие тестами, документация.

**Mode:** mvp

**Success Criteria:**
1. Все 5+ error/streaming состояний воспроизводятся (через тесты + manual QA)
2. Security audit passes (security-reviewer agent)
3. Coverage ≥80% backend orchestrator + clients
4. CI green (lint + test) на каждом PR
5. README + USER.md позволяют новому юзеру setup за ≤15 минут

**Requirements covered:** STATE-02..03, TRACE-03, SEC-01..04, DEVX-01..05

**Plans:**

### Plan 3.1: Error & Streaming States
- MCP disconnected baner + retry button + input disabled
- LLM rate limit → toast с Retry-After
- Streaming stages в UI (визуализация)
- LLM error → readable message

### Plan 3.2: Security Hardening
- Confirm dialog для execute_code dangerous keywords
- CORS lockdown configurable
- Pydantic strict
- CSP headers
- API key forward через header (не persist)

### Plan 3.3: Tests + CI
- Unit tests orchestrator (mocks LLM + MCP)
- Unit tests MCP client (mocks HTTP)
- Unit tests LLM client (mocks streaming)
- E2E Playwright: 3 ключевых flow
- GitHub Actions: lint + test on PR

### Plan 3.4: Docs
- README обновить (post-MVP)
- USER.md — гид для аналитиков
- API.md — OpenAPI spec
- ARCHITECTURE.md актуализировать
- TRACE-03: Copy as curl button

---

## Phase 4: Demo & Refine

**Goal:** анонимизация, расширенные cards, productivity quick wins, готовность к real demo с аналитиком.

**Mode:** mvp

**Success Criteria:**
1. Демо на реальном проекте (РТ или УСО) проходит за 15 минут
2. Anonymization работает: ON → ответы с токенами, «Раскрыть» → реальные значения
3. 6 типов inline cards рендерятся
4. Quick prompts / slash / @-mentions работают

**Requirements covered:** ANON-01..03, CARD-04..06, PROD-01..05

**Plans:**

### Plan 4.1: Anonymization
- Header toggle
- Backend forward anon mode в MCP
- submit_for_deanonymization через UI button «Раскрыть»
- Visual highlight токенов

### Plan 4.2: Advanced Cards
- MetricCard (число + sparkline)
- ReferencesCard (где используется)
- CodeCard (BSL syntax highlight)

### Plan 4.3: Productivity
- Quick prompts chips
- Slash commands: /sql /journal /find /audit /clear
- @-mentions objects из metadata cache
- Cmd-K search

### Plan 4.4: Live Demo Session
- Setup на реальной 1С
- Демо аналитику (Никита или внешний)
- Запись pain points + feedback
- Backlog для post-MVP

---

## Out of Roadmap

Vector search / RAG · Mobile UI · Multi-user · Real-time collaboration · Voice · Light theme · Theming · Direct 1С editing · 1С management.

---

*Roadmap created: 2026-05-13*
*Granularity: coarse (4 phases ≈ 5-7 weeks)*
