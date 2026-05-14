# Phase 3: Production Ready — Context

**Gathered:** 2026-05-14
**Status:** Ready for planning
**Source:** Direct extraction (yolo) из ROADMAP.md + REQUIREMENTS.md + Phase 2 deferred items

<domain>
## Phase Boundary

Что эта фаза доставляет:
- **Error states** — пользовательские состояния когда MCP отвалилось, LLM возвращает 429/5xx, streaming прерывается посреди ответа
- **Security hardening** — CSP, CORS lockdown, Pydantic strict, confirm dialog перед опасными `execute_code`
- **Test coverage** — unit/integration backend ≥80%, E2E Playwright 3 ключевых flow, GitHub Actions CI
- **Docs** — README (post-MVP), USER.md, API.md (OpenAPI), актуализация ARCHITECTURE.md, TRACE-03 Copy as curl кнопка
- **Backlog из Phase 2** — LogCard cursor-fetch backend endpoint (UI уже готов)

Что эта фаза НЕ доставляет (deferred → v2):
- Анонимизация (ANON-01..03) — отложено до v2 (REQUIREMENTS.md уже маркирует v2)
- Quick prompts / slash commands / @-mentions / Cmd-K / Export PDF (PROD-01..05) — v2
- Расширенные cards (MetricCard/ReferencesCard/CodeCard) — v2
- OAuth / SSO — v2

Вход в Phase 3 (что работает после Phase 2):
- End-to-end chat: backend orchestrator (NL→LLM→MCP loop), inline cards (Table/Object/Log), sessions CRUD, channel selector, trace panel
- 122 backend pytest + 56 vitest всё зелёное
- SSE контракт (7 events) синхронен между backend и frontend
- group_by_date sidebar работает, /sessions/[id] dynamic route с восстановлением истории
- Tools/cards persistence в SQLite

</domain>

<decisions>
## Implementation Decisions

### Plan 3.1 — Error & Streaming States (STATE-02, STATE-03)

**STATE-02 (MCP disconnected banner)**:
- Когда `POST /chat` или `POST /connections/{id}/ping` возвращает ошибку MCP (502 от backend; connection refused; timeout): backend эмитит SSE `event: error` с `{message, code: "mcp_disconnected"}` и завершает stream
- Frontend: в `Thread.tsx` (или новый `ConnectionStatusBanner`) — красная плашка наверху чата «Подключение к 1С потеряно. Повторить» + input disabled
- Кнопка «Повторить» вызывает `POST /connections/{id}/ping`; если зелёный → банер скрывается, input enabled
- Banner — top-level в page, не модальный

**STATE-03 (LLM rate limit / errors)**:
- Backend LLMClient: при HTTP 429 респекте `Retry-After` header; при остальных 4xx — фьюзить error в SSE с понятным `message` и `code`
- Codes: `llm_rate_limit`, `llm_invalid_key`, `llm_network_error`, `llm_server_error`
- Frontend: shadcn `sonner` Toaster (одна зависимость) или внутренний минимальный toast компонент (~80 строк)
- Toast показывает русское сообщение + (если есть retry-after) countdown секунд

**Streaming stages визуализация** (CHAT-03 ширится):
- `status` события `{stage: "thinking"|"calling_tool"|"formatting"}` уже эмитятся backend (Phase 2)
- В UI assistant message — небольшой строчный индикатор «Анализирую...», «Вызываю execute_query...», «Формирую ответ...» (на основе последнего status event)
- При получении `done` — индикатор скрывается

**LLM error → readable message**:
- В UI ошибки рендерятся как assistant message с красным border, иконкой ⚠ (текстовой), без stack trace
- Backend никогда не пробрасывает Python traceback в `event: error`

### Plan 3.2 — Security Hardening (SEC-01..04)

**SEC-01 (Confirm dialog для execute_code)**:
- Backend orchestrator перед каждым `tool_call` с `name == "execute_code"` проверяет args на dangerous keywords: `Удалить`, `Записать(`, `НачатьТранзакцию`, `Отменить`, `ОчиститьВсё`, `УстановитьЗначение`, `НовыйОбъект.Записать` etc
- Если найден — backend эмитит `event: confirm_required` с payload `{tool_call_id, name, args, reason: "<keyword>"}` и **приостанавливает loop** (ждёт ответ frontend)
- Frontend: модальный диалог shadcn `<Dialog>` с показом args и кнопками «Выполнить» / «Отменить»
- При «Выполнить» — POST `/chat/confirm` с `{tool_call_id, approved: true}` — backend продолжает loop с этим tool_call
- При «Отменить» — POST `/chat/confirm` с `{approved: false}` — backend эмитит `event: error` с `code: "user_declined"` и закрывает stream

