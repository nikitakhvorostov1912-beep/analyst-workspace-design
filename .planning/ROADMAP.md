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
| 7 | Desktop Installer | DIST-01..05 | ✓ Done — v1.1.0 |  |

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

## Phase 7: Desktop Installer ✓ Done

**Status:** COMPLETE — v1.1.0 (2026-05-16)
**Installer:** `desktop/dist/analyst-setup-v1.0.0.exe` (105.9 MB), SHA256: 2B96AA66...

**Goal:** Превратить веб-приложение (требует Python + Node для запуска) в **один Windows installer .exe** — аналитик скачал, кликнул, получил ярлык на рабочем столе, кликнул → окно с приложением.

**Mode:** mvp

**Success Criteria:**
1. ✓ Один файл `analyst-setup-v1.0.0.exe` (105.9 MB) который ставится без админских прав (perMachine: false)
2. ✓ После установки — ярлык на рабочем столе и в Start Menu «1С Аналитик»
3. ✓ Двойной клик → открывается Electron-окно с приложением. Аналитик НЕ видит cmd-окон, портов, запуска серверов
4. ✓ Приложение **не требует** установленных Python / Node / pnpm у аналитика — всё в инсталляторе
5. ✓ При закрытии окна — все child процессы (backend, frontend) автоматически останавливаются

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

## Milestone 5: Post-v1.1 Expansion

**Status:** Planned (started 2026-05-17)
**Rationale:** 3 направления допила пользователя из MSG #10 (transcript 769b133a).
**Source:** `.claude/memory/requirements-stack-sessions-learn.md`

| # | Phase | Goal | Effort |
|---|-------|------|--------|
| 8 | STACK Integration | Подцепить релевантные глобальные скиллы/правила/MCP к проекту | M (2 plans) |
| 9 | Sessions DB Init | БД сессий автоматом связывается при установке Electron | S (1 plan) |
| 10 | Learn Engine | LLM в продукте обучается на записанных сессиях (RAG over sessions) | L (3 plans) |

---

## Phase 8: STACK Integration

**Goal:** Подцепить релевантные глобальные ресурсы Claude Code (skills, rules, MCP refs) к проекту так, чтобы будущие Claude-сессии имели точечный контекст. НЕ копировать 100+ 1С-метаданных скиллов — этот проект про чат-UI.

**Mode:** mvp

**Success Criteria:**
1. `.claude/skills/` содержит 3 проектных скилла: `awd-dev-up`, `awd-quality-gate`, `awd-claude-design-handoff`
2. `.claude/CLAUDE.md` (локальный) routing к 5 релевантным глобальным скиллам: `claude-design`, `playwright-test`, `reflect`, `weekly-improve`, `inspect`
3. `.claude/rules/` содержит проектные правила (extract из корневого CLAUDE.md)
4. Локальный CLAUDE.md ЯВНО запрещает работу в `analyst-tools-1c`, описывает workflow при «Продолжай»
5. Новая Claude-сессия в проекте подгружает локальный CLAUDE.md и видит routing

**Requirements covered:** STACK-01..03 (новые)

### Plan 8.1: Project Skills + Rules Scaffolding
- Создать `.claude/skills/awd-dev-up/SKILL.md` — поднять backend+frontend с verify
- Создать `.claude/skills/awd-quality-gate/SKILL.md` — pytest+vitest+playwright+pnpm build → PASS/FAIL
- Создать `.claude/skills/awd-claude-design-handoff/SKILL.md` — собрать context bundle для claude.ai/design + промпт-шаблон (chat-first, без 8 экранов)
- Создать `.claude/rules/` с extract правил: `design-bans.md`, `tech-stack.md`, `session-contract.md`
- Скрипты в `awd-dev-up/scripts/` для запуска (PowerShell + bash)

**Acceptance:** `/awd-dev-up` запускается → backend на :8010 + frontend на :3010 + verify через HTTP

### Plan 8.2: Local CLAUDE.md Routing + Verification
- Создать `.claude/CLAUDE.md` (НЕ корневой) — routing к проектным скиллам + ссылки на глобальные
- Lazy-load карта: какие memory-файлы читать на какой триггер (как knowledge-router.md)
- Wrong-project защита: первый абзац запрещает работу вне `analyst-workspace-design/`
- README-секция «Структура .claude/» в корневом README.md
- Smoke: запустить Claude Code в проекте, ввести «Продолжай» → должна прочитать STATE.md + последний PHASE-summary

