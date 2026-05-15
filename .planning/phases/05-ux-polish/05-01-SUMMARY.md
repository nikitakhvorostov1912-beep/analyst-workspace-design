---
phase: 05-ux-polish
plan: 01
subsystem: backend/llm-config + frontend/api
tags: [llm-config, crud, security, pydantic, fastapi, typescript]
dependency_graph:
  requires: [04-03]
  provides: [llm-config-crud-api, llm-config-test-endpoint, frontend-llm-api-client]
  affects: [05-02, 05-03, 05-04]
tech_stack:
  added: []
  patterns: [singleton-upsert, pydantic-strict, direct-httpx-test, header-api-key]
key_files:
  created:
    - backend/app/routes/llm_config.py
    - backend/tests/test_llm_config_route.py
  modified:
    - backend/app/models.py
    - backend/app/main.py
    - frontend/lib/types.ts
    - frontend/lib/api.ts
decisions:
  - INTEGER id=1 singleton workaround: таблица llm_settings имеет INTEGER PK; UPSERT на id=1, API возвращает алиас "default". Миграция v6 не нужна.
  - direct httpx вместо LLMClient: LLMClient имеет только stream_chat_completion (SSE), нет non-streaming метода. Для test endpoint (1-token, non-streaming) использован прямой httpx.AsyncClient с timeout=10s.
metrics:
  duration: 45m
  completed: 2026-05-15T13:44:49Z
---

# Phase 05 Plan 01: LLM Config CRUD Backend + Frontend API Client Summary

Backend CRUD (GET/POST/PATCH/DELETE /llm-config + POST /llm-config/test) с UPSERT singleton; frontend lib/api.ts с 5 функциями; API ключ не хранится на backend.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Pydantic модели LLM конфига | 916f824 | backend/app/models.py |
| 2 | Router /llm-config + регрессионные тесты | d3fed9f | backend/app/routes/llm_config.py, backend/app/main.py, backend/tests/test_llm_config_route.py |
| 3 | Frontend types + API client | df9189d | frontend/lib/types.ts, frontend/lib/api.ts |

## Endpoints Created (5)

| Endpoint | Method | Status | Description |
|----------|--------|--------|-------------|
| /llm-config | GET | 200 | Singleton или null |
| /llm-config | POST | 201 | UPSERT (INSERT OR REPLACE id=1) |
| /llm-config/default | PATCH | 200 | Partial update |
| /llm-config/default | DELETE | 204 | Удаление |
| /llm-config/test | POST | 200 | Валидация ключа через 1-token completion |

## Pydantic Models Added (5)

- `LLMConfigCreate`: strict + extra=forbid, endpoint http/https validation
- `LLMConfigUpdate`: optional поля, та же endpoint валидация
- `LLMConfigResponse`: без поля api_key (T-05-01 mitigated)
- `LLMConfigTestRequest`: strict, ключ только через header
- `LLMConfigTestResponse`: ok/error_code/error_message/duration_ms

## Frontend API Functions Added (5)

- `fetchLLMConfig()` — GET, возвращает null если не задан
- `saveLLMConfig(body)` — POST UPSERT
- `updateLLMConfig(patch)` — PATCH /default
- `deleteLLMConfig()` — DELETE /default, 204=success
- `testLLMConfig(body, apiKey)` — POST /test, apiKey в header X-LLM-API-Key

## Tests Added

- 14 pytest тестов: 14/14 зелёных
- Регрессия: 315/315 зелёных (не сломано ни одного из предыдущих)
- pnpm type-check: 0 ошибок
- ruff check app/routes/llm_config.py: 0 ошибок

## Security (Threat Model)

| Threat | Mitigation | Verified |
|--------|-----------|---------|
| T-05-01: api_key в response | LLMConfigResponse без поля api_key | test_post_creates_returns_response_without_api_key |
| T-05-02: Tampering POST/PATCH | Pydantic strict+extra=forbid | test_post_strict_rejects_extra_field |
| T-05-03: DoS через /test → outbound | timeout=10s в httpx.AsyncClient | в коде llm_config.py:_TEST_TIMEOUT_S=10.0 |
| T-05-05: error_message info leak | Truncate до 200 символов | в коде llm_config.py:_ERROR_MSG_MAX=200 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] LLMClient не имеет chat_completion метода**
- **Found during:** Task 2, чтение backend/app/clients/llm.py
- **Issue:** LLMClient имеет только `stream_chat_completion` (AsyncIterator, SSE streaming). Нет non-streaming `chat_completion`. Прямой вызов `LLMClient.chat_completion()` в test endpoint не возможен.
- **Fix:** Использован прямой `httpx.AsyncClient.post(f"{endpoint}/chat/completions", ...)` с timeout=10s. Это совпадает с запасным вариантом R3 в плане.
- **Files modified:** backend/app/routes/llm_config.py
- **Commit:** d3fed9f

## Known Stubs

Нет. Все 5 endpoints функциональны и протестированы.

## Threat Flags

Нет новых threat surfaces за пределами threat_model плана.

## Known Follow-ups for Plan 5.2/5.3/5.4

- **Plan 5.2 (Settings UI):** использует `fetchLLMConfig/saveLLMConfig/testLLMConfig` для формы настроек
- **Plan 5.3 (Onboarding):** использует `saveLLMConfig/testLLMConfig` для первичной настройки
- **Plan 5.4 (localStorage migration):** переименует/удалит `getLLMConfig()` из storage.ts; `fetchChat` начнёт использовать `fetchLLMConfig()` вместо localStorage для endpoint/model; api_key останется в sessionStorage

## Self-Check: PASSED

- [x] backend/app/routes/llm_config.py — FOUND
- [x] backend/app/models.py (LLMConfigCreate) — FOUND
- [x] backend/tests/test_llm_config_route.py — FOUND
- [x] Commits 916f824, d3fed9f, df9189d — FOUND
- [x] 14 тестов зелёные — VERIFIED
- [x] 315/315 регрессия — VERIFIED
- [x] pnpm type-check 0 ошибок — VERIFIED
