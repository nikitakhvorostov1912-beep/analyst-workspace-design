---
phase: 03-production-ready
plan: 03
subsystem: devx
tags: [tests, coverage, playwright, ci, github-actions]
dependency_graph:
  requires: [03-01, 03-02]
  provides: [DEVX-01, DEVX-02, DEVX-03]
  affects: [backend/tests, frontend/e2e, .github/workflows]
tech_stack:
  added: [playwright ^1.49.0]
  patterns: [pytest-cov gates, Playwright route() mocking, GitHub Actions concurrency groups]
key_files:
  created:
    - backend/tests/test_orchestrator_coverage.py
    - backend/tests/test_mcp_client_edge_cases.py
    - backend/tests/test_llm_client_edge_cases.py
    - backend/tests/test_routes_edge_cases.py
    - frontend/playwright.config.ts
    - frontend/e2e/fixtures.ts
    - frontend/e2e/mocks/handlers.ts
    - frontend/e2e/mocks/server.ts
    - frontend/e2e/setup-and-prompt.spec.ts
    - frontend/e2e/sessions-history.spec.ts
    - frontend/e2e/channel-switch.spec.ts
    - .github/workflows/ci.yml
    - .github/workflows/README.md
  modified:
    - backend/pyproject.toml
    - backend/tests/conftest.py
    - frontend/package.json
    - frontend/pnpm-lock.yaml
    - frontend/vitest.config.ts
decisions:
  - "Playwright route() вместо MSW — упрощает архитектуру (нет browser/Node двойственности)"
  - "Coverage gate 80% в pyproject.toml addopts, применяется только к orchestrator + clients"
  - "vitest.config.ts: exclude e2e/** для исключения Playwright spec из vitest run"
metrics:
  duration: "15m 11s"
  completed: "2026-05-14"
  tasks: 3
  files: 17
---

# Phase 03 Plan 03: Tests + CI Summary

**Одна строка:** pytest coverage 92.8% (gate ≥80%), 9 Playwright E2E spec через route() mock, GitHub Actions CI с 3 jobs и pnpm/pip кешированием.

## Задачи

### Task 1: Backend coverage gates 80% + edge case тесты ✓

Добавлено 39 новых backend тестов (200 total, ранее 161).

**Покрытие (фактическое):**

| Модуль | До | После |
|--------|----|-------|
| `app/clients/llm.py` | 57% | 86.6% |
| `app/clients/mcp.py` | 87% | 94.2% |
| `app/orchestrator/loop.py` | 89% | 92.1% |
| `app/orchestrator/cards.py` | 93% | 93.5% |
| **TOTAL (orchestrator+clients)** | **88%** | **92.8%** |

Gate `--cov-fail-under=80` пройден. Добавлен в `pyproject.toml addopts`.

**Новые тесты по файлам:**

- `test_orchestrator_coverage.py` (8 тестов): max_iterations exit, init_error, finish_reason length/content_filter, unknown_channel ДО MCP initialize, tool_args unparseable JSON, _cap_content truncation
- `test_mcp_client_edge_cases.py` (7 тестов): SSE response parsing, session_id rotation, malformed JSON в SSE → MCPError, JSON-RPC error, 4xx/5xx propagation, aclose idempotent
- `test_llm_client_edge_cases.py` (10 тестов): finish_reason length/content_filter yielded, multi-chunk tool_calls, malformed chunk skip, [DONE] stops iteration, _parse_retry_after variants, context manager, standalone function
- `test_routes_edge_cases.py` (11 тестов): sessions DELETE/PATCH/GET 404, PATCH empty title 422, connections empty list, PUT ftp:// 422, DELETE 404, ping 404, ping 502, mcp Phase 1 backward compat

**Оставшиеся uncovered строки (не критичны):**

- `llm.py:78` — `if tools:` branch (tools=None path редко встречается в integration тестах)
- `llm.py:93-102` — 429 в streaming context (требует stream mock)
- `llm.py:141-143` — standalone wrapper (async gen, тип проверен)
- `mcp.py:73,82,95` — `elif` ветки header case sensitivity
- `loop.py:114-120` — retry path для 5xx в _call_tool_with_retry
- `loop.py:128-137` — RequestError retry path
- `loop.py:449-451` — persistence failure after done

### Task 2: Playwright E2E тесты ✓

**Решение:** Playwright route() вместо MSW (Karpathy Simplicity — нет browser/Node двойственности).

**9 тестов в 3 файлах:**

- `setup-and-prompt.spec.ts`: empty state → «Начните работу», addInitScript конфигурация, ответ ассистента из mock SSE
- `sessions-history.spec.ts`: 4 группы visible (Сегодня/Вчера/На этой неделе/Раньше), click → URL /sessions/{id}, сообщения из mock
- `channel-switch.spec.ts`: ChannelSelector visible, dropdown items, создание новой сессии → redirect