**Acceptance:** новая Claude-сессия в проекте знает про проектные скиллы и не лезет в analyst-tools-1c

---

## Phase 9: Sessions DB Init

**Goal:** SQLite БД сессий автоматически инициализируется при установке Electron. Путь managed Electron'ом (`%APPDATA%\1С Аналитик\app.db`), миграции прокатываются при первом запуске.

**Mode:** mvp

**Success Criteria:**
1. `desktop/main.js` выставляет `DATABASE_URL=sqlite+aiosqlite:///${app.getPath('userData')}/app.db` перед spawn backend
2. Backend при первом запуске накатывает миграции в этот путь (миграции уже есть из Phase 1)
3. Установка через `analyst-setup-v1.0.0.exe` → запуск → `%APPDATA%\1С Аналитик\app.db` существует
4. Smoke: install → 3 сессии → uninstall → reinstall → старые сессии видны (userData не очищается)
5. Privacy escape hatch: в `/settings` кнопка «Сбросить локальную базу» (TRUNCATE всех таблиц)

**Requirements covered:** SESS-01..03 (новые)

### Plan 9.1: Electron-Managed userData DB Path + Reset Endpoint + Smoke
- Edit `desktop/main.js` — добавить `process.env.DATABASE_URL = ...` перед `spawn(backendExe, ...)`
- Edit `backend/app/config.py` — приоритет env DATABASE_URL над дефолтом `/data/app.db`
- Edit `backend/app/storage/db.py` — миграция создаёт schema + индексы если БД пустая
- Backend endpoint `POST /admin/reset-local-db` (требует confirm header X-Confirm-Reset: true)
- Frontend `/settings` секция «Локальные данные»: кнопка с AlertDialog подтверждения
- Verify smoke: build installer → fresh VM install → 3 сессии → uninstall → reinstall → сессии видны

**Acceptance:** на чистой VM: 1) install .exe; 2) приложение запускается; 3) `%APPDATA%\1С Аналитик\app.db` создан; 4) после 3 сессий + uninstall + reinstall — сессии видны в sidebar

---

## Phase 10: Learn Engine

**Goal:** LLM в самом приложении использует прошлые сессии аналитика как контекст для текущего ответа. После N сессий «как ты вчера решал X?» → ответ ссылается на конкретный прошлый разговор.

**Mode:** mvp

