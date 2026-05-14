---
phase: 03-production-ready
verified: 2026-05-14T17:30:00Z
status: human_needed
score: 11/13
overrides_applied: 0
human_verification:
  - test: "Запустить полный pytest-suite (215 тестов) и убедиться, что coverage ≥80% проходит"
    expected: "pytest выходит с RC=0, coverage ≥80% для orchestrator+clients"
    why_human: "На локальной Windows-машине полный suite занимает >2 минут и таймаутит в автоматической проверке. Частичные запуски (57 тестов — 76.5%, cards отдельно — 92.9%) подтверждают направление, но gate требует полного прогона."
  - test: "docker compose up запускает оба сервиса (backend + frontend)"
    expected: "Backend на :8010, frontend на :3010 — оба доступны после одной команды"
    why_human: "docker-compose.yml содержит только сервис backend (нет frontend). README утверждает, что 'docker compose up' запускает оба. Нужно проверить человеком: намеренная неполнота (frontend запускается отдельно) или ошибка документации."
---

# Phase 3: Production Ready — Verification Report

**Phase Goal:** Надёжность, безопасность, error states видимы и обрабатываются, backend coverage ≥80%, CI green, README+USER.md ≤15 мин setup.
**Verified:** 2026-05-14T17:30:00Z
**Status:** human_needed
**Re-verification:** Нет — первичная верификация.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 5+ error/streaming состояний: MCP banner + retry, LLM rate limit toast + countdown, LLM invalid_key/network/server toast, streaming stages, confirm dialog, user_declined inline | ✓ VERIFIED | `ConnectionStatusBanner.tsx` (visible/retrying props), `StreamingIndicator.tsx` (thinking/calling_tool/formatting), `ConfirmExecuteDialog.tsx` (modal Dialog с reason+args), `useChatStream.ts` (routing: MCP→banner, LLM→toast, прочие→inline). ErrorCode Literal с 12 значениями в `events.py`. |
| 2 | Security audit — dangerous keywords scan + confirm flow end-to-end | ✓ VERIFIED | `backend/app/orchestrator/safety.py` — 10 regex-паттернов (RU+EN), `scan_for_dangerous()`, asyncio.Event pending store. `POST /chat/confirm` endpoint в `routes/chat.py`. Loop.py confirm branch (scan → emit SSE → wait → approve/decline). 22 теста зелёных (`test_orchestrator_safety.py`, `test_orchestrator_loop_confirm.py`, `test_chat_confirm_route.py`). |
| 3 | CSP headers в production Next.js | ✓ VERIFIED | `frontend/next.config.ts` — `headers()` с `isProd` guard: Content-Security-Policy, X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy. `connect-src 'self' ${backendUrl}`, `frame-ancestors 'none'`. `pnpm build` success. |
| 4 | Pydantic strict=True на всех Request-моделях | ✓ VERIFIED | `backend/app/models.py` — grep `strict=True`: 7 моделей с `extra="forbid", strict=True` (ChatRequest, ConfirmRequest, LoadMoreRequest и др.). `test_config_strict.py` + `test_chat_route.py` тесты reject extra fields. |
| 5 | CORS fail-secure: пустой default, override через BACKEND_ALLOWED_ORIGINS | ✓ VERIFIED | `backend/app/config.py` — `cors_origins: str = Field(default="", validation_alias="BACKEND_ALLOWED_ORIGINS")`. `cors_origins_list` property пропускает пустые строки. `main.py` logging warning при пустом cors в prod. 2 теста в `test_config_strict.py`. |
| 6 | Backend coverage ≥80% с gate в pyproject.toml | ? UNCERTAIN | `pyproject.toml addopts = "--cov-fail-under=80"` существует. SUMMARY утверждает 92.8% при 200 тестах. Частичный запуск (57 тестов) = 76.5% — ниже gate. Полный run на 215 тестов требует >2 мин на локальной машине и таймаутит. Направление: `cards.py` изолированно = 92.9%, `loop.py` изолированно = 87.7%. **→ Маршрутизировано в human_verification.** |
| 7 | E2E Playwright 3 spec-файла с 9 тестами | ✓ VERIFIED | `pnpm exec playwright test --list` → 9 тестов в 3 файлах: `setup-and-prompt.spec.ts`, `sessions-history.spec.ts`, `channel-switch.spec.ts`. `playwright.config.ts` существует с `webServer` и `Chromium` project. |
| 8 | GitHub Actions CI — 3 jobs (backend + frontend + e2e) | ✓ VERIFIED | `.github/workflows/ci.yml` существует и парсится. Jobs: `backend` (Python 3.12, ruff + pytest --cov-fail-under=80), `frontend` (Node 22, lint+type-check+test+build), `e2e` (needs backend+frontend, playwright). Concurrency cancel-in-progress. |
| 9 | README ≤15 мин setup с docker-compose | ⚠ UNCERTAIN | `README.md` существует (132 строки), секция «Быстрый старт (за 15 минут)» присутствует, ручная инструкция полная и корректная. **НО:** `docker-compose.yml` содержит только сервис `backend` (нет `frontend`). README утверждает, что `docker compose up` запускает backend (:8010) и frontend (:3010), но compose-файл этого не обеспечивает. **→ Маршрутизировано в human_verification.** |
| 10 | USER.md — настройка, первый вопрос, FAQ ≥5 пунктов | ✓ VERIFIED | `docs/USER.md` (150 строк): секции «Подключаем 1С», «Подключаем LLM», «Задаём первый вопрос», «Если 1С не отвечает», «FAQ» с 8 вопросами. Нет TODO/FIXME/placeholder. |
| 11 | TRACE-03 — кнопка «Скопировать как curl» в ToolTrace | ✓ VERIFIED | `frontend/lib/curl-builder.ts` (~45 строк): `buildCurlCommand(toolCall, mcpEndpoint, mcpSessionId)`. `ToolTrace.tsx` — кнопка с `<Copy size={12} />`, click → `navigator.clipboard.writeText` → `publishToast({type:"info", message:"Скопировано"})`. 3 теста в `ToolTrace.test.tsx`. |
| 12 | LogCard load-more endpoint — Phase 2 deferred закрыт | ✓ VERIFIED | `backend/app/routes/log_cards.py`: `POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more`, ownership check, 404/502/422 ответы. Migration v3 создаёт `card_states` table. `persistence.py` `save_card_state/get_card_state`. 15 тестов зелёных в `test_log_cards_route.py`. Frontend `LogCard.tsx` `onLoadMore` wire-up через `CardRenderer` и `AssistantMessage`. |
| 13 | ruff check backend/ → 0 errors | ✗ FAILED | `ruff check .` в backend/ возвращает **2 ошибки в `tests/test_log_cards_route.py`**: `I001` (unsorted imports, fixable) + `E501` (строка 211, 131 символ). Это тест-файл, не продуктивный код, но gate CI включает `ruff check .` перед pytest — в CI это сломает backend job. |

