---
phase: 05-ux-polish
plan: 04
subsystem: frontend
tags: [react, nextjs, backend-source-of-truth, storage-migration, sessionStorage, api-keys, vitest]

requires:
  - phase: 05-01
    provides: "fetchLLMConfig/LLMConfigResponse types + /llm-config backend endpoint"
  - phase: 05-02
    provides: "getLLMApiKey/setLLMApiKey (api-keys.ts) from Settings UI"
  - phase: 05-03
    provides: "OnboardingDialog + onboarding-flag.ts + page.tsx integration"

provides:
  - "fetchChat принимает llm:{endpoint,model} параметр, api_key из sessionStorage"
  - "page.tsx hasConfig = fetchConnections + fetchLLMConfig (backend source-of-truth)"
  - "migrateLegacyApiKey(): one-time localStorage→sessionStorage migration (T-05-13)"
  - "storage.ts: @deprecated на 4 функциях (getMCPConnections/setMCPConnections/getLLMConfig/setLLMConfig)"
  - "useChatStream: fetchLLMConfig перед каждым send, передаёт endpoint+model в fetchChat"
  - "ModelBadge: async fetchLLMConfig (null = не рендерить)"
  - "sessions/[id]/page.tsx: fetchConnections в handleBannerShow + handleRetry"

affects:
  - "05-05: E2E Playwright — smoke на migration flow (localStorage legacy → sessionStorage)"

tech-stack:
  added: []
  patterns:
    - "backend source-of-truth pattern: fetchConnections+fetchLLMConfig в useEffect Promise.all"
    - "migrateLegacyApiKey: one-time migration helper at app startup"
    - "fetchChat с explicit llm parameter — caller отвечает за передачу config"
    - "fetchLLMConfig per-send в useChatStream — один доп. round-trip (T-05-14 accept)"

key-files:
  created: []
  modified:
    - "frontend/lib/storage.ts"
    - "frontend/lib/api.ts"
    - "frontend/lib/api-keys.ts"
    - "frontend/app/page.tsx"
    - "frontend/app/sessions/[id]/page.tsx"
    - "frontend/components/chat/Input.tsx"
    - "frontend/components/chat/AssistantMessage.tsx"
    - "frontend/components/shell/ModelBadge.tsx"
    - "frontend/components/shell/ChannelSelector.tsx"
    - "frontend/components/chat/useChatStream.ts"
    - "frontend/components/chat/__tests__/useChatStream.test.tsx"

key-decisions:
  - "fetchChat принимает llm как параметр (не внутри функции fetchLLMConfig) — избегает circular import"
  - "fetchLLMConfig вызывается в каждом useChatStream.send() — T-05-14 accept, ~5ms, не влияет на UX"
  - "AssistantMessage: getMCPConnections() оставлен как legacy cache (T-05-15 accept — read-only curl UI)"
  - "Input.tsx: getLLMApiKey() sessionStorage check вместо prop hasLLM — минимум изменений архитектуры"
  - "ModelBadge: null → не рендерить (пустой элемент лучше чем «—» из стаффа)"
  - "migrateLegacyApiKey: проверяет api_key.length > 0 перед переносом — защита от edge case R3"

requirements-completed: [UX-04]

duration: ~10min
completed: 2026-05-15
---

# Phase 05 Plan 04: Source-of-Truth Migration Summary

**Backend = единственный источник истины: fetchConnections+fetchLLMConfig заменяют localStorage getMCPConnections/getLLMConfig в 7 компонентах; fetchChat принимает llm параметр + sessionStorage api_key; one-time migration helper для legacy пользователей**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-05-15T16:04:00Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

### Task 1 — storage.ts @deprecated + api.ts fetchChat новая сигнатура

- `storage.ts`: добавлены JSDoc `@deprecated` маркеры на 4 функции: `getLLMConfig`, `setLLMConfig`, `getMCPConnections`, `setMCPConnections`. Тела сохранены для backward compat.
- `api.ts fetchChat`: изменена сигнатура — добавлен параметр `llm: { endpoint: string; model: string }`. Удалён `getLLMConfig` import из storage, добавлен `getLLMApiKey` из api-keys.
- `api-keys.ts`: добавлена `migrateLegacyApiKey()` — one-time migration T-05-13: если sessionStorage пуст + localStorage имеет `analyst.llm` с api_key — переносит ключ в sessionStorage и очищает localStorage.

### Task 2 — Переключение компонентов на backend

