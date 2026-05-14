---
phase: 01-foundation
plan: 02
subsystem: frontend
tags: [nextjs15, react19, tailwind4, shadcn-ui, ibm-plex, dark-theme, sse, typescript-strict]
dependency_graph:
  requires: [plan-01-backend]
  provides: [frontend-skeleton, appshell, sse-parser, api-client, storage-layer]
  affects: [phase-2-chat, phase-2-settings-crud, phase-2-sessions]
tech_stack:
  added:
    - Next.js 15.5.18 (App Router)
    - React 19.2.6
    - Tailwind CSS 4.3.0 + @tailwindcss/postcss
    - shadcn/ui (button, input, scroll-area, select над Radix UI)
    - IBM Plex Sans + IBM Plex Mono через next/font/google
    - lucide-react 0.460.0
    - class-variance-authority + clsx + tailwind-merge
  patterns:
    - CSS variables для тёмной палитры (--bg, --fg, --accent), без светлой темы
    - SSR-safe localStorage через typeof window guard
    - Discriminated union SSEEvent для типобезопасного парсинга
    - TextDecoder с stream:true для incremental UTF-8 декодирования
    - LLM api_key только в X-LLM-API-Key header (никогда в body)
key_files:
  created:
    - frontend/package.json
    - frontend/pnpm-workspace.yaml
    - frontend/tsconfig.json
    - frontend/next.config.ts
    - frontend/postcss.config.mjs
    - frontend/tailwind.config.ts
    - frontend/.env.local.example
    - frontend/.eslintrc.json
    - frontend/components.json
    - frontend/app/layout.tsx
    - frontend/app/page.tsx
    - frontend/app/globals.css
    - frontend/app/settings/page.tsx
    - frontend/components/shell/AppShell.tsx
    - frontend/components/shell/Header.tsx
    - frontend/components/shell/Sidebar.tsx
    - frontend/components/shell/ChannelSelector.tsx
    - frontend/components/shell/ModelBadge.tsx
    - frontend/components/chat/Thread.tsx
    - frontend/components/chat/Message.tsx
    - frontend/components/chat/Input.tsx
    - frontend/components/ui/button.tsx
    - frontend/components/ui/input.tsx
    - frontend/components/ui/scroll-area.tsx
    - frontend/components/ui/select.tsx
    - frontend/lib/api.ts
    - frontend/lib/sse.ts
    - frontend/lib/storage.ts
    - frontend/lib/types.ts
    - frontend/lib/utils.ts
  modified: []
decisions:
  - "TextDecoderStream несовместим с ReadableStream<Uint8Array> в TypeScript strict mode — использован TextDecoder с stream:true напрямую"
  - "outputFileTracingRoot добавлен в next.config.ts — устраняет warning о множественных lockfile в монорепо"
  - "InputProps как type alias вместо interface — избегает @typescript-eslint/no-empty-object-type"
  - "page.tsx использует empty state (нет MCP+LLM) и full AppShell (есть конфиг) — проверка через useEffect + localStorage"
  - "BackendIndicator рендерится как фиксированный badge в углу — не ломает layout при недоступном backend"
metrics:
  duration: "~10 мин"
  completed: "2026-05-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 30
  files_modified: 0
---

# Phase 01 Plan 02: Frontend Foundation Summary

Next.js 15 + Tailwind 4 + shadcn/ui skeleton с тёмной темой IBM Plex, AppShell (header/sidebar/main/input), типизированным SSE-парсером и localStorage обёртками для LLM/MCP конфига.

## Что сделано

### Task 1 — Next.js + Tailwind + shadcn/ui init (коммит `ea84cdb`)

