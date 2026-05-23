# 10 · Execution Plan

Пошаговый план для Claude Code. Каждый шаг — атомарный коммит. Тесты прогоняй после каждого шага.

---

## Pre-flight

1. **Создай ветку:** `git checkout -b ui/audit-2026-05-23-handoff`
2. **Прочитай:**
   - `README.md`
   - `01-context-and-status.md` (чтобы не делать дважды)
   - `08-copy-glossary.md` (для понимания терминологии)
3. **Открой в браузере:** `reference/visual-audit-report.html` — это финальная цель.
4. **Прогон baseline-тестов:** `pnpm test && pnpm test:e2e` — чтобы знать стартовое состояние.

---

## Спринт 01 — Cleanup (1–2 дня, ~8 коммитов)

**Цель:** terminology + tokens + удаление мёртвого кода.

### Step 1.1 — Design tokens

- [ ] Внеси diff из `03-design-tokens.md` в `frontend/styles/design-tokens.css`
- [ ] Добавь `prefers-reduced-motion` блок в конец файла
- [ ] Commit: `chore(tokens): add motion + info + focus-ring + syntax tokens`

### Step 1.2 — REM-1 json-tree colors

- [ ] Diff из `02-codebase-cleanup.md` § REM-1 в `frontend/lib/json-tree.tsx`
- [ ] Прогон: открой чат с trace, разверни tool_call → проверь цвета
- [ ] Commit: `fix(json-tree): use semantic tokens instead of hardcoded Tailwind colors`

### Step 1.3 — REM-3 единая версия

- [ ] Создай `frontend/lib/app-version.ts`
- [ ] Обнови `next.config.mjs` (env переменная из package.json)
- [ ] Замени hardcoded версии в `StencilLockup.tsx`, `about/page.tsx`
- [ ] Commit: `chore(version): single source of truth via APP_VERSION`

### Step 1.4 — REM-4 terminology (текстовые замены)

- [ ] Прогон таблицы из `02-codebase-cleanup.md` § REM-4.a, .b, .c
- [ ] Используй codemods из секции «Codemods» в том же файле
- [ ] **Ручная проверка** изменённых файлов — не сломалось ли что в контексте
- [ ] Обнови e2e-тесты, если они матчат старый текст
- [ ] Commit: `refactor(copy): align UI terminology with analyst language (no MCP/channel/tool calls)`

### Step 1.5 — REM-2 docker text

- [ ] Замена в `frontend/app/settings/page.tsx:33`
- [ ] Commit: `fix(settings): remove docker-specific suggestion (works in Electron)`

### Step 1.6 — REM-5 StreamingIndicator удалить

- [ ] `grep -rn "StreamingIndicator" frontend/` — все импорты
- [ ] Замени на `StreamingStages` через `frontend/lib/streaming-stages.ts` (уже есть mapper)
- [ ] Удали `frontend/components/chat/StreamingIndicator.tsx`
- [ ] Удали тип `StreamingStage` если не используется
- [ ] Прогон: `pnpm test` — особенно streaming-stages tests
- [ ] Commit: `refactor(chat): remove deprecated StreamingIndicator, use StreamingStages everywhere`

### Step 1.7 — HIGH-1 Tailwind config decision

- [ ] **Решение:** A (рекомендуется) или B
- [ ] Применяй diff из `02-codebase-cleanup.md` § HIGH-1
- [ ] Если A — пройди по shell-файлам, замени inline `style={{ fontFamily }}` на `className="font-mono"` / `font-jb`
- [ ] Если B — создай utility-классы, замени inline-style
- [ ] Commit: `chore(tailwind): consolidate utility classes via @theme inline (v4)`

### Step 1.8 — HIGH-6, HIGH-7, HIGH-8, HIGH-10 — мелкие правки

- [ ] HIGH-6: убрать дубль «Модель ИИ» в LLMConfigForm + плоский SelectItem
- [ ] HIGH-7: tooltip на disabled «Тест»
- [ ] HIGH-8: kind cards `min-h-[88px]`
- [ ] HIGH-10: AppShell gridTemplateRows = `52px`
- [ ] Commit: `fix(settings,shell): misc layout fixes (label dup, tooltip, kind cards, header alignment)`

### Step 1.9 — HIGH-2 Focus-ring 2px

- [ ] Diff в `button.tsx`, `input.tsx`, `select.tsx`, `chat/Input.tsx`
- [ ] Прогон: Tab по странице — везде видимое 2px ring + offset
- [ ] Commit: `fix(a11y): bump focus-ring to 2px + offset, WCAG 2.4.7 compliance`

### Acceptance Спринт 01

- [ ] Чек-лист из `09-acceptance-criteria.md` § Спринт 01 — все пункты выполнены
- [ ] `pnpm test && pnpm test:e2e` — зелёные
- [ ] PR в main, заголовок: `Sprint 01 — Cleanup (terminology, tokens, deprecated code removal)`

