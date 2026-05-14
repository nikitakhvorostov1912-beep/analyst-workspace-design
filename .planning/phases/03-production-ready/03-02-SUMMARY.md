---
phase: 03-production-ready
plan: 02
subsystem: security
tags: [security, csp, pydantic, cors, asyncio, sse, confirm-dialog, react, fastapi]

# Dependency graph
requires:
  - phase: 03-production-ready/03-01
    provides: "Literal ErrorCode с user_declined + dangerous_keyword_blocked, ErrorEvent.retry_after_s"
provides:
  - "safety.py — DANGEROUS_KEYWORDS regex list, scan_for_dangerous(), pending confirmation store (asyncio.Event)"
  - "register_pending_confirmation / resolve_pending_confirmation / wait_for_confirmation API"
  - "ConfirmRequiredEvent Pydantic-модель (strict=True, extra=forbid)"
  - "loop.py — SEC-01 ветка: scan → emit confirm_required → wait → approve/decline → continue/stop"
  - "POST /chat/confirm endpoint — 204/404/422, body ConfirmRequest strict"
  - "Все Request-модели Pydantic: extra=forbid + strict=True (ChatRequest, SessionCreate, SessionPatch, MCPConnectionCreate/Update, ConfirmRequest)"
  - "Settings.cors_origins default='' (fail-secure); парсер из BACKEND_ALLOWED_ORIGINS env"
  - "Settings.environment Literal[dev,prod]"
  - "next.config.ts CSP headers (production-only): default-src + connect-src + frame-ancestors none"
  - "ConfirmExecuteDialog — модальный Dialog с reason + args JSON + кнопки Выполнить/Отменить"
  - "useChatStream — pendingConfirm state + resolveConfirm(approved) → POST /chat/confirm"
  - "postChatConfirm() в lib/api.ts"
  - "ConfirmRequiredPayload тип + confirm_required в SSEEvent union в lib/types.ts"
affects: [03-03, 03-04]

# Tech tracking
tech-stack:
  added:
    - "@radix-ui/react-dialog (уже был через радиксUI family — dialog.tsx обёртка добавлена)"
  patterns:
    - "asyncio.Event coordination между SSE generator и HTTP endpoint через module-level dict"
    - "Pydantic strict=True + extra=forbid на всех Request-моделях — SEC-03"
    - "CSP production-only через next.config.ts headers() — dev не ломается HMR"
    - "CORS fail-secure: пустой дефолт cors_origins, override через BACKEND_ALLOWED_ORIGINS"
    - "TDD: test(03-02) RED commit → feat(03-02) GREEN commit"

key-files:
  created:
    - "backend/app/orchestrator/safety.py"
    - "backend/tests/test_orchestrator_safety.py"
    - "backend/tests/test_orchestrator_loop_confirm.py"
    - "backend/tests/test_chat_confirm_route.py"
    - "backend/tests/test_config_strict.py"
    - "frontend/components/chat/ConfirmExecuteDialog.tsx"
    - "frontend/components/ui/dialog.tsx"
    - "frontend/components/chat/__tests__/ConfirmExecuteDialog.test.tsx"
    - "frontend/__tests__/next-config.test.ts"
  modified:
    - "backend/app/orchestrator/events.py (ConfirmRequiredEvent добавлен)"
    - "backend/app/orchestrator/loop.py (SEC-01 confirm ветка)"
    - "backend/app/routes/chat.py (POST /chat/confirm)"
    - "backend/app/models.py (strict=True на всех Request-моделях + ConfirmRequest)"
    - "backend/app/config.py (cors_origins fail-secure + environment Literal)"
    - "backend/app/main.py (CORS warning при пустом prod)"
    - "frontend/next.config.ts (CSP headers production-only)"
    - "frontend/lib/types.ts (ConfirmRequiredPayload + confirm_required SSEEvent)"
    - "frontend/lib/api.ts (postChatConfirm)"
    - "frontend/components/chat/useChatStream.ts (pendingConfirm + resolveConfirm)"
    - "frontend/app/page.tsx (ConfirmExecuteDialog интеграция)"
    - "frontend/app/sessions/[id]/page.tsx (ConfirmExecuteDialog интеграция)"
    - "frontend/components/chat/__tests__/useChatStream.test.tsx (3 новых теста confirm flow)"

