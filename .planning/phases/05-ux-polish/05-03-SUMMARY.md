---
phase: 05-ux-polish
plan: 03
subsystem: ui
tags: [react, shadcn, dialog, onboarding, localStorage, wizard, vitest]

requires:
  - phase: 05-01
    provides: "fetchLLMConfig/LLMConfigResponse types"
  - phase: 05-02
    provides: "MCPConnectionForm + LLMConfigForm (reusable props-based forms)"

provides:
  - "OnboardingDialog: 3-step modal wizard (MCP → LLM → Done)"
  - "StepIndicator: 1/3 → 2/3 → 3/3 visual step tracker"
  - "onboarding-flag.ts: getOnboardingCompleted/setOnboardingCompleted (localStorage SSR-safe)"
  - "app/page.tsx: first-run detection + legacy guard + OnboardingDialog mount"

affects:
  - "05-04: page.tsx hasConfig refactor (getMCPConnections/getLLMConfig removal)"
  - "05-05: Playwright E2E onboarding.spec.ts"

tech-stack:
  added:
    - "@radix-ui/react-dialog (via dialog.tsx shadcn component)"
  patterns:
    - "safeLocalStorage SSR-safe pattern (same as storage.ts)"
    - "ping gate: onSaved → pingConnection → setPingPassed (async handler in dialog)"
    - "open useEffect reset: state сбрасывается при каждом open=true"
    - "legacy guard: Promise.all([fetchConnections, fetchLLMConfig]) + auto-set flag"

key-files:
  created:
    - "frontend/components/ui/dialog.tsx"
    - "frontend/lib/onboarding-flag.ts"
    - "frontend/components/onboarding/StepIndicator.tsx"
    - "frontend/components/onboarding/OnboardingDialog.tsx"
    - "frontend/components/onboarding/__tests__/OnboardingDialog.test.tsx"
  modified:
    - "frontend/app/page.tsx"

key-decisions:
  - "LLM gate = onSaved (не onTested) — упрощает API формы, документируется как контракт Save-after-Test"
  - "Legacy guard через backend fetchConnections+fetchLLMConfig, не через localStorage — актуальные данные"
  - "refreshAfterOnboarding() без window.location.reload — чистый refetch getMCPConnections/getLLMConfig из storage"
  - "Dialog open=true с onPointerDownOutside preventDefault — блокирует случайное закрытие"

requirements-completed: [UX-01]

duration: ~3min (Tasks 1+2 закоммичены предыдущим агентом; Task 3 создан в этом запуске)
completed: 2026-05-15
---

# Phase 05 Plan 03: First-run Onboarding Wizard Summary

**3-step modal onboarding wizard (MCP → LLM → Done) with localStorage completion flag, ping/save gates for «Далее» buttons, legacy guard for existing users, and 9 unit tests — 219 total pass**

## Performance

- **Duration:** ~3 min (Tasks 1+2 были готовы; Task 3 выполнен в этом запуске)
- **Completed:** 2026-05-15T15:50:40Z
- **Tasks:** 3
- **Files modified:** 6 (5 created, 1 modified)

## Accomplishments

- OnboardingDialog: 3-шаговый modal wizard с gate-логикой «Далее» (ping gate на шаге 1, save gate на шаге 2)
- StepIndicator: визуальный трекер 1/3 → 2/3 → 3/3 с CSS vars проекта
- onboarding-flag.ts: SSR-safe localStorage helpers, KEY = `analyst.onboarding_completed`
- app/page.tsx: showOnboarding state, legacy guard через Promise.all backend-check, refreshAfterOnboarding()
- 9 unit-тестов (OnboardingDialog.test.tsx) — все сценарии wizard: рендер, ping success/fail, переходы, back, LLM gate, complete, skip
- Полная регрессия: 219 тестов pass (было 210)

## Task Commits

1. **Task 1: onboarding-flag + StepIndicator + dialog.tsx** — `9b4aa0b` (feat)
2. **Task 2: OnboardingDialog + page.tsx integration** — `6520e03` (feat)
3. **Task 3: 9 unit-тестов OnboardingDialog** — `a03f726` (feat)

## Components Created

### OnboardingDialog (194 строки)

Props: `{ open: boolean; onComplete: (firstChannelId: string | null) => void; onSkip: () => void }`

State:
- `step: 1 | 2 | 3` — текущий шаг
- `createdConnection: MCPConnection | null` — сохранённый коннектор
- `pingPassed: boolean` — gate для «Далее» шага 1
- `llmTestPassed: boolean` — gate для «Далее» шага 2
- `pingLoading: boolean` — индикатор проверки соединения

