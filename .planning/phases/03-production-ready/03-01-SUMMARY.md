---
phase: 03-production-ready
plan: 01
subsystem: ui
tags: [sse, error-handling, toast, react, fastapi, streaming, mcp]

# Dependency graph
requires:
  - phase: 02-mvp-chat
    provides: "SSE wire format, useChatStream baseline, pingConnection API, MCPClient"
provides:
  - "ErrorEvent.retry_after_s + Literal ErrorCode (12 значений)"
  - "LLMRateLimitError класс с retry_after_s в clients/llm.py"
  - "MCPDisconnectedError класс в clients/mcp.py"
  - "Маппинг 429/401/403/5xx LLM → 4 кода + mcp_disconnected в loop.py"
  - "Toaster (~100 строк) без sonner — countdown + FIFO cap"
  - "publishToast/subscribeToast event bus в lib/toast.ts"
  - "ConnectionStatusBanner — красный fixed баннер + кнопка Повторить"
  - "StreamingIndicator — стадии Анализирую/Вызываю/Формирую"
  - "useChatStream error routing: MCP → banner, LLM → toast, прочие → inline"
  - "AssistantMessage inline error с красным border + иконкой ⚠"
  - "SessionPage handleRetry с pingConnection + bannerRetrying lock"
affects: [03-02, 03-03, plan-3-2, plan-3-3]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Window CustomEvent bus для toast (без глобального state)"
    - "Discriminated SSE error routing по code категориям (MCP vs LLM vs прочие)"
    - "recursive setTimeout вместо setInterval для countdown (fake-timers совместимость)"
    - "_safe_error_message() truncate 200 chars + splitlines()[0] — T-03-01 mitigated"
    - "LLMRateLimitError subclass httpx.HTTPStatusError с атрибутом retry_after_s"

key-files:
  created:
    - "frontend/lib/toast.ts"
    - "frontend/components/ui/toast.tsx"
    - "frontend/components/chat/ConnectionStatusBanner.tsx"
    - "frontend/components/chat/StreamingIndicator.tsx"
    - "frontend/components/chat/__tests__/ConnectionStatusBanner.test.tsx"
    - "frontend/components/chat/__tests__/StreamingIndicator.test.tsx"
    - "frontend/components/ui/__tests__/toast.test.tsx"
  modified:
    - "backend/app/orchestrator/events.py"
    - "backend/app/orchestrator/loop.py"
    - "backend/app/clients/llm.py"
    - "backend/app/clients/mcp.py"
    - "backend/tests/test_orchestrator_loop.py"
    - "backend/tests/test_chat_route.py"
    - "frontend/lib/types.ts"
    - "frontend/components/chat/useChatStream.ts"
    - "frontend/components/chat/AssistantMessage.tsx"
    - "frontend/components/chat/Thread.tsx"
    - "frontend/components/chat/Input.tsx"
    - "frontend/app/sessions/[id]/page.tsx"
    - "frontend/app/layout.tsx"
    - "frontend/components/chat/__tests__/useChatStream.test.tsx"

key-decisions:
  - "recursive setTimeout вместо setInterval в countdown — setInterval создаёт бесконечный цикл с vi.runAllTimers() в fake-timers тестах"
  - "mcp_connect_error оставлен в ErrorCode Literal и MCP_ERROR_CODES для обратной совместимости"
  - "Toaster вставлен напрямую в layout.tsx body без отдельного toast-provider.tsx (упрощение)"
  - "ConnectionStatusBanner использует variant=secondary вместо outline — outline не существует в кастомном button.tsx"
  - "clamp(retry_after_s, 0, 300) в llm.py — T-03-04 защита от злоумышленного Retry-After"

patterns-established:
  - "ErrorCode Literal с 12 значениями как единый контракт между backend и frontend"
  - "Error routing: MCP codes → ConnectionStatusBanner; LLM codes → Toaster; прочие → inline"

requirements-completed: [STATE-02, STATE-03]

# Metrics
duration: 35min
completed: 2026-05-14
---

# Phase 3 Plan 01: Error UX — MCP Banner + LLM Toast + Streaming Stages Summary

**SSE error contract расширен retry_after_s + 12 кодами; frontend получил Toaster без sonner, ConnectionStatusBanner с retry, StreamingIndicator стадий — STATE-02 и STATE-03 закрыты**

## Performance

- **Duration:** 35 min
- **Started:** 2026-05-14T15:00:00Z
- **Completed:** 2026-05-14T15:35:00Z
- **Tasks:** 2 (Task 1 backend + Task 2 frontend)
- **Files modified:** 21

## Accomplishments

- Backend: ErrorEvent.retry_after_s, Literal ErrorCode 12 значений, LLMRateLimitError, MCPDisconnectedError, маппинг 429/401/403/5xx/сетевые ошибки
- Frontend: Toaster (~100 строк без sonner), publishToast event bus, ConnectionStatusBanner, StreamingIndicator, error routing в useChatStream
- 136 backend тестов зелёные (coverage 88%), 76 frontend тестов зелёные, type-check чистый, lint чистый, build success