key-decisions:
  - "asyncio.Event в module-level dict (safety._pending) — работает на single-worker; multi-worker требует Redis (задокументировано в README как ограничение)"
  - "CORS fail-secure: default cors_origins='' → 0 origins в prod без env → явная ошибка, не молчаливое открытие"
  - "CSP только production: dev режим HMR требует unsafe-eval, не ломаем DX"
  - "Pydantic strict=True только на Request-моделях, не на Response — Response strict замедляет сериализацию"
  - "Confirm dialog не закрывает SSE-стрим — backend сам эмитит error event после approve/decline/timeout"

patterns-established:
  - "SEC-01 pattern: scan → emit SSE → wait asyncio.Event → act — переиспользуем для будущих security gates"
  - "Fail-secure default: любой security-relevant config дефолтно ограничительный (CORS пустой, CSP в prod)"
  - "TDD для security модулей: RED (behavior tests) → GREEN (implementation) — оба коммита разделены"

requirements-completed: [SEC-01, SEC-02, SEC-03, SEC-04]

# Metrics
duration: 60min
completed: 2026-05-14
---

# Phase 3 Plan 02: Security Hardening Summary

**SEC-01..04 полностью закрыты: dangerous keyword confirm dialog через asyncio.Event coordination, CSP headers production-only, Pydantic strict=True на Request-моделях, CORS fail-secure c BACKEND_ALLOWED_ORIGINS**

## Performance

- **Duration:** ~60 мин
- **Started:** 2026-05-14T12:09:00Z
- **Completed:** 2026-05-14T13:10:00Z
- **Tasks:** 2 (TDD x2: RED + GREEN каждый)
- **Files modified:** 23

## Accomplishments

- Backend: safety.py с 10 regex-паттернами (RU+EN), asyncio.Event pending store, scan_for_dangerous(); POST /chat/confirm 204/404/422; loop.py SEC-01 ветка; 39 новых тестов (161 total, всё зелёное)
- Frontend: ConfirmExecuteDialog модал (Radix Dialog + reason + JSON args + 2 кнопки); useChatStream pendingConfirm state + resolveConfirm(); next.config.ts CSP production-only; 12 новых vitest тестов (88 total)
- Config: CORS fail-secure (пустой дефолт), Settings.environment Literal; ruff clean, pnpm lint clean, type-check clean

## Task Commits

TDD workflow — RED коммит затем GREEN:

1. **Task 1 RED: Backend safety + confirm тесты** — `6695b1d` (test)
2. **Task 1 GREEN: Backend security hardening** — `a9b9b32` (feat)
3. **Task 2 RED: Frontend confirm dialog тесты** — `6b6eb24` (test)
4. **Task 2 GREEN: Frontend CSP + ConfirmExecuteDialog** — `2efd975` (feat)
5. **Cleanup: Message.tsx props + unused imports** — `69c97c5` (fix)
6. **Ruff E501 fix** — `4e16c83` (fix)

## Files Created/Modified

**Backend — создано:**
- `backend/app/orchestrator/safety.py` — DANGEROUS_KEYWORDS, scan_for_dangerous, asyncio.Event pending store
- `backend/tests/test_orchestrator_safety.py` — 13 unit тестов regex + pending store
- `backend/tests/test_orchestrator_loop_confirm.py` — 4 интеграционных теста confirm branch в loop
- `backend/tests/test_chat_confirm_route.py` — 3 теста POST /chat/confirm
- `backend/tests/test_config_strict.py` — 2 теста CORS fail-secure

**Backend — изменено:**
- `backend/app/orchestrator/events.py` — ConfirmRequiredEvent (strict=True)
- `backend/app/orchestrator/loop.py` — SEC-01 confirm ветка перед _call_tool_with_retry
- `backend/app/routes/chat.py` — POST /chat/confirm endpoint
- `backend/app/models.py` — strict=True на всех Request-моделях + ConfirmRequest
- `backend/app/config.py` — cors_origins fail-secure + Settings.environment
- `backend/app/main.py` — CORS warning для пустого prod origins

**Frontend — создано:**
- `frontend/components/chat/ConfirmExecuteDialog.tsx` — модальный диалог подтверждения
- `frontend/components/ui/dialog.tsx` — Radix Dialog обёртка
- `frontend/components/chat/__tests__/ConfirmExecuteDialog.test.tsx` — 4 теста
- `frontend/__tests__/next-config.test.ts` — 5 тестов CSP logic