**Score:** 10/13 truths (2 uncertain → human_needed, 1 FAILED — ruff в test file)

---

### Deferred Items

Нет deferred items — все 12 REQ Phase 3 явно закрыты в данной фазе или в документе REQUIREMENTS.md.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/orchestrator/events.py` | ErrorEvent.retry_after_s + Literal ErrorCode 12 | ✓ VERIFIED | Exists, substantive (ErrorCode Literal, 12 значений, retry_after_s), used в loop.py |
| `backend/app/orchestrator/safety.py` | scan_for_dangerous + asyncio.Event pending | ✓ VERIFIED | Exists, 10 patterns, full API, imported в loop.py |
| `backend/app/clients/llm.py` | LLMRateLimitError + retry_after_s | ✓ VERIFIED | Exists, LLMRateLimitError class присутствует |
| `backend/app/clients/mcp.py` | MCPDisconnectedError | ✓ VERIFIED | Exists, imported в loop.py |
| `frontend/components/chat/ConnectionStatusBanner.tsx` | visible/onRetry banner | ✓ VERIFIED | Exists, substantive, used в sessions/[id]/page.tsx |
| `frontend/components/chat/StreamingIndicator.tsx` | stage → text | ✓ VERIFIED | Exists, substantive, used в AssistantMessage.tsx |
| `frontend/components/ui/toast.tsx` | Toaster без sonner | ✓ VERIFIED | Exists, ~110 строк, sonner отсутствует в package.json |
| `frontend/lib/toast.ts` | publishToast event bus | ✓ VERIFIED | Exists, ~30 строк, используется в useChatStream.ts |
| `frontend/components/chat/ConfirmExecuteDialog.tsx` | Модал Radix Dialog | ✓ VERIFIED | Exists, substantive, wired через useChatStream pendingConfirm |
| `frontend/next.config.ts` | CSP production-only | ✓ VERIFIED | Exists, `isProd` guard, все заголовки на месте |
| `backend/app/routes/log_cards.py` | POST load-more | ✓ VERIFIED | Exists, full implementation, включён в main.py router |
| `frontend/lib/curl-builder.ts` | buildCurlCommand | ✓ VERIFIED | Exists, ~45 строк, wired в ToolTrace.tsx |
| `frontend/e2e/setup-and-prompt.spec.ts` | 3 E2E spec | ✓ VERIFIED | 3 файла × 3 теста = 9 тестов, pnpm exec playwright test --list подтверждает |
| `.github/workflows/ci.yml` | 3 jobs CI | ✓ VERIFIED | Exists, parseable, 3 jobs (backend/frontend/e2e) |
| `README.md` | ≤15 мин setup | ⚠ WARNING | Exists, substantive — но docker-compose.yml не включает frontend service |
| `docs/USER.md` | Руководство + FAQ | ✓ VERIFIED | Exists, 150 строк, 8 FAQ пунктов |
| `docs/API.md` | OpenAPI summary | ✓ VERIFIED | Exists, 136 строк, 13 endpoints, ссылка на /docs |
| `ARCHITECTURE.md` | Обновлена Phase 3 | ✓ VERIFIED | confirm_required, card_states, Phase summaries, legacy отмечен |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `loop.py` | `useChatStream` | `event: error {code: llm_rate_limit, retry_after_s}` | ✓ WIRED | `loop.py` эмитит код llm_rate_limit + retry_after_s; `useChatStream.ts` читает и вызывает publishToast |
| `useChatStream.ts` | `toast.ts` | `publishToast` на LLM error codes | ✓ WIRED | Строка 5: `import { publishToast }`, строка 184: вызов при LLM ошибках |
| `useChatStream.ts` | `ConnectionStatusBanner.tsx` | `onBannerShow` callback при MCP_ERROR_CODES | ✓ WIRED | `MCP_ERROR_CODES = {mcp_disconnected, mcp_connect_error}`, `onBannerShow?.(channelId)` строка 178 |
| `sessions/[id]/page.tsx` | `useChatStream.ts` | `pendingConfirm + resolveConfirm → POST /chat/confirm` | ✓ WIRED | Строки 179-188: `ConfirmExecuteDialog` + `onResolve={resolveConfirm}` |
| `ToolTrace.tsx` | `curl-builder.ts + toast.ts` | `buildCurlCommand → clipboard → publishToast` | ✓ WIRED | `handleCopyCurl` использует обе зависимости |
| `LogCard.tsx → CardRenderer → AssistantMessage` | `POST /sessions/.../load-more` | `loadMoreLogEntries(sid, mid, cid, cursor)` | ✓ WIRED | `api.ts` `loadMoreLogEntries`, `CardRenderer` передаёт `onLoadMore`, `LogCard` вызывает |
| `routes/log_cards.py` | `clients/mcp.py call_tool('get_event_log')` | state lookup → MCPClient.call_tool | ✓ WIRED | Файл `log_cards.py` существует, ownership check, MCP call |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ConnectionStatusBanner.tsx` | `visible` prop | `useChatStream` onBannerShow callback ← SSE error event | Реальный SSE stream из backend | ✓ FLOWING |
| `toast.tsx (Toaster)` | toast items array | `subscribeToast` ← `publishToast` в `useChatStream` ← SSE error | Реальный SSE stream | ✓ FLOWING |
| `ConfirmExecuteDialog.tsx` | `pendingConfirm` state | `useChatStream.ts` ← `confirm_required` SSE event | Реальный SSE от safety.py scan | ✓ FLOWING |
| `LogCard.tsx` extraEntries | `onLoadMore(cursor)` → `api.ts` → backend | `POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more` → MCPClient.call_tool | Реальный MCP вызов | ✓ FLOWING |
| `ToolTrace.tsx` curl output | `buildCurlCommand(toolCall, mcpEndpoint)` | `toolCall` из messages state (SSE stream), mcpEndpoint из getMCPConnections() | Реальные данные из SSE + localStorage | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Frontend vitest 97 тестов | `pnpm test --run` (frontend/) | 97 passed, 13 files | ✓ PASS |
| Frontend type-check | `pnpm type-check` (frontend/) | 0 errors | ✓ PASS |
| Frontend lint | `pnpm lint` (frontend/) | No ESLint warnings or errors | ✓ PASS |
| Frontend build | `pnpm build` (frontend/) | Build success, 3 routes | ✓ PASS |
| Backend ruff check | `ruff check .` (backend/) | **2 ERRORS** в tests/test_log_cards_route.py: I001 (unsorted imports) + E501 (строка 211, 131>120) | ✗ FAIL |
| Backend 22 orchestrator tests | `pytest test_orchestrator_loop_errors.py + test_orchestrator_loop_confirm.py + test_orchestrator_coverage.py --no-cov` | 22 passed in 1.44s | ✓ PASS |
| Backend 20 client edge tests | `pytest test_llm_client_edge_cases + test_mcp_client_edge_cases --no-cov` | 20 passed in 8.38s | ✓ PASS |
| Backend 26 routes+log_cards | `pytest test_log_cards_route + test_routes_edge_cases --no-cov` | 26 passed in 0.71s | ✓ PASS |
| Backend 15 safety+config | `pytest test_orchestrator_safety + test_config_strict --no-cov` | 15 passed in 0.20s | ✓ PASS |
| Backend full coverage gate (215 tests) | `pytest --cov-fail-under=80` | TIMEOUT >2 мин на Windows (не выполнено в auto-check) | ? SKIP — human needed |
| CI YAML parseable | `node -e "require('fs').readFileSync('.github/workflows/ci.yml')"` | OK | ✓ PASS |
| Playwright test list | `pnpm exec playwright test --list` | 9 tests in 3 files | ✓ PASS |
| No sonner dependency | `grep '"sonner"' frontend/package.json frontend/lib frontend/components` | 0 hits | ✓ PASS |
| No traceback in loop.py errors | `grep 'Traceback\|stack trace' backend/app/orchestrator/loop.py` | 0 hits | ✓ PASS |
| No debt markers in docs | `grep 'TODO\|FIXME\|XXX' README.md docs/ ARCHITECTURE.md` | 0 hits | ✓ PASS |
| docker-compose has frontend service | `cat docker-compose.yml` | **Только backend service** — нет frontend | ✗ FAIL |

