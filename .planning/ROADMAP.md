# Roadmap: 1С Аналитик — чат с MCP

**Created:** 2026-05-13
**Granularity:** coarse (6 phases)
**Mode:** mvp (vertical slices)

## Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Foundation | Backend + frontend booting + клиенты | CONN-01, CONN-02, CONN-04, STATE-01 | 4 |
| 2 | MVP Chat | End-to-end chat: NL → MCP → cards в UI | CHAT-*, CARD-01..03, HIST-*, TRACE-01..02, CONN-03 | 5 |
| 3 | Production Ready | Error states + security + tests + docs | STATE-02..03, TRACE-03, DEVX-* (partial) | 5 |
| 4 | Demo & Refine | Anonymization + advanced cards + productivity features (v2 subset) | ANON-*, CARD-04..06, PROD-* | 4 |
| 5 | Полировка UX до готового продукта | Settings CRUD UI + First-Run Onboarding + backend как source of truth для connections + dev mode fix + production launch readiness | UX-01..05 (новые) | 5 |
| 6 | Self-Explanatory UI | /about + /status + try examples в empty state + header иконки | (UX polish, без новых REQ) | — |
| 7 | Desktop Installer | 3/5 | In Progress|  |

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

**Plans:** 4 plans

**Success Criteria:**
1. Демо на реальном проекте (РТ или УСО) проходит за 15 минут
2. Anonymization работает: ON → ответы с токенами, «Раскрыть» → реальные значения
3. 6 типов inline cards рендерятся
4. Quick prompts / slash / @-mentions работают

**Requirements covered:** ANON-01..03, CARD-04..06, PROD-01..04 (PROD-05 partial: CSV есть, PDF deferred)

Plans:
- [ ] 04-01-PLAN.md — Anonymization (header toggle + visual highlight + Раскрыть через submit_for_deanonymization)
- [ ] 04-02-PLAN.md — Advanced Cards (MetricCard со sparkline + ReferencesCard grouped + CodeCard prismjs)
- [ ] 04-03-PLAN.md — Productivity (Quick prompts + Slash commands + @-mentions + Cmd-K через FTS5)
- [ ] 04-04-PLAN.md — Live Demo Session (DEMO-SCRIPT.md + observer checklist + feedback template + seed script + post-MVP backlog)

---

## Phase 5: Полировка UX до готового продукта

**Goal:** Закрыть все UX-затыки, чтобы готовое приложение можно было открыть и пользоваться без чтения USER.md. Source of truth — backend, не localStorage. /settings — реальный CRUD, не stub.

**Mode:** mvp

**Success Criteria:**
1. `docker compose up` запускает оба сервиса; `http://localhost:3010` открывается без ошибок dev mode (CSP headers fix)
2. **First-run experience**: пустая БД → пользователь видит понятный onboarding wizard и через 3 клика добавляет MCP + LLM
3. **/settings — полноценный CRUD UI**: добавить/редактировать/удалить MCP connection через форму; настроить LLM endpoint+key+model через форму; нет надписей «следующая итерация»
4. Source of truth для connections — backend `/connections` API (не localStorage); `getMCPConnections()` устарел и удалён или превращён в кеш с фоновой sync
5. Empty state с понятным CTA: «Шаг 1: подключите 1С» / «Шаг 2: настройте LLM» / «Шаг 3: задайте первый вопрос»

**New Requirements (Phase 5):**
- **UX-01**: First-run onboarding wizard (3 шага в /settings или модальный)
- **UX-02**: Settings → MCP Connections — полноценный CRUD с формой (name, endpoint, channel, test ping)
- **UX-03**: Settings → LLM — полноценный CRUD с формой + кнопкой Test Connection
- **UX-04**: Source of truth = backend; localStorage только для `activeChannelId` + LLM api_key (security)
- **UX-05**: Dev mode launch без ошибок — headers fix + проверочный smoke test в CI

**Plans:**