**Frontend — изменено:**
- `frontend/next.config.ts` — CSP headers production-only
- `frontend/lib/types.ts` — ConfirmRequiredPayload + confirm_required в SSEEvent
- `frontend/lib/api.ts` — postChatConfirm()
- `frontend/components/chat/useChatStream.ts` — pendingConfirm state + resolveConfirm
- `frontend/app/page.tsx` — ConfirmExecuteDialog интеграция
- `frontend/app/sessions/[id]/page.tsx` — ConfirmExecuteDialog интеграция
- `frontend/components/chat/Message.tsx` — streamingStage/currentToolName props (cleanup от 03-01)

## Decisions Made

- asyncio.Event в module-level dict работает на single-worker; production multi-worker требует Redis — задокументировано как известное ограничение
- CORS fail-secure дефолт: никаких origins без явной конфигурации в prod
- CSP только production — dev HMR с HMR websocket/eval не совместим со строгим CSP
- Pydantic strict только на Request-моделях, Response без strict (скорость сериализации)
- Confirm dialog не закрывает SSE-стрим — ждёт backend error event (архитектурное решение: один источник правды)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Message.tsx не передавал streamingStage/currentToolName в AssistantMessage**
- **Найдено в:** Task 2 (frontend cleanup после 03-01)
- **Проблема:** Message.tsx принимал только `message` prop, не передавал streaming индикаторы в AssistantMessage — UI работал но без streaming stage в session route
- **Fix:** Добавлены props `streamingStage` + `currentToolName` в Message, пробрасываются в AssistantMessage
- **Файлы:** `frontend/components/chat/Message.tsx`
- **Коммит:** `69c97c5`

**2. [Rule 1 - Bug] Ruff E501 в test_orchestrator_loop_errors.py**
- **Найдено в:** финальная проверка ruff check
- **Проблема:** строка 336 в тесте — строковый литерал длиной 154 символов (>120 лимит)
- **Fix:** разбит длинный литерал на конкатенацию
- **Файлы:** `backend/tests/test_orchestrator_loop_errors.py`
- **Коммит:** `4e16c83`

**3. [Rule 1 - Bug] Unused imports в test файлах**
- **Найдено в:** ruff check после Task 1
- **Проблема:** `pytest`, `format_sse`, `MCPDisconnectedError` unused imports в 2 тестовых файлах
- **Fix:** удалены
- **Файлы:** `backend/tests/test_orchestrator_events_new.py`, `backend/tests/test_orchestrator_loop_errors.py`
- **Коммит:** `69c97c5`

---

**Итого отклонений:** 3 auto-fixed (Rule 1 — bug/cleanup)
**Влияние:** все исправления необходимы для корректности и чистоты ruff. Scope creep нет.

## Issues Encountered

- asyncio.TimeoutError vs TimeoutError в safety.py: Python 3.11+ возвращает `TimeoutError` (alias для `asyncio.TimeoutError`); в `asyncio.wait_for` используется встроенный `TimeoutError` — тест проходит на Python 3.11
- DANGEROUS_KEYWORDS тест word-boundary: `\bЗаписать\(` с буквальной скобкой требует IGNORECASE и не word-boundary проблем в кириллице — работает через re.search по JSON-строке

## Threat Surface Scan

Все угрозы из `<threat_model>` покрыты:
- T-03-06: scan_for_dangerous + confirm dialog реализованы
- T-03-07: UUID tool_call_id + auto-pop после resolve/timeout — реализовано
- T-03-08: CONFIRMATION_TIMEOUT_S=120 + finally pop — реализовано
- T-03-09: CORS fail-secure default + env override — реализовано
- T-03-10: Pydantic strict=True + extra=forbid — реализовано
- T-03-11: /chat не логирует X-LLM-API-Key — тест caplog подтвердил
- T-03-12: CSP script-src 'self' 'unsafe-inline' production-only — реализовано
- T-03-13: ACCEPT (unsafe-inline style — Tailwind требует)
- T-03-14: 120s timeout с конфигурацией через env — реализовано

Новых threat surface не обнаружено.

## Next Phase Readiness

- SEC-01..04 закрыты — готово для Plan 03-03 (Tests + CI)
- 161 backend pytest + 88 frontend vitest — все зелёные
- ruff clean, pnpm lint clean, tsc clean
- Известное ограничение: asyncio.Event pending store — single-worker only; multi-worker продакшн требует Redis (documented)
- Plan 03-03 будет расширять coverage + добавлять E2E Playwright + GitHub Actions CI

---
*Phase: 03-production-ready*
*Completed: 2026-05-14*