## Task Commits

1. **Task 1: Backend error mapping** - `f956ab5` (feat) — уже существовал до выполнения
2. **Task 2: Frontend components** - `534ecda` (feat)

**Plan metadata:** создаётся следующим коммитом (docs)

## Files Created/Modified

- `frontend/lib/toast.ts` — publishToast/subscribeToast event bus (~30 строк)
- `frontend/components/ui/toast.tsx` — Toaster с countdown, FIFO cap 5, без sonner
- `frontend/components/chat/ConnectionStatusBanner.tsx` — красный fixed баннер + retry кнопка
- `frontend/components/chat/StreamingIndicator.tsx` — стадии Анализирую/Вызываю/Формирую
- `frontend/components/chat/useChatStream.ts` — error routing + streamingStage + currentToolName
- `frontend/components/chat/AssistantMessage.tsx` — inline error border-red-700
- `frontend/components/chat/Thread.tsx` — streamingStage props
- `frontend/components/chat/Input.tsx` — disabledReason banner подсказка
- `frontend/app/sessions/[id]/page.tsx` — banner state + handleRetry + pingConnection
- `frontend/app/layout.tsx` — Toaster один раз в body
- `backend/app/orchestrator/events.py` — retry_after_s, Literal ErrorCode
- `backend/app/orchestrator/loop.py` — _safe_error_message, маппинг ошибок LLM/MCP
- `backend/app/clients/llm.py` — LLMRateLimitError + _parse_retry_after с clamp 0..300
- `backend/app/clients/mcp.py` — MCPDisconnectedError

## Decisions Made

- recursive setTimeout для countdown вместо setInterval — избегает бесконечный цикл с `vi.runAllTimers()` в fake-timers тестах
- mcp_connect_error оставлен в ErrorCode и MCP_ERROR_CODES — обратная совместимость, оба кода маршрутизируются в banner
- Toaster напрямую в layout.tsx без отдельного provider — меньше файлов, проще

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Бесконечный цикл countdown в toast с fake-timers**
- **Found during:** Task 2 (frontend тесты)
- **Issue:** `setInterval` в ToastItem с `vi.runAllTimers()` в afterEach создавал infinite loop — vitest aborting after 10000 timers
- **Fix:** Заменено на рекурсивный `setTimeout` — каждый тик отдельный timer, `vi.runAllTimers()` завершается конечно
- **Files modified:** `frontend/components/ui/toast.tsx`
- **Verification:** `pnpm test --run` — 76 passed
- **Committed in:** `534ecda`

**2. [Rule 1 - Bug] TypeScript ошибка variant="outline" в ConnectionStatusBanner**
- **Found during:** Task 2 (type-check)
- **Issue:** `variant="outline"` не существует в кастомном `button.tsx` — только default/secondary/ghost/link/destructive
- **Fix:** Заменено на `variant="secondary"` с кастомными className для красных цветов
- **Files modified:** `frontend/components/chat/ConnectionStatusBanner.tsx`
- **Verification:** `pnpm type-check` — 0 errors
- **Committed in:** `534ecda`

---

**Total deviations:** 2 auto-fixed (2x Rule 1 - Bug)
**Impact on plan:** Оба фикса необходимы для прохождения тестов и type-check. Scope не расширен.

## Issues Encountered

- Backend Task 1 был полностью реализован до начала выполнения (commit f956ab5 существовал) — план выполнен в два этапа, второй подхвачен исполнителем без дублирования

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- STATE-02 и STATE-03 закрыты полностью
- ErrorCode Literal с 12 значениями готов для Plan 3.2 (user_declined, dangerous_keyword_blocked уже присутствуют)
- Toaster, ConnectionStatusBanner, StreamingIndicator доступны для переиспользования в Plan 3.2+
- Streaming stage индикатор работает из коробки через useChatStream.streamingStage

## Known Stubs

None — все компоненты получают реальные данные из SSE-потока.

## Threat Flags

Нет новых поверхностей сверх threat_model плана. T-03-01 (traceback), T-03-02 (API key echo), T-03-04 (retry_after clamp) — все митигированы и проверены тестами.

## Self-Check: PASSED

- `f956ab5` существует в git log: confirmed
- `534ecda` существует в git log: confirmed
- `frontend/lib/toast.ts` существует: confirmed
- `frontend/components/ui/toast.tsx` существует: confirmed
- `frontend/components/chat/ConnectionStatusBanner.tsx` существует: confirmed
- `frontend/components/chat/StreamingIndicator.tsx` существует: confirmed
- backend 136 tests passed, frontend 76 tests passed

---
*Phase: 03-production-ready*
*Completed: 2026-05-14*