### Plan 5.1: Backend source-of-truth миграция + LLM CRUD endpoints
- POST/GET/PATCH/DELETE `/llm-config` endpoints (БД таблица `llm_settings` уже есть из Phase 1, но без CRUD UI)
- `POST /llm-config/test` — валидация ключа через мини-запрос к LLM (1 token)
- `POST /connections/{id}/test` уже есть — используем
- Frontend `lib/api.ts` → новые функции `fetchLLMConfig/saveLLMConfig/deleteLLMConfig/testLLMConfig`

**Acceptance:** curl `POST /llm-config` создаёт запись в DB; `GET /llm-config` возвращает (без api_key в response, только префикс)

### Plan 5.2: Settings UI CRUD
- `/settings/page.tsx` — полная замена stub: 2 секции с формами + кнопками
- MCP form: name + endpoint + channel + кнопки Сохранить / Тест ping / Удалить
- LLM form: endpoint + api_key + model + temperature + кнопки Сохранить / Тест / Удалить
- shadcn `<Form>` + zod валидация (`form-schema.ts`)
- Inline toast «Сохранено» / «Ошибка: ...» при операциях

**Acceptance:** через UI можно добавить MCP, увидеть в Channel Selector dropdown, отправить первое сообщение

### Plan 5.3: First-Run Onboarding
- Detection: пустая БД connections + нет LLM → показывается `<OnboardingDialog>` модально поверх главной
- 3 шага с прогресс-индикатором: «1. Подключите 1С» → форма MCP → ping; «2. Настройте LLM» → форма LLM → test; «3. Готово!»
- Skip-кнопка для опытных (сразу /settings)
- localStorage `analyst.onboarding_completed` чтобы не показывать повторно

**Acceptance:** свежая БД + первый запуск → автоматически открывается onboarding; после прохождения — главная с пустой сессией

### Plan 5.4: page.tsx + AppShell — backend как source of truth
- `getMCPConnections()` удалить или превратить в @deprecated; всё через `fetchConnections()`
- `page.tsx hasConfig` логика → `useEffect → fetchConnections() && fetchLLMConfig() → hasConfig=true/false`
- Empty state обновить: «Шаг 1: подключите 1С» с прямой ссылкой на onboarding/settings
- Header: ChannelSelector уже использует backend (из 02-04) — оставить

**Acceptance:** добавление MCP через curl без UI → refresh главной → empty state пропадает

### Plan 5.5: Verification + Polish
- E2E Playwright: onboarding flow (3 шага) + CRUD operations + first message
- Visual smoke артефакты обновить (USER.md скриншоты остаются placeholder, README обновить про onboarding)
- pytest регрессия на новые `/llm-config` endpoints
- Финальный health check для CI: backend startup time ≤2 сек NFR-4 verified
- Final commit `release(v1.0)`: tag готового релиза

**Acceptance:** `docker compose up` → http://localhost:3010 → пройти onboarding за 90 секунд → отправить «Расскажи про базу» → видна TableCard

---

## Phase 7: Desktop Installer

**Goal:** Превратить веб-приложение (требует Python + Node для запуска) в **один Windows installer .exe** — аналитик скачал, кликнул, получил ярлык на рабочем столе, кликнул → окно с приложением.

**Mode:** mvp

**Success Criteria:**
1. Один файл `analyst-setup-v1.0.exe` (~180 MB) который ставится без админских прав
2. После установки — ярлык на рабочем столе и в Start Menu «1С Аналитик»
3. Двойной клик → открывается Electron-окно с приложением. Аналитик НЕ видит cmd-окон, портов, запуска серверов
4. Приложение **не требует** установленных Python / Node / pnpm у аналитика — всё в инсталляторе
5. При закрытии окна — все child процессы (backend, frontend) автоматически останавливаются