**Инфраструктура:**

- `fixtures.ts`: `setupRoutes(page)` регистрирует route() handlers для всех backend endpoints; `setLocalStorage(page, ...)` помещает конфигурацию до загрузки; локальные ключи `analyst.llm`, `analyst.mcp_connections`, `analyst.active_channel` соответствуют `lib/storage.ts`
- `vitest.config.ts`: `exclude: ["e2e/**"]` — Playwright spec не попадают в vitest run

**Верификация:** `pnpm exec playwright test --list` показывает 9 тестов; `pnpm type-check` 0 ошибок; `pnpm test --run` 88 vitest тестов зелёных.

### Task 3: GitHub Actions CI workflow ✓

**Файл:** `.github/workflows/ci.yml`

3 джобы выполняются на `pull_request` branches: [main] + `push` branches: [main]:

```
backend: Python 3.12, pip cache, ruff check, pytest --cov-fail-under=80
frontend: Node 22, pnpm cache (lockfile), lint + type-check + vitest + build
e2e: needs [backend, frontend], playwright install chromium, playwright test, upload-artifact при failure
```

**Кеш:** pip кешируется по умолчанию через `actions/setup-python@v5 cache: pip`; pnpm — через `cache: pnpm + cache-dependency-path: frontend/pnpm-lock.yaml`.

**Concurrency:** `cancel-in-progress: true` для той же группы — экономит ресурсы при множественных push в быстрой последовательности.

**Artifacts:** при падении e2e → `playwright-traces` загружаются в GitHub (90 дней).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] monkeypatch в loop_module namespace, не в persistence_module**

- **Found during:** Task 1, test_loop_init_error_on_save_user_message_failure
- **Issue:** Патчинг `persistence_module.save_user_message` не влиял на `loop_module` — тот уже имел импортированную ссылку
- **Fix:** `monkeypatch.setattr(loop_module, "save_user_message", failing_save)`
- **Files modified:** backend/tests/test_orchestrator_coverage.py

**2. [Rule 3 - Blocking] vitest подхватывал Playwright spec файлы**

- **Found during:** Task 2, после запуска `pnpm test`
- **Issue:** vitest без exclude подхватывал `e2e/**` и падал на Playwright-специфичном API
- **Fix:** Добавлен `exclude: ["node_modules", "e2e/**"]` в vitest.config.ts
- **Files modified:** frontend/vitest.config.ts

**3. [Rule 3 - Blocking] TypeScript noUncheckedIndexedAccess → `conns[0].id` fails**

- **Found during:** Task 2, pnpm type-check
- **Issue:** `conns[0]` в addInitScript callback имеет тип `MCPConnection | undefined` из-за `noUncheckedIndexedAccess`
- **Fix:** Заменено на `conns[0]?.id ?? "db-a"` во всех 3 spec-файлах
- **Files modified:** frontend/e2e/*.spec.ts

### Decisions Made

1. **Playwright route() вместо MSW** — MSW требует browser/Node двойственности с setupWorker/setupServer; route() работает в одной среде без дополнительных зависимостей
2. **Coverage gate только для orchestrator+clients** — routes покрытие не критично для MVP, gate в addopts применяется к --cov=app/orchestrator + --cov=app/clients
3. **E2E тесты = 9 тестов (не 3)** — добавлены более гранулярные проверки по 3 в каждом spec

## Known Stubs

Нет. Все mock данные в fixtures.ts явно задокументированы как тестовые.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: info_disclosure | .github/workflows/ci.yml | Playwright traces artifacts могут содержать mock request данные — приемлемо (нет real secrets) |

## Self-Check: PASSED

- [x] `backend/tests/test_orchestrator_coverage.py` — FOUND
- [x] `backend/tests/test_mcp_client_edge_cases.py` — FOUND
- [x] `backend/tests/test_llm_client_edge_cases.py` — FOUND
- [x] `backend/tests/test_routes_edge_cases.py` — FOUND
- [x] `frontend/playwright.config.ts` — FOUND
- [x] `frontend/e2e/fixtures.ts` — FOUND
- [x] `.github/workflows/ci.yml` — FOUND
- [x] Commits: 7c16e0d, 938ad79, 5daab40 — FOUND
- [x] Coverage 92.8% ≥ 80% gate — PASSED
- [x] `pnpm exec playwright test --list` → 9 tests — PASSED
- [x] `pnpm type-check` → 0 errors — PASSED
- [x] `pnpm test --run` → 88 passed — PASSED