- `package.json`: next@15, react@19, tailwindcss@4, radix-ui компоненты, lucide-react
- `tsconfig.json`: strict + noUncheckedIndexedAccess + paths @/*
- `next.config.ts`: ignoreErrors=false, outputFileTracingRoot для монорепо
- `postcss.config.mjs`: @tailwindcss/postcss (Tailwind 4, не v3)
- `tailwind.config.ts`: darkMode=class, IBM Plex font vars, CSS variable цвета
- `globals.css`: dark palette (#0a0a0a bg, #141414 elevated, #f97316 accent)
- `layout.tsx`: html lang=ru class=dark, IBM_Plex_Sans + IBM_Plex_Mono cyrillic subset
- shadcn/ui: button, input, scroll-area, select — все с dark theme через CSS variables
- `lib/utils.ts`: cn helper

### Task 2 — AppShell + UI компоненты + страницы (коммит `9943f37`)

- `AppShell.tsx`: CSS grid 260px+1fr, 56px header span col-span-2, sidebar, main, bottom
- `Header.tsx`: лого «1С Аналитик», ChannelSelector по центру, ModelBadge + Settings icon
- `Sidebar.tsx`: группы Сегодня/Вчера/Ранее с «Истории пока нет», кнопка «Новый чат»
- `ChannelSelector.tsx`: shadcn Select из getMCPConnections(), disabled placeholder если пусто
- `ModelBadge.tsx`: IBM Plex Mono pill с model·temperature из getLLMConfig()
- `Thread.tsx`: ScrollArea + Message компоненты, dummy welcome message
- `Message.tsx`: plain text рендер (T-01-11 XSS guard), user/assistant стили
- `Input.tsx`: textarea с min/max height, Ctrl+Enter submit, предупреждение без LLM config
- `page.tsx`: empty state «Начните работу» + CTA «Настроить» → /settings, или AppShell
- `settings/page.tsx`: секции LLM + MCP connections (read-only из localStorage, Phase 1)

### Task 3 — API-клиент + SSE парсер + storage (коммит `8d24851`)

- `types.ts`: ChatRequest, SSEEvent (discriminated union по event), HealthResponse, MCPPingResponse, LLMConfig, MCPConnection, ChatMessage — зеркало Pydantic моделей
- `storage.ts`: getLLMConfig/setLLMConfig, getMCPConnections/setMCPConnections, active channel — SSR-safe (typeof window guard)
- `sse.ts`: parseSSEStream ReadableStream → AsyncIterable<SSEEvent>; TextDecoder stream:true; блоки через \n\n; runtime-валидация event names
- `api.ts`: fetchHealth, fetchChat (api_key ТОЛЬКО в X-LLM-API-Key, не в body), fetchMCPPing; ноль any
- `page.tsx` дополнен BackendIndicator: smoke-вызов fetchHealth() → «Backend: ok 0.1.0» или «Backend: недоступен» в нижнем углу

## Итоги верификации

```
pnpm install  → Packages: +363, done (сеть доступна, верифицировано)
pnpm type-check (tsc --noEmit)  → чисто, ноль ошибок
pnpm lint (next lint)  → No ESLint warnings or errors
pnpm build  → ✓ Compiled, 3 маршрута: / + /_not-found + /settings
grep запрещённых: Inter, from-purple, to-cyan, glass, emoji, : any, @ts-ignore  → ноль совпадений
```

**Не верифицировано в sandbox (нет GUI):**

- `pnpm dev` → визуальная проверка AppShell в браузере; build прошёл успешно, что подтверждает корректность кода
- smoke интеграция с backend: BackendIndicator реализован, но `curl localhost:8010/health` не запускался в этой сессии
- ⌘+Enter в textarea: логика присутствует в коде (`e.metaKey || e.ctrlKey`), визуально не проверялась

## Отклонения от плана

### [Rule 1 - Bug] TextDecoderStream несовместим с TS strict mode

- **Найдено при:** Task 3, первый запуск tsc
- **Проблема:** `stream.pipeThrough(new TextDecoderStream())` — `WritableStream<BufferSource>` не assignable to `WritableStream<Uint8Array>` в TypeScript strict
- **Исправление:** `TextDecoder` с `decode(value, { stream: true })` напрямую — корректно и без type cast
- **Файл:** `frontend/lib/sse.ts`

### [Rule 1 - Bug] empty interface в input.tsx

- **Найдено при:** Task 1, pnpm lint
- **Проблема:** `interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}` — `@typescript-eslint/no-empty-object-type: error`
- **Исправление:** замена `interface` на `type` alias
- **Файл:** `frontend/components/ui/input.tsx`

### [Rule 2 - Missing] outputFileTracingRoot в next.config.ts

- **Найдено при:** Task 1, pnpm lint (warning о множественных lockfiles в монорепо)
- **Добавлено:** `outputFileTracingRoot: path.join(process.cwd(), "..")` — устраняет warning

## Known Stubs

- `Sidebar.tsx`: группы Сегодня/Вчера/Ранее — dummy, данных нет (Phase 2 Sessions)
- `Thread.tsx`: dummy welcome message — реальный chat поток в Phase 2
- `ModelBadge.tsx`: показывает данные из localStorage; пусто если не настроено (ожидаемо)
- `ChannelSelector.tsx`: список пустой пока нет MCP connections (ожидаемо)
- `settings/page.tsx`: только чтение, без CRUD (Phase 2.4 по плану)

Все стабы соответствуют scope Phase 1 — Out-of-Scope явно задокументирован в PLAN.md.

## Threat Surface Scan

Новые поверхности соответствуют threat model PLAN.md:
- localStorage: LLM api_key доступен JS на origin (T-01-09: mitigate в Phase 3)
- fetchChat: api_key только в X-LLM-API-Key header, compile-time guard через type (T-01-12: mitigated)
- Message.tsx: plain text рендер, не dangerouslySetInnerHTML (T-01-11: mitigated)

## Self-Check: PASSED