**Path decision (Claude's discretion):** **Path B — собственный RAG (SQLite-vss + embeddings)**.
Reason: Multi-LLM requirement (MSG #11) — решение должно работать **независимо от провайдера** (MiMo / Claude / GPT / Yandex / GigaChat / Grok). Anthropic Memory Tool API работает только с Claude → нарушает требование.

**Success Criteria:**
1. SQLite-vss vector store с embeddings для всех сообщений (background job)
2. Backend `POST /learn/retrieve` — top-K релевантных кусков по query
3. Orchestrator при `/chat` встраивает контекст в system prompt: «На основе прошлых сессий: ...» (top-3, ≤500 токенов)
4. UI индикатор: «📚 Использован контекст N сообщений» с раскрытием каких именно
5. Privacy escape hatch: настройка «Отключить Learn» — embeddings не строятся, retrieve не вызывается
6. Embeddings провайдер — отдельная настройка LLM (independent от main LLM)

**Requirements covered:** LEARN-01..04 (новые)

### Plan 10.1: Vector Store + Embeddings Provider + Indexing Job
- Установить `sqlite-vec` Python пакет (преемник sqlite-vss)
- Migration v6: добавить vec0 таблицу `message_embeddings(message_id INTEGER, embedding FLOAT[N])`
- Backend `app/services/embeddings.py` — обёртка OpenAI-compat embeddings API (по умолчанию `text-embedding-3-small`)
- Background job `app/jobs/index_messages.py` — индексирует новые сообщения каждые 60 сек
- Settings UI: новая секция «Embeddings» — endpoint, model, api_key
- Default embedding model: `text-embedding-3-small` (1536 dims) — можно поменять на `BGE-M3` (1024 dims) или Yandex

**Acceptance:** 10 сессий по 5 сообщений → 50 записей в `message_embeddings` → vector search «расскажи про базу» возвращает top-5 релевантных

### Plan 10.2: Retrieve API + Orchestrator Integration + UI Badge
- Backend `POST /learn/retrieve` body `{query, channelId, topK=5}` → возвращает массив `{messageId, sessionId, snippet, similarity}`
- Orchestrator hook: перед LLM-вызовом → retrieve → если top-1 similarity ≥ 0.7 → добавить в system prompt «На основе прошлых сессий: ...»
- Лимит: max 3 snippets × 500 tokens каждый = 1500 tokens context
- SSE event `learn_context` с массивом использованных snippets
- Frontend `LearnContextBadge` component — кликабельная иконка «📚 N» под ответом, разворачивает список использованных snippets с ссылками на сессии
- E2E: Playwright тест — 2 связанные сессии, проверить что badge появляется на 2-й

**Acceptance:** после 5 сессий про РТ → новый чат «как мы решали проблему с поручительствами?» → ответ содержит ссылку на прошлую сессию + badge «📚 1»

### Plan 10.3: Privacy Controls + Verification + Release
- Settings UI: toggle «Включить обучение на моих сессиях» (default OFF, opt-in при онбординге Step 3)
- Backend: если toggle OFF → background job не индексирует новые сообщения, retrieve возвращает пустой массив
- `POST /learn/forget?sessionId=...` — удалить embeddings конкретной сессии (privacy)
- `POST /learn/forget-all` — удалить все embeddings (под AlertDialog confirm)
- Migration v7: добавить `learn_enabled BOOLEAN` в llm_settings
- E2E + unit coverage ≥ 80% новых модулей
- README обновить: раздел «Обучение на ваших сессиях» с privacy explanation
- Tag v1.2.0

**Acceptance:** все 5 success criteria Phase 10 verified + tag v1.2.0 + GitHub release

---

## Phase 11: Design v2 Import

**Source:** Claude Design handoff `Рабочее место 1с Аналитик.zip` (2026-05-18) — `temp/from-claude-design-20260518-111524/`.

**Goal:** Импортировать визуальный язык из Claude Design v2 (15 JSX-файлов + index.html preview) в реальный проект — Tailwind tokens, унифицированные атомы, обновлённые Header/Onboarding/StreamingStages/Cards. Сохранить всю backend-логику (useChatStream, SSE events, fetchConnections и т.д.).

**Mode:** mvp — 5 plans, последовательно

**Success Criteria:**
1. Design tokens из CSS variables → `tailwind.config.ts` `theme.extend` (palette, transitions, easings)
2. 5 атомарных компонентов: `StatusDot`, `CardHeader` (unified), `CardActionMenu`, `EmptyState`, `ErrorBanner`
3. Header переработан: brand mark + channel popover с search + anon pill amber + model badge + cmd-k trigger
4. Onboarding wizard расширен с 3 до 4 шагов (Step 3 — Learn opt-in)
5. StreamingStages с иконками заменяет StreamingIndicator: analyzing → learn → tool(spin) → tool_done → finalizing
6. 6 cards рефакторинг — общий CardHeader + унифицированный action menu
7. Animations: fade-up, scale-in, dialog-in, spin, blink на правильных местах
8. Все 315 pytest + ≥219 vitest тестов зелёные после импорта
9. Tag v1.2.0, deploy через Electron installer

**Requirements covered:** UX-06..10 (новые)

### Plan 11.1: Design Tokens (Tailwind config + CSS layer)
- Извлечь CSS variables из `temp/from-claude-design-.../index.html`: `--bg-1/2/3`, `--fg-1/2/3/4`, `--bd-1/2/3`, `--accent`, `--accent-08`, `--accent-20`, `--success`, `--warning`, `--warning-12`, `--warning-20`, `--error`
- Создать `frontend/styles/design-tokens.css` с `:root.dark { ... }`
- Расширить `tailwind.config.ts` `theme.extend.colors` под названия токенов (bg, fg, bd, accent, success, warning, error)
- Animation tokens: `--t-micro: 150ms`, `--t-normal: 200ms`, `--t-large: 300ms`, `--ease: cubic-bezier(0.4, 0, 0.2, 1)` — в `theme.extend.transitionDuration` + `transitionTimingFunction`
- Keyframes: `fade-up`, `scale-in`, `spin`, `blink`, `dialogIn` — в `theme.extend.keyframes` + `theme.extend.animation`

**Acceptance:** существующие компоненты компилируются без падений, цвета визуально не сдвинулись (CSS vars совпадают)

### Plan 11.2: Atoms (5 компонентов)
- `frontend/components/ui/StatusDot.tsx` — green pulse / red / connecting spin + tooltip props
- `frontend/components/cards/CardHeader.tsx` — icon + title + tool chip + meta + anon pill + action menu, props под все 6 типов
- `frontend/components/cards/CardActionMenu.tsx` — popover с items {Copy / Pin / Maximize / Export CSV / Refresh / Hide}
- `frontend/components/ui/EmptyState.tsx` — illustration + headline + description + CTA
- `frontend/components/ui/ErrorBanner.tsx` — severity (info/warning/error) + title + description + actions {Retry / Dismiss}
- Каждый — `.tsx` с типами + vitest тесты ≥ 3 на компонент

**Acceptance:** vitest проходит для 5 новых атомов, type-check clean

### Plan 11.3: Header + ChannelSelector + Onboarding 4-step
- `frontend/components/shell/Header.tsx` — переработка: brand mark, channel popover с search, anon pill amber, model badge, cmd-k trigger, health + help + settings buttons
- `frontend/components/shell/ChannelSelector.tsx` — popover с search input, items как в Claude Design (StatusDot + name + url/lastPing + check)
- `frontend/components/shell/AnonymizationToggle.tsx` — pill `[Lock/Unlock] Анон: ВКЛ/ВЫКЛ`
- `frontend/components/onboarding/OnboardingDialog.tsx` — расширить с 3 до 4 шагов (вставить Step 3 «Обучение опционально»)
- Progress bar + StepIndicator pills (done/active/future)
- Skip button сверху-справа

**Acceptance:** onboarding с пустой БД проходит за 4 клика, channel selector search фильтрует, anon toggle меняет state

### Plan 11.4: StreamingStages + ToolTrace + Cards refactor
- `frontend/components/chat/StreamingStages.tsx` — заменяет StreamingIndicator. 5 стадий с иконками: analyzing/learn/tool(spin)/tool_done/finalizing
- `frontend/components/chat/ToolTrace.tsx` — переработка: chevron rotation, mini chips имён, total ms, expandable per-call
- 6 cards рефакторинг (`TableCard`, `ObjectCard`, `LogCard`, `MetricCard`, `ReferencesCard`, `CodeCard`) — использовать новый `<CardHeader />`, `<CardActionMenu />`
- `frontend/components/chat/AssistantMessage.tsx` — заменить `StreamingIndicator` на `StreamingStages`, обновить рендер cards

**Acceptance:** main flow «Расскажи про базу» показывает StreamingStages с правильной анимацией, cards рендерятся с CardHeader, action menu кликается

### Plan 11.5: Animations + Smoke + Release v1.2.0
- Mount transitions: fade-up на сообщениях, scale-in на popovers/dropdowns, dialogIn на modals
- Streaming text shimmer (CSS gradient на новом тексте)
- Sidebar collapse animation (width transition 300ms)
- Status dot pulse 2s infinite
- E2E Playwright: проверить main flow + onboarding 4-step + cards render
- Manual smoke на :3010
- Tag `v1.2.0` + RELEASE-NOTES
- Сборка Electron installer `analyst-setup-v1.2.0.exe`

**Acceptance:** все анимации smooth (no jank), E2E зелёный, installer ставится на чистую VM

---

## Out of Roadmap

~~Vector search / RAG~~ → переоценено и включено в Phase 10 (Learn Engine).

Mobile UI · Multi-user (совместная работа в одной сессии) · Real-time collaboration · Voice · Light theme · Theming · Direct 1С editing · 1С management.

macOS/Linux installer — Out of Scope (Phase 7 только Windows; кросс-платформа в v2).

Cross-user learning (sharing embeddings между пользователями) — Privacy violation, Out of Roadmap.

---

*Roadmap created: 2026-05-13*
*Phase 5 added: 2026-05-15 (UX gaps after Phase 4 visual smoke)*
*Phase 7 added: 2026-05-15 (Electron desktop installer — снять зависимости Python/Node у аналитика)*
*Milestone 5 added: 2026-05-17 (STACK + SESSIONS + LEARN — MSG #10 verbatim)*
*Granularity: coarse (10 phases across 5 milestones)*