**SEC-02 (CSP headers)**:
- Next.js `next.config.ts` — `headers()` с `Content-Security-Policy`:
  - `default-src 'self'`
  - `script-src 'self' 'unsafe-inline'` (Next.js inline hydration; dev mode еще `'unsafe-eval'`)
  - `connect-src 'self' http://localhost:8010` (backend URL — из env)
  - `style-src 'self' 'unsafe-inline'` (Tailwind inline + IBM Plex Google Fonts)
  - `font-src 'self' https://fonts.gstatic.com`
  - `img-src 'self' data:`
  - `frame-ancestors 'none'`
- В dev mode менее строгий (next.js HMR требует eval)

**SEC-03 (Pydantic strict + validators)**:
- Все Request models — `model_config = ConfigDict(extra="forbid", strict=True)` (уже есть `extra="forbid"`, добавить `strict=True`)
- Field-level validators для endpoints/URLs (валидные https?:// схемы, не localhost для production по env флагу)
- Response models — без `strict=True` (slow down)
- НЕ ломать существующие тесты: проверить что snake_case API не страдает от strict

**SEC-04 (CORS lockdown + API key forwarding)**:
- `Settings.cors_origins` уже Pydantic (Phase 1) — fix чтобы дефолт был НЕ `["http://localhost:3010"]` а реально configurable
- Добавить ENV `BACKEND_ALLOWED_ORIGINS="https://app1.example,https://app2.example"` — список через запятую
- API ключ LLM — **никогда не логировать, никогда не персистить**. Проверить grep по логам что нигде нет `api_key` в str/repr/journal записи
- Тест: подделать `Authorization` в logs middleware

### Plan 3.3 — Tests + CI (DEVX-01..03)

**Unit tests orchestrator** (≥80% coverage):
- Уже есть 122 pytest. Добавить недостающие — coverage report и латание дыр
- `pytest-cov` + `--cov-fail-under=80` локально и в CI
- Specific gaps: error paths в `orchestrator/loop.py` (network errors, timeout, max iterations), retry policy, MCPError, LLMError

**Unit tests MCP client (mocks HTTP)**:
- Существующие тесты MCP — extend на edge cases: 4xx, 5xx, SSE vs JSON content-type, malformed JSON-RPC response, Mcp-Session-Id rotation, тяжёлый concurrent call (asyncio.gather)

**Unit tests LLM client (mocks streaming)**:
- Существующие — extend: rate limit 429 с Retry-After, multi-chunk tool_calls accumulation, finish_reason переходы (stop, tool_calls, length, content_filter), partial JSON в chunk

**E2E Playwright** (DEVX-02):
- 3 flow:
  1. Empty state → создать connection → создать LLM config → отправить prompt → видеть thread
  2. Создать 5 сессий → refresh → 4 группы в sidebar → click → load history
  3. Channel switch → редирект → новая сессия → видим новый channel в URL/state
- Mocked backend (MSW или собственный фейк FastAPI на отдельном порту) — НЕ требует реальной 1С
- Запуск: `pnpm exec playwright test` в frontend/, headless по умолчанию

**GitHub Actions CI** (DEVX-03):
- `.github/workflows/ci.yml`:
  - Job `backend`: Python 3.12, `pip install -e .`, `ruff check .`, `pytest --cov-fail-under=80`
  - Job `frontend`: Node 22, pnpm install, type-check + lint + build + vitest
  - Job `e2e` (опционально, гейтится `if: github.event_name == 'pull_request'`): пнпм playwright install + test
- Все jobs на PR + push в main
- Cache pnpm / pip для скорости

### Plan 3.4 — Docs + TRACE-03 + LogCard cursor-fetch backend (DEVX-04..05, TRACE-03)

**README** (DEVX-04 docker-compose часть):
- Полный setup: `git clone → docker compose up backend → pnpm install && pnpm dev → http://localhost:3010`
- Скриншоты основных экранов (минимум 3: empty, chat with cards, sidebar history)
- Бейджи: tests, build, license
- Лицензия (MIT?) — если не было

**USER.md** (DEVX-05):
- Гид для аналитика-новичка: «как настроить подключение», «как задать первый вопрос», «что делать если 1С не отвечает»
- Скриншоты с подсветкой UI элементов
- FAQ (5-7 типичных проблем)

**API.md**:
- OpenAPI 3.1 спека backend — FastAPI её генерит автоматически на `/openapi.json`; экспорт в `docs/api.md` через `widdershins` или ручной render
- Альтернатива: ссылка на `/docs` (Swagger UI встроенный)

**ARCHITECTURE.md актуализация**:
- Обновить топологию (orchestrator + persistence layer добавлены в Phase 2)
- Обновить data flow diagram (7 SSE events)
- Удалить ссылки на v0/v0b legacy

**TRACE-03 (Copy as curl)**:
- В `ToolTrace.tsx` expand-row добавить кнопку «Скопировать как curl»
- Формирует HTTP-запрос в формате:
  ```
  curl -X POST '<mcp_endpoint>' \
    -H 'Content-Type: application/json' \
    -H 'Mcp-Session-Id: <id>' \
    -d '<json-rpc body>'
  ```
- На clipboard через navigator.clipboard.writeText
- Toast «Скопировано»

**LogCard cursor-fetch backend** (закрываем Phase 2 deferred):
- Backend `POST /cards/log/load-more` (или `/sessions/{sid}/messages/{mid}/cards/{cid}/load-more`):
  - Принимает `cursor` + filters из original LogCard
  - Вызывает `MCPClient.call_tool("get_event_log", {**filters, cursor})`
  - Возвращает next page entries + new cursor
- Frontend `LogCard.onLoadMore` — вызывает endpoint, appends entries, обновляет cursor

### Out of scope для Phase 3 (явно)

- Анонимизация (ANON-01..03) — v2, в REQUIREMENTS уже маркировано
- Advanced cards (CARD-04..06) — v2
- Productivity (PROD-01..05) — v2
- OAuth / SSO — Out of Scope (REQUIREMENTS)
- Email notifications — Out of Scope
- Mobile / tablet UI — Out of Scope
- Light theme — Out of Scope
- Voice / TTS — Out of Scope
- Direct 1С data editing — Out of Scope (только просмотр + confirmed execute_code)
- Vector search / RAG — v2

### Claude's Discretion

- Choice of toast library: рекомендация — внутренний минимальный компонент 80 строк вместо `sonner` (избегаем зависимости)
- Format CSP: rendering статически в next.config.ts vs middleware — на усмотрение планера, оба валидны
- E2E mock strategy: MSW vs отдельный FastAPI stub — на усмотрение планера; рекомендация MSW (стандарт)
- README/USER.md скриншоты: можно отложить до момента когда реальная 1С будет доступна (для финального smoke), pre-merge — без скриншотов
- TRACE-03 placement: button-icon в trace row vs hover-menu — на усмотрение планера

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project documentation
- `PROJECT.md`, `ARCHITECTURE.md`, `CLAUDE.md`
- `REQUIREMENTS.md` — REQ-IDs Phase 3: STATE-02, STATE-03, TRACE-03, SEC-01..04, DEVX-01..05
- `ROADMAP.md` — Phase 3 секция

### Phase 1 + Phase 2 артефакты
- `.planning/phases/01-foundation/01-01-SUMMARY.md`, `01-02-SUMMARY.md`
- `.planning/phases/02-mvp-chat/PHASE-summary.md`
- `.planning/phases/02-mvp-chat/02-01-SUMMARY.md` ... `02-05-SUMMARY.md`
- `.planning/phases/02-mvp-chat/VERIFICATION.md`

### Existing code (точки интеграции)
- Backend orchestrator: `backend/app/orchestrator/loop.py`, `events.py`, `cards.py`, `persistence.py`, `title.py`
- Routes: `backend/app/routes/chat.py`, `sessions.py`, `connections.py`, `mcp.py`, `health.py`
- Clients: `backend/app/clients/llm.py`, `mcp.py`
- Config: `backend/app/config.py`, `backend/app/main.py` (CORS middleware)
- Frontend: `frontend/lib/api.ts`, `sse.ts`, `types.ts`, `storage.ts`, `useChatStream.ts`, `useSessionsStore.ts`
- Components: `frontend/components/chat/{Thread,Message,AssistantMessage,ToolTrace}.tsx`, `components/shell/{Header,Sidebar,ChannelSelector,AppShell}.tsx`
- Cards: `frontend/components/cards/{TableCard,ObjectCard,LogCard,CardRenderer}.tsx`

### External docs
- FastAPI security: https://fastapi.tiangolo.com/tutorial/security/
- Next.js CSP: https://nextjs.org/docs/app/building-your-application/configuring/content-security-policy
- Playwright Next.js: https://playwright.dev/docs/test-configuration
- GitHub Actions Python+Node: standard workflow templates

</canonical_refs>

<specifics>
## Specific Ideas

### SSE event matrix расширения (Plan 3.1 + 3.2)

К существующим 7 events добавляются:
| event | data |
|-------|------|
| `confirm_required` | `{tool_call_id, name, args, reason: "<dangerous keyword>"}` (Plan 3.2 SEC-01) |

`error.code` расширяется constants:
- `llm_rate_limit` (Plan 3.1)
- `llm_invalid_key` (Plan 3.1)
- `llm_network_error` (Plan 3.1)
- `llm_server_error` (Plan 3.1)
- `mcp_disconnected` (Plan 3.1)
- `user_declined` (Plan 3.2 SEC-01)
- `dangerous_keyword_blocked` (если backend решит блокировать без confirmation — fallback)

### CSP headers (Plan 3.2 SEC-02)

Подход 1 (рекомендуется): `next.config.ts` `async headers()`:
```ts
async headers() {
  return [{
    source: '/(.*)',
    headers: [
      { key: 'Content-Security-Policy', value: cspString },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
    ],
  }];
}
```

CSP в dev mode НЕ применять (Next HMR ломается) — `if (process.env.NODE_ENV === 'production')`.

### Dangerous keywords (Plan 3.2 SEC-01)

Регексп case-insensitive по args (как строка JSON):
- `\bУдалить\b`, `\bЗаписать\(`, `\bНачатьТранзакцию\b`, `\bОчистить\b`, `\bУстановить\b`
- + английский эквивалент если LLM генерит на en: `\bDelete\b`, `\bDrop\b`, `\bTruncate\b`
- Configurable через env `DANGEROUS_KEYWORDS` (опц.)

### Test coverage gaps (Plan 3.3 priorities)

Запустить `pytest --cov=app --cov-report=term-missing` локально → отчёт; в плане задокументировать конкретные uncovered branches.

Predict (без запуска): не покрыты вероятно:
- `orchestrator/loop.py` — error paths когда LLMClient бросает Network/5xx; max_iterations exit; некорректный tool_call id
- `orchestrator/cards.py` — fallback unknown tool type (текущая реализация — что возвращает?)
- `routes/sessions.py` — DELETE non-existent (404 path), PATCH invalid title
- `routes/connections.py` — DELETE cascade
- `clients/mcp.py` — SSE response parsing, Mcp-Session-Id ротация
- `clients/llm.py` — finish_reason="length" / "content_filter"

### Playwright config (Plan 3.3)

`frontend/playwright.config.ts`:
```ts
export default defineConfig({
  testDir: './e2e',
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:3010',
    reuseExistingServer: !process.env.CI,
  },
  use: { baseURL: 'http://localhost:3010', headless: true },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
```

MSW для backend mock: `e2e/mocks/handlers.ts` с handlers для `/connections`, `/sessions`, `/chat`.

### GitHub Actions CI (Plan 3.3)

`.github/workflows/ci.yml` structure (без точной yaml, оставляем планеру):
- on: pull_request + push to main
- jobs:
  - backend: setup-python 3.12, cache pip, install -e backend/, ruff, pytest --cov
  - frontend: setup-node 22, setup-pnpm, cache pnpm, install, type-check, lint, build, vitest
  - e2e: depends_on [backend, frontend], install playwright browsers (`--with-deps chromium`), run tests
- Concurrency group по ref — cancel-in-progress

### LogCard cursor-fetch endpoint (Plan 3.4)

Decision: реализовать как **stateful** endpoint, не stateless `/cards/log/load-more`. Stateful — store `card.payload.query_state` в DB при первом построении LogCard (или в memory с TTL), при load-more — look up state, добавить cursor, передать в `get_event_log`. Минимальный stateful: extend `cards` table с колонкой `state_json` (одна миграция).

Простой вариант: `POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more` body `{cursor}`, returns `{entries, next_cursor}`. Frontend LogCard уже имеет `onLoadMore` — wire-up.

</specifics>

<deferred>
## Deferred Ideas (НЕ в Phase 3)

- **ANON-01..03** (анонимизация) — v2
- **CARD-04..06** (Metric, References, Code) — v2
- **PROD-01..05** (quick prompts, slash, @-mentions, Cmd-K, Export) — v2
- **OAuth / SSO** — Out of Scope (REQUIREMENTS)
- **Email notifications** — Out of Scope
- **Vector search / RAG** — v2
- **Theming** — Out of Scope (только dark)

</deferred>

---

*Phase: 03-production-ready*
*Context gathered: 2026-05-14 — yolo mode, direct extraction*