Ключевые обработчики:
- `handleMCPSaved(conn)` → `pingConnection(conn.id)` → `setPingPassed(true)` / `publishToast({type:"error"})`
- `handleLLMSaved()` → `setLlmTestPassed(true)`
- `handleComplete()` → `setOnboardingCompleted(true)` → `onComplete(createdConnection?.id ?? null)`
- `handleSkip()` → `setOnboardingCompleted(true)` → `onSkip()`

### StepIndicator (46 строк)

Props: `{ current: 1 | 2 | 3; total: 3 }`

Рендер: три кружка + соединительные линии + «Шаг N из 3». Стили через `var(--accent)`, `var(--border)`, `var(--fg-muted)`.

## lib/onboarding-flag.ts API

```typescript
getOnboardingCompleted(): boolean   // localStorage.getItem("analyst.onboarding_completed") === "true"
setOnboardingCompleted(done: boolean): void  // set / remove key
```

SSR-safe: возвращает false/no-op в Node context.

## Tests Added

**9 тестов** в `frontend/components/onboarding/__tests__/OnboardingDialog.test.tsx`:

| # | Тест | Сценарий |
|---|------|---------|
| 1 | Initial render | Шаг 1 виден, «Далее» disabled |
| 2 | Ping success | onSaved + успешный pingConnection → «Далее» active, toast info |
| 3 | Ping failure | onSaved + rejected ping → «Далее» disabled, toast error |
| 4 | Step 1→2 | Успешный ping + click «Далее» → шаг 2 LLM-форма |
| 5 | Step 2 Back | click «← Назад» на шаге 2 → возврат шаг 1 |
| 6 | LLM save gate | «Далее» на шаге 2 disabled до onSaved, active после |
| 7 | Step 2→3 | LLM save + «Далее» → шаг 3 «Готово!» |
| 8 | Complete | Шаг 3 + «Начать работу» → setOnboardingCompleted(true), onComplete(conn-id) |
| 9 | Skip | «Пропустить» → setOnboardingCompleted(true), onSkip() |

## app/page.tsx Changes

Добавлено к существующей странице:
- `showOnboarding: boolean | null` state (null = не определено)
- useEffect: `getOnboardingCompleted()` → legacy guard (`fetchConnections + fetchLLMConfig`) → `setShowOnboarding(true/false)`
- `refreshAfterOnboarding()` helper: перечитывает getMCPConnections/getLLMConfig из storage
- Ранний return: `if (showOnboarding) → <OnboardingDialog ... /> + <BackendIndicator />`
- Импорты: OnboardingDialog, getOnboardingCompleted, setOnboardingCompleted

## Manual Smoke Results

*Не выполнялся в этом запуске — автоматические тесты покрывают logic; E2E smoke на Plan 5.5.*

## Known Follow-ups

### Plan 5.4 (page.tsx hasConfig refactor)
- Удалить `getMCPConnections()/getLLMConfig()` из app/page.tsx — заменить на backend-driven `fetchConnections()/fetchLLMConfig()`
- Убрать `refreshAfterOnboarding()` localStorage-based → `fetchConnections()` refetch
- Полная замена `hasConfig` localStorage logic на backend-driven check

### Plan 5.5 (Playwright E2E)
- `onboarding.spec.ts`: свежая БД + clear localStorage → wizard пройти полностью → refresh → модалка НЕ открывается
- Legacy guard scenario: curl create connection+llm → clear only onboarding flag → refresh → нет модалки

## Deviations from Plan

### Auto-fixed Issues

Нет — Tasks 1+2 были выполнены предыдущим агентом в соответствии с планом. Task 3 (тесты) выполнен в этом запуске без отклонений.

## Known Stubs

Нет — OnboardingDialog.handleMCPSaved вызывает реальный `pingConnection()`. handleLLMSaved вызывается после реального `LLMConfigForm.onSaved` (который вызывает `saveLLMConfig`). page.tsx вызывает реальные `fetchConnections/fetchLLMConfig` для legacy guard.

## Threat Flags

Нет новых поверхностей атаки. T-05-10 / T-05-11 / T-05-12 из плана — disposition accept/mitigate как задокументировано.

## Self-Check: PASSED

- `frontend/components/ui/dialog.tsx`: FOUND
- `frontend/lib/onboarding-flag.ts`: FOUND
- `frontend/components/onboarding/StepIndicator.tsx`: FOUND
- `frontend/components/onboarding/OnboardingDialog.tsx`: FOUND
- `frontend/components/onboarding/__tests__/OnboardingDialog.test.tsx`: FOUND
- `frontend/app/page.tsx` contains OnboardingDialog: FOUND
- Commit 9b4aa0b: FOUND
- Commit 6520e03: FOUND
- Commit a03f726: FOUND
- 219 tests pass: VERIFIED

---
*Phase: 05-ux-polish*
*Completed: 2026-05-15*