- **`app/page.tsx`**: `useEffect` полностью переписан на `Promise.all([fetchConnections(), fetchLLMConfig()])`. `hasConfig` = `conns.length > 0 && llm !== null` (строго AND, не OR). `migrateLegacyApiKey()` вызывается при старте. `refreshAfterOnboarding()` — async с fetchConnections+fetchLLMConfig.
- **`app/sessions/[id]/page.tsx`**: `getMCPConnections` → `fetchConnections` в `handleBannerShow` (async + catch) и `handleRetry`.
- **`useChatStream.ts`**: перед каждым `fetchChat` вызывает `fetchLLMConfig()` — получает endpoint+model для нового параметра; если config null — возвращает inline error.
- **`Input.tsx`**: `getLLMConfig()` → `getLLMApiKey()` (sessionStorage check для disabled-state alert).
- **`ModelBadge.tsx`**: переписан на `useEffect → fetchLLMConfig().then(...)`, `null` начальный state = не рендерить бейдж.
- **`AssistantMessage.tsx`**: добавлен legacy cache comment (T-05-15 accept).
- **`ChannelSelector.tsx`**: добавлен `@deprecated` comment на localStorage fallback в catch.

### Task 3 — Тесты

- `useChatStream.test.tsx`: mock `getLLMConfig` удалён, добавлен mock `fetchLLMConfig: vi.fn().mockResolvedValue({id:"default", endpoint, model, temperature})`. Storage mock оставляет только `getAnonEnabled`.
- `ChannelSelector.test.tsx`: без изменений (legacy fallback сохранён, тесты продолжают работать).

## Task Commits

1. **Task 1** — `412c18c` (feat): storage.ts @deprecated + fetchChat new signature
2. **Task 2** — `5566052` (feat): backend source-of-truth migration — 7 файлов
3. **Task 3** — `7342835` (feat): useChatStream.test.tsx mock адаптация

## Public API Changes

### fetchChat (lib/api.ts) — breaking change

**Before:**
```typescript
export async function* fetchChat(
  req: ChatRequest,
  signal?: AbortSignal,
  extraHeaders?: Record<string, string>,
): AsyncIterable<SSEEvent>
```

**After:**
```typescript
export async function* fetchChat(
  req: ChatRequest,
  llm: { endpoint: string; model: string },
  signal?: AbortSignal,
  extraHeaders?: Record<string, string>,
): AsyncIterable<SSEEvent>
```

Единственный call-site — `useChatStream.ts` (обновлён в Task 2). `fetchChat` теперь читает `getLLMApiKey()` из sessionStorage вместо `getLLMConfig()` из localStorage.

### migrateLegacyApiKey (lib/api-keys.ts) — new export

One-time migration helper. Вызывается в `app/page.tsx` useEffect при монтировании.

## Regression Results

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| Frontend (pnpm test --run) | 219 | 219 | 0 |
| Backend (pytest -x) | 315 | 315 | 0 |

## Legacy Migration Helper

`migrateLegacyApiKey()` (api-keys.ts):
- Проверяет: `sessionStorage.analyst.llm_api_key` пуст?
- Читает: `localStorage.analyst.llm` (старый JSON-объект)
- Если `parsed.api_key` — строка длиннее 0: переносит в sessionStorage, очищает localStorage
- Защита R3: `typeof parsed.api_key === "string" && parsed.api_key.length > 0`

## Known Follow-ups

### Plan 5.5 (E2E + release)

- Playwright smoke на migration flow: установить `localStorage.analyst.llm = {..., api_key: "sk-legacy"}` → refresh → проверить sessionStorage получил ключ, localStorage очищен
- E2E для full first-run onboarding + hasConfig check из backend
- Performance: cache fetchLLMConfig в useChatStream (один fetch на send — T-05-14 accept)

## Deviations from Plan

None — план выполнен точно.

Единственное небольшое отступление от буквы плана: в `handleBannerShow` (sessions/[id]/page.tsx) plan предлагал "принимать connections через props ОТ родителя ИЛИ legacy fallback". Выбран третий вариант — async `fetchConnections()` в callback с catch. Это чище чем props drilling и не хуже legacy fallback. Соответствует цели Plan 5.4.

## Known Stubs

Нет. Все 7 целевых файлов содержат реальную логику. `AssistantMessage` использует legacy localStorage cache — это задокументировано как T-05-15 accept, не заглушка.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: mitigated T-05-13 | frontend/lib/api-keys.ts | migrateLegacyApiKey() закрывает угрозу старого api_key в localStorage |

T-05-14 (fetchLLMConfig per-send) — accept. T-05-15 (stale MCP cache в AssistantMessage) — accept.

## Self-Check: PASSED

- `frontend/lib/storage.ts` содержит `@deprecated`: FOUND
- `frontend/lib/api.ts fetchChat` содержит `getLLMApiKey()`: FOUND
- `frontend/lib/api-keys.ts` содержит `migrateLegacyApiKey`: FOUND
- `frontend/app/page.tsx` содержит `fetchLLMConfig`: FOUND
- `frontend/app/sessions/[id]/page.tsx` содержит `fetchConnections`: FOUND
- 219 frontend tests pass: VERIFIED
- 315 backend tests pass: VERIFIED
- Commit 412c18c: FOUND
- Commit 5566052: FOUND
- Commit 7342835: FOUND

---
*Phase: 05-ux-polish*
*Completed: 2026-05-15*