---

## Спринт 02 — Component additions (2–3 дня, ~5 коммитов)

### Step 2.1 — Skeleton

- [ ] Создай `frontend/components/ui/Skeleton.tsx`
- [ ] CSS в `globals.css` (см. `04-motion-system.md` M01)
- [ ] Замени 4 «Загрузка...» места
- [ ] Commit: `feat(ui): add Skeleton component, replace text loading states`

### Step 2.2 — FieldError

- [ ] Создай `frontend/components/ui/FieldError.tsx`
- [ ] Замени все inline `<p className="text-xs text-red-400">` в формах
- [ ] Добавь `aria-invalid` / `aria-describedby` к inputs
- [ ] Commit: `feat(ui): unified FieldError component with a11y attributes`

### Step 2.3 — LiveTestResult

- [ ] Создай `frontend/components/ui/LiveTestResult.tsx`
- [ ] Интегрируй в `MCPConnectionForm.tsx`, `LLMConfigForm.tsx`
- [ ] Commit: `feat(settings): inline test result chip alongside toast`

### Step 2.4 — UndoToast

- [ ] Создай `UndoToast.tsx`, `UndoToastHost.tsx`, `lib/undo-toast.ts`
- [ ] CSS keyframes в `globals.css` (см. M09)
- [ ] Подключи `<UndoToastHost />` в `app/layout.tsx`
- [ ] Расширь `useSessionsStore`: `removeOptimistic`, `restoreOptimistic`, `commitRemove`
- [ ] Замени `window.confirm` в `SessionList.tsx:84`
- [ ] Commit: `feat(chat): optimistic delete with undo toast (replaces window.confirm)`

### Step 2.5 — Settings unification

- [ ] HIGH-3: применяй diff из `02-codebase-cleanup.md` § HIGH-3
- [ ] Перенеси Memory/Insights/Skills в отдельную секцию «Дополнительно»
- [ ] Commit: `refactor(settings): unify padding/radius, move link-cards to dedicated section`

### Acceptance Спринт 02

- [ ] Чек-лист `09-acceptance-criteria.md` § Спринт 02

---

## Спринт 03 — Screen redesigns (2–3 дня, ~5 коммитов)

### Step 3.1 — TraceSummary

- [ ] Создай `frontend/lib/tool-summary.ts` (с маппингом из `mcp-tool-descriptions.ts`)
- [ ] Создай `frontend/components/chat/TraceSummary.tsx`
- [ ] Интегрируй в `ToolTrace.tsx`
- [ ] Прогон: разверни trace — видишь human summary, клик «JSON» → raw
- [ ] Commit: `feat(chat): human-readable trace summary (TraceSummary)`

### Step 3.2 — Welcome → ComposerHub

- [ ] Создай `frontend/lib/welcome-templates.ts`
- [ ] Создай `frontend/components/chat/ComposerHub.tsx` (см. `06-screen-redesigns.md` § Welcome)
- [ ] Замени welcome screen в `app/page.tsx:266-292`
- [ ] Удали сине-подчёркнутые ссылки
- [ ] Commit: `feat(welcome): composer-hub with templates and recent chats strip`

### Step 3.3 — Channel selector enrichment

- [ ] Расширь `MCPConnection` в `lib/types.ts`
- [ ] Backend: `/connections/{id}/info` возвращает новые поля (отдельная задача в backend repo, синхронизируй)
- [ ] Создай `frontend/lib/format-relative-time.ts`
- [ ] Обнови dropdown items в `ChannelSelector.tsx` (см. `06-screen-redesigns.md` § Channel)
- [ ] Убери «Канал: ...» строку
- [ ] Commit: `feat(channel): enrich connection cards with config type, metadata count, last sync`

### Step 3.4 — Status page split

- [ ] Создай `StatusCard` сабкомпонент
- [ ] Реструктурируй `app/status/page.tsx` — high-level cards + collapsible expert-block
- [ ] Все технические термины — в expert-блок
- [ ] Commit: `refactor(status): split into high-level summary + collapsible technical details`

### Step 3.5 — BackendDownBanner

- [ ] Создай `frontend/components/shell/BackendDownBanner.tsx`
- [ ] Подключи в `AppShell` (глобально)
- [ ] Удали или упрости `BackendIndicator` в `app/page.tsx`
- [ ] Commit: `feat(shell): top-banner when backend unavailable + retry`

### Acceptance Спринт 03

- [ ] Чек-лист `09-acceptance-criteria.md` § Спринт 03

---

## Спринт 04 — Motion polish (3–4 дня, ~6 коммитов)

### Step 4.1 — Streaming stages stagger

