---
phase: 01-foundation
status: planned
created: 2026-05-13
mode: yolo
granularity: coarse
plans: 2
waves: 1
parallelization: true
---

# Phase 1 — Foundation

**Цель фазы:** заложить инфраструктуру — backend (FastAPI + SQLite + LLM/MCP клиенты) и frontend (Next.js 15 + Tailwind 4 + AppShell) поднимаются через `docker compose up` (backend) и `pnpm dev` (frontend). Без бизнес-логики чата — только skeleton, smoke endpoints, типизированные контракты.

**Outcome (для пользователя):** developer (Никита) клонирует репо → `docker compose up backend` поднимает API на :8010 за ≤ 2 сек, `pnpm dev` поднимает Next.js на :3010 с тёмной темой и AppShell. Browser открывает http://localhost:3010 — видна оболочка приложения с empty state. Никаких реальных чатов с LLM пока нет — это Phase 2.

---

## Структура планов (coarse granularity)

| Plan | Файл | Wave | Зависимости | Файлы | Задач |
|------|------|------|-------------|-------|-------|
| 01 | `PLAN-01-backend.md` | 1 | — | 25 (backend/* + docker-compose.yml) | 3 |
| 02 | `PLAN-02-frontend.md` | 1 | — | 29 (frontend/*) | 3 |

**Параллелизм:** оба плана идут в Wave 1 без пересечения по файлам (backend trees vs frontend trees непересекающиеся), значит могут исполняться двумя executors параллельно. Единственное взаимодействие — контракт SSE event types и Pydantic ↔ TypeScript типы (зеркало через `<interfaces>` блоки в каждом плане).

**Wave 1 (параллельно):**
- Plan 01 (backend): docker compose up backend → GET /health 200, POST /chat SSE, POST /mcp/{id}/ping
- Plan 02 (frontend): pnpm dev → http://localhost:3010 рендерит AppShell + skeleton

---

## Покрытие требований (мост к REQUIREMENTS.md)

### FR (функциональные)
| Req | Plan | Что закладывается |
|-----|------|-------------------|
| FR-1 (MCP endpoint в Settings) | 01 + 02 | Backend: storage таблица mcp_connections + клиент MCP. Frontend: /settings stub с секцией Connections + lib/storage MCPConnection[] |
| FR-2 (LLM provider в Settings) | 01 + 02 | Backend: storage таблица llm_settings + LLMClient. Frontend: /settings stub с секцией LLM + lib/storage LLMConfig |
| FR-7 (SSE streaming) | 01 + 02 | Backend: SSE через sse_starlette, события status/delta/done. Frontend: lib/sse.ts парсер ReadableStream → AsyncIterable<SSEEvent> |
| FR-9 (Channel selector) | 02 | components/shell/ChannelSelector.tsx (placeholder с пустым списком в Phase 1) |
| FR-10 (Empty state) | 02 | app/page.tsx — empty state с CTA «Настроить» → /settings |

### NFR (нефункциональные)
| Req | Plan | Реализация |
|-----|------|-----------|
| NFR-1 (First SSE byte ≤ 500 мс) | 01 | event=status эмиттится синхронно сразу после открытия SSE генератора, до запроса к LLM |
| NFR-4 (Cold start backend ≤ 2 сек) | 01 | Python 3.12-slim, минимальный image, uvicorn без reload, lifespan быстро инициализирует SQLite через aiosqlite |
| NFR-8 (CORS) | 01 | Pydantic Settings → CORS_ORIGINS из env, default http://localhost:3010 (NOT "*") |
| NFR-15 (Тёмная тема) | 02 | class="dark" на <html>, Tailwind darkMode='class', CSS variables только для dark палитры |
| NFR-16 (Русский UI) | 02 | lang="ru", все видимые тексты на русском, IBM Plex с cyrillic subset |
| NFR-18 (≥ 80% coverage) | 01 | pytest + coverage для orchestrator/storage; в Phase 1 закладываем структуру тестов, реальный coverage будет в M3 |
| NFR-19 (no any) | 02 | tsc strict, eslint rule @typescript-eslint/no-explicit-any: error, grep-gate в verify |

### IR (интеграционные)
| Req | Plan | Реализация |
|-----|------|-----------|
| IR-1 (OpenAI-compat LLM) | 01 | app/clients/llm.py — httpx POST {endpoint}/chat/completions stream=true, парсинг SSE choices[0].delta |
| IR-2 (MCP Streamable HTTP) | 01 | app/clients/mcp.py — POST endpoint с JSON-RPC, поддержка JSON и SSE response, Mcp-Session-Id |
| IR-5 (Mcp-Session-Id) | 01 | MCPClient.initialize() извлекает из response header, переиспользует в list_tools/call_tool |
| IR-6 (SSE event format) | 01 + 02 | Backend: формат `event: <name>\ndata: <json>\n\n`. Frontend: lib/sse.ts парсит ровно этот формат |
| IR-7 (docker compose up) | 01 | docker-compose.yml в корне проекта, service backend (Phase 2 добавит frontend service) |

---

## Out of Scope для Phase 1 (явно)

- Оркестратор чата (NL → LLM → tool_call loop → MCP → LLM continue) — Phase 2.1
- Inline cards (Table/Object/Log) — Phase 2.2
- Sessions CRUD + sidebar grouping by date — Phase 2.3
- Реальный Settings CRUD (MCP connections + LLM config с тестированием) — Phase 2.4
- Trace panel — Phase 2.5
- Error states (MCP disconnected баннер, LLM rate limit toast) — Phase 3.1
- Анонимизация — Phase 3.2
- Markdown rendering в сообщениях — Phase 2.2
- E2E Playwright — Phase 3.4
- 80%+ coverage (для Phase 1 цель ≥ 60% backend, frontend tests появятся в Phase 2-3)

---

## Риски и митигации

| Риск | Митигация |
|------|-----------|
| Tailwind 4 ещё нестабилен в production | Использовать только базовые утилиты, не экспериментальные features (@tailwindcss/postcss конфиг — стабилен) |
| React 19 ломает совместимость с shadcn/ui | shadcn/ui v0 + Radix UI совместимы с React 19; компоненты копируются в репо (не npm package), при необходимости — патчим у себя |
| MCP Streamable HTTP может возвращать SSE или JSON | MCPClient в Plan 01 явно поддерживает оба варианта по Content-Type response |
| IBM Plex cyrillic subset большой | next/font Google автоматически subset'ит по latin+cyrillic, не подключать вручную ВЕСЬ Plex |
| Аналитики разные могут использовать разные OpenAI-compat endpoints | LLMClient целиком абстрагирует endpoint/model/api_key — каждый /chat запрос приходит со своими headers |
| Phase 1 без полной интеграции = большой риск что Phase 2 найдёт несовместимости | Контракты SSE/JSON-RPC явно зафиксированы в <interfaces> блоках обоих планов; в конце Phase 1 — ручной smoke (frontend fetchHealth → backend /health) подтверждает что CORS и типы совпадают |

---

## Verification gate (что должно быть зелёным к концу фазы)

1. `cd backend && pip install -e . && pytest -x` — все backend тесты зелёные
2. `cd backend && ruff check .` — ноль ошибок
3. `cd frontend && pnpm install && pnpm type-check && pnpm lint && pnpm build` — успех
4. `docker compose up -d backend && curl -fsS http://localhost:8010/health` → `{"status":"ok","db":"ok"}`
5. Cold start backend (time от `docker compose restart backend` до первого 200 на /health) ≤ 2 сек
6. `cd frontend && pnpm dev` → открыть http://localhost:3010 → виден AppShell, тёмная тема, русский, IBM Plex
7. Frontend + backend параллельно: главная страница показывает «Backend: ok 0.1.0» в углу (smoke integration через fetchHealth)
8. grep по запрещённым паттернам (Inter, purple-cyan, glass, эмодзи, `: any`, axios) — ничего не находит
9. SSE контракт совместим: формат строки `event: <name>\ndata: <json>\n\n` идентичен между backend Plan 01 и frontend Plan 02 parseSSEStream

---

## Файлы, созданные в этой фазе планирования

- `.planning/phases/01-foundation/PLAN-01-backend.md` — план backend (3 задачи, ~25 файлов backend/)
- `.planning/phases/01-foundation/PLAN-02-frontend.md` — план frontend (3 задачи, ~29 файлов frontend/)
- `.planning/phases/01-foundation/PHASE-summary.md` — этот файл

Реального кода проекта не создавалось — это исключительно plan-файлы. Исполнение через `/gsd-execute-phase 01` запустит Wave 1 (оба плана параллельно).

---

## Дальнейшие шаги

1. (опц.) `/gsd-plan-check 01` — проверка планов через plan-checker
2. `/gsd-execute-phase 01` — исполнение обоих планов параллельно (yolo mode, balanced executor Sonnet 4.6)
3. После Phase 1 — `/gsd-plan-phase 02` для M2 MVP Chat (orchestrator, cards, sessions, settings, trace panel)