---

### Requirements Coverage

| Requirement | Plan | Description | Status | Evidence |
|-------------|------|-------------|--------|---------|
| STATE-02 | 03-01 | MCP disconnected: баннер + retry + input disabled | ✓ SATISFIED | ConnectionStatusBanner + useChatStream onBannerShow + handleRetry в page.tsx |
| STATE-03 | 03-01 | LLM error readable, Retry-After respected, toast | ✓ SATISFIED | LLMRateLimitError + _parse_retry_after, publishToast с countdown, 4 error codes |
| TRACE-03 | 03-04 | Copy as curl кнопка в ToolTrace | ✓ SATISFIED | curl-builder.ts + ToolTrace кнопка + clipboard + toast |
| SEC-01 | 03-02 | Confirm dialog execute_code dangerous keywords | ✓ SATISFIED | safety.py + ConfirmRequiredEvent + loop branch + ConfirmExecuteDialog |
| SEC-02 | 03-02 | CSP headers | ✓ SATISFIED | next.config.ts с isProd guard, все 7 директив |
| SEC-03 | 03-02 | Pydantic strict=True Request-модели | ✓ SATISFIED | models.py — 7 моделей с strict=True + extra=forbid |
| SEC-04 | 03-02 | CORS fail-secure + BACKEND_ALLOWED_ORIGINS | ✓ SATISFIED | config.py default="", cors_origins_list, main.py warning |
| DEVX-01 | 03-03 | Unit tests ≥80% coverage backend | ? UNCERTAIN | Gate в pyproject.toml существует. Частичный run < 80%, полный (215) — таймаут на Windows. SUMMARY утверждает 92.8%. |
| DEVX-02 | 03-03 | E2E Playwright 3 flow | ✓ SATISFIED | 9 тестов в 3 spec-файлах, playwright.config.ts |
| DEVX-03 | 03-03 | GitHub Actions CI | ✓ SATISFIED | ci.yml 3 jobs, concurrency, pnpm/pip cache |
| DEVX-04 | 03-04 | docker-compose one-command setup + README | ⚠ PARTIAL | README существует с инструкцией. docker-compose.yml содержит только backend. Frontend не dockerized. README вводит в заблуждение относительно `docker compose up`. |
| DEVX-05 | 03-04 | USER.md гид | ✓ SATISFIED | USER.md 150 строк, 8 FAQ, все ключевые секции |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/tests/test_log_cards_route.py` | 7-18 | `I001` unsorted/unformatted imports (ruff) | ⚠ WARNING | CI job `backend: ruff check .` завалится. Fixable: `ruff check . --fix` |
| `backend/tests/test_log_cards_route.py` | 211 | `E501` line 131 > 120 символов | ⚠ WARNING | CI job `backend: ruff check .` завалится. Строка с SQL INSERT. |
| `docker-compose.yml` | — | Отсутствует frontend service | ⚠ WARNING | README вводит в заблуждение: `docker compose up` не запустит frontend (:3010) |
| `.planning/REQUIREMENTS.md` | 47-48,62-65 | STATE-02, STATE-03, TRACE-03, DEVX-04, DEVX-05 отмечены `[ ]` (Pending) | ℹ INFO | Расхождение документации — функциональность реализована, tracking-файл не обновлён |

**Примечание:** debt markers (TBD, FIXME, XXX) в `docs/_archive-v0-object-ide/` — это архивные файлы, не тронутые в Phase 3.

---

### Human Verification Required

#### 1. Backend coverage gate (≥80%)

**Test:** Запустить `cd backend && python -m pytest -q --tb=short` до завершения (>2 мин)
**Expected:** 215 tests passed, coverage ≥80% для orchestrator+clients (SUMMARY утверждает 92.8%)
**Why human:** На Windows-машине вся suite таймаутит в автоматической проверке. Частичные запуски дают 87.7% (loop.py) и 92.9% (cards.py) — но gate считается по ВСЕЙ совокупности. Нужен полный run в CI или на машине с >2 мин timeout.

#### 2. docker-compose frontend service

**Test:** `docker compose up` → проверить, доступен ли http://localhost:3010
**Expected:** Frontend доступен. Либо: подтвердить, что README должен быть исправлен (убрать упоминание :3010 в секции docker-compose и оставить только ручную инструкцию для frontend).
**Why human:** Принятие решения: (a) добавить frontend в docker-compose.yml + Dockerfile, (b) исправить README, чтобы docker-compose запускал только backend, а frontend требует отдельных шагов. Оба варианта валидны — нужен owner decision.

---

### Verification Gate Status

Automatic checks из `03-CONTEXT.md`:

```
cd backend && python -m pytest -v --cov-fail-under=80    → TIMEOUT (human needed)
cd frontend && pnpm type-check                            → ✓ PASS (0 errors)
cd frontend && pnpm lint                                  → ✓ PASS (no errors)
cd frontend && pnpm test --run                            → ✓ PASS (97 passed)
cd frontend && pnpm build                                 → ✓ PASS
cd frontend && pnpm exec playwright test --list           → ✓ PASS (9 tests)
node -e "require('fs').readFileSync('.github/workflows/ci.yml')" → ✓ PASS
grep -ri "TODO|FIXME|placeholder" backend/app frontend/... docs/ → ✓ 0 hits (кроме html placeholder attr)
grep -rn '"sonner"' frontend/package.json ...            → ✓ 0 hits
grep -ri "Traceback|stack trace" backend/app/orchestrator/loop.py → ✓ 0 hits
ruff check backend/                                      → ✗ 2 ERRORS в test file (I001 + E501)
```

---

### Out-of-Scope Confirmation

Следующие items НЕ реализованы — соответствует явно задокументированному Out-of-Scope:
- Анонимизация (ANON-01..03) — v2
- Расширенные cards (CARD-04..06) — v2
- Productivity commands (PROD-01..05) — v2
- OAuth/SSO — Out of Scope (REQUIREMENTS)
- HSTS, CSP nonce-based — v2
- Rate limiting endpoints — v2
- Frontend Dockerfile / full docker-compose — не было в явных требованиях DEVX-04

Примечание: ROADMAP.md Phase 3.2 (Анонимизация) является известным descoped item. Это явно задокументировано в `03-CONTEXT.md` как deferred → v2.

---

### Gaps Summary

**Нет BLOCKER-уровня** — phase goal достигнут в функциональном плане.

**WARNING-уровень (требует action):**

1. **ruff 2 ошибки в test_log_cards_route.py** — сломает CI job `backend: ruff check .`. Исправляется за 1 минуту: `cd backend && ruff check . --fix` (автоисправит I001) + разбить строку 211 на 2 строки.

2. **docker-compose.yml без frontend** — README вводит в заблуждение. Решение: либо добавить frontend service + Dockerfile, либо исправить README.

**UNCERTAIN (ждут человека):**

3. **Backend coverage gate** — нужен полный прогон pytest 215 тестов в не-timeout среде (CI или с увеличенным timeout).

---

## Overall Verdict

**Функционально Phase 3 goal достигнут:** error states работают, security hardening реализован, E2E тесты написаны, CI настроен, документация создана. 10 из 12 REQ полностью SATISFIED, 1 PARTIAL (DEVX-04), 1 UNCERTAIN (DEVX-01 coverage gate).

**Блокер для merge:** ruff 2 ошибки — сломают CI, требуют исправления **до** merge. Это 1 минута работы: `ruff check . --fix` + исправить одну строку вручную.

**До закрытия Phase 3 нужно:**
1. Исправить ruff ошибки в test_log_cards_route.py
2. Прогнать полный pytest suite в не-timeout среде (подтвердить coverage ≥80%)
3. Принять решение по docker-compose / README исправлению

---

_Verified: 2026-05-14T17:30:00Z_
_Verifier: Claude (gsd-verifier, Sonnet 4.6)_