- [ ] Внеси stagger 80ms в `StreamingStages.tsx`
- [ ] Commit: `chore(motion): stage stagger animation in StreamingStages`

### Step 4.2 — Sparkline draw-in

- [ ] Обнови `Sparkline.tsx` с `getTotalLength` + CSS keyframes
- [ ] Commit: `feat(motion): sparkline draw-in animation`

### Step 4.3 — Send-flight

- [ ] CSS keyframe в `globals.css`
- [ ] Handler в `Input.tsx` handleSubmit
- [ ] Commit: `feat(motion): send button spring press`

### Step 4.4 — Connection pulse refinement

- [ ] Проверь `StatusDot` — все три состояния (online/connecting/offline) имеют корректные анимации
- [ ] Commit: `fix(motion): correct status dot animations`

### Step 4.5 — Drag-over composer

- [ ] Diff в `Input.tsx` с `transition-all duration-200 ease-out` + `scale(1.005)`
- [ ] Commit: `feat(motion): smooth drag-over feedback`

### Step 4.6 — Sidebar collapse

- [ ] Diff в `AppShell.tsx` с CSS transition
- [ ] localStorage persistence
- [ ] Commit: `feat(shell): animated sidebar collapse`

### Step 4.7 — Page enter

- [ ] Добавь `animate-fade-up` на main wrapper в каждой странице
- [ ] **Или** `key={pathname}` в AppShell (если state не пересоздаётся для тяжёлых страниц)
- [ ] Commit: `feat(motion): page enter fade-up on route change`

### Step 4.8 — Onboarding improvements

- [ ] localStorage persistence (см. `07-onboarding-improvements.md` O-1)
- [ ] Resume banner (O-2)
- [ ] Welcome warning if config incomplete (O-3)
- [ ] Шаг 3 → «Память» (O-6)
- [ ] Шаг 4 quick-start examples (O-5)
- [ ] Шаг 3 copy fix (O-4)
- [ ] Commit: `feat(onboarding): persist progress + resume banner + quick-starts`

### Acceptance Спринт 04

- [ ] Чек-лист `09-acceptance-criteria.md` § Спринт 04
- [ ] Прогон в `prefers-reduced-motion: reduce` — все анимации мгновенные

---

## Final review

После всех спринтов:

1. **Light theme audit** — пройди по всем экранам в light-теме, сверь с brand guide.
2. **A11y audit** — Lighthouse + axe-core на каждой странице.
3. **Performance** — Lighthouse Performance score ≥ 90.
4. **Visual diff** — открой `reference/visual-audit-report.html` и сравни с live-приложением.
5. **Score self-check** — пройди по 6 столпам, цель 86/100.
6. **Update docs:**
   - `.brand/BRAND.md` — отметь changelog 2026-05-23 «UX/UI audit redesign».
   - `.planning/` — создай `UI-REVIEW-2026-05-25.md` с финальным score.

---

## Dependency graph

Что от чего зависит — чтобы избежать блокировки:

```
Step 1.1 (tokens)  ──┬─→ Step 4.1–4.7 (motion использует токены)
                     └─→ Step 1.2 (json-tree использует --syntax-*)

Step 1.7 (tailwind) ─→ Step 2.1+ (компоненты могут использовать @theme классы)

Step 2.4 (UndoToast) ─→ зависит от ничего; можно делать параллельно с 2.1–2.3

Step 3.3 (channel) ─→ требует backend изменений; делать одновременно с backend PR

Step 3.1 (TraceSummary) ─→ независим от 3.2 / 3.3
```

Параллелизация:
- Спринт 02 + 03 можно частично перекрыть, если разные люди работают на UI vs backend.
- Спринт 04 — только после 01 (нужны токены).

---

## Что НЕ делать

- ❌ Не трогай `conn.channel` как поле API/модели — это backend контракт
- ❌ Не убирай `MCP_Toolkit_v1.7.0.epf` упоминания — это имя физического файла, аналитики его ищут
- ❌ Не переделывай OnboardingDialog с нуля — он уже 4-шаговый, нужны точечные правки
- ❌ Не добавляй gradient-text, glass-morphism, purple/cyan accents — нарушает brand guide
- ❌ Не используй Inter, Roboto, Arial — только IBM Plex + JetBrains Mono
- ❌ Не делай анимаций > 500ms (кроме loop pulse/skeleton)

---

## Если что-то непонятно

1. Сверься с `reference/visual-audit-report.html` (открой в браузере).
2. Прочитай соседний markdown файл из `design_handoff_audit_redesign/`.
3. Проверь `.brand/BRAND.md` для брендовых правил.
4. Если конфликт между brand guide и handoff — **brand guide побеждает**.

Удачи. После завершения — отправь PR с заголовком: `UX/UI audit redesign — 47→86 (spring 2026)`.