**New Requirements (Phase 7):**
- **DIST-01**: Electron main process spawnit backend (PyInstaller exe) + frontend (Next.js standalone) на random свободных портах, ждёт готовности, открывает BrowserWindow
- **DIST-02**: PyInstaller упаковка backend → один backend.exe (~50 MB) включая Python runtime + uvicorn + все зависимости + миграции
- **DIST-03**: Next.js standalone build с `output: "standalone"` → frontend готов к запуску через `node server.js` без npm install
- **DIST-04**: electron-builder упаковка в NSIS installer .exe с custom icon, метаданными, ярлыками
- **DIST-05**: Auto-cleanup — при close все child процессы убиваются (browser close + Window.on('close') + signal handlers)

**Plans:**

### Plan 7.1: Electron main process + dev launch
- `desktop/` папка с Electron приложением (main.js, preload.js, package.json)
- main.js: spawn backend.exe + node server.js → ждёт `/health` 200 → создаёт BrowserWindow → loadURL http://127.0.0.1:<frontend-port>
- Window.on('close') → kill all spawned children (ChildProcess.kill('SIGTERM'), fallback SIGKILL через 3 сек)
- Random ports (избежать конфликта с уже занятыми 8010/3010)
- Dev mode: запускает существующий `uvicorn` и `next dev` для отладки

**Acceptance:** `cd desktop && npm run dev` → открывается окно Electron с приложением (backend и frontend подняты как child processes)

### Plan 7.2: PyInstaller backend bundle
- `backend/build.spec` для PyInstaller (entry: app/main.py с uvicorn embedded)
- `pyinstaller --onefile --name backend backend/build.spec` → `dist/backend.exe`
- Включает: Python 3.12 runtime, fastapi, uvicorn, pydantic, aiosqlite, httpx, sse-starlette
- DB и frontend dist копируются в директорию рядом с backend.exe (через `--add-data`)
- Verify: `dist\backend.exe` запускается без Python в системе, /health отвечает

**Acceptance:** удалить Python из PATH временно → `backend.exe` всё равно работает на :8010

### Plan 7.3: Next.js standalone build для bundling
- Включить `output: "standalone"` в next.config.ts через env
- `pnpm build` → создаёт `frontend/.next/standalone/server.js` + `frontend/.next/static/`
- Скрипт копирования: `static/` в `standalone/.next/static/`, `public/` в `standalone/public/`
- Verify: `node frontend/.next/standalone/server.js` запускает frontend на любом порту

**Acceptance:** удалить `node_modules` временно → standalone server всё равно работает

### Plan 7.4: electron-builder config + сборка installer
- `desktop/electron-builder.yml` с конфигом:
  - target: nsis (Windows installer)
  - icon: `desktop/icon.ico`
  - extraResources: backend.exe + frontend standalone
  - artifactName: `analyst-setup-v${version}.exe`
- `pnpm dlx electron-builder build --win` → `desktop/dist/analyst-setup-v1.0.exe`
- NSIS configures: ярлык Desktop + Start Menu, AppData install location
- Размер ~180 MB

**Acceptance:** `setup.exe` поставлен на чистую Windows → ярлык работает, окно открывается

### Plan 7.5: Verification + release v1.1
- Smoke: чистая VM Windows 10/11 без Python/Node/pnpm → `setup.exe` → клик ярлыка → приложение работает за < 10 секунд от клика
- Проверить close behavior — backend.exe и node.exe child процессы убиты после закрытия окна
- README обновить — новый раздел «Скачать .exe для аналитика» + ссылка на release
- GitHub Release v1.1 с приложенным .exe (если хочется публично)

**Acceptance:** на машине без dev зависимостей `analyst-setup-v1.0.exe` ставится, запускается, работает; close корректно убирает процессы

---

## Out of Roadmap

Vector search / RAG · Mobile UI · Multi-user · Real-time collaboration · Voice · Light theme · Theming · Direct 1С editing · 1С management.

macOS/Linux installer — Out of Scope (Phase 7 только Windows; кросс-платформа в v2).

---

*Roadmap created: 2026-05-13*
*Phase 5 added: 2026-05-15 (UX gaps after Phase 4 visual smoke)*
*Phase 7 added: 2026-05-15 (Electron desktop installer — снять зависимости Python/Node у аналитика)*
*Granularity: coarse (7 phases)*
