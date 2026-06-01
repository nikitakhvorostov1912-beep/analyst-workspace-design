# 01 · Context & Status

**Что уже сделано, что осталось.** Перед началом любого спринта прочитай этот файл — не делай повторно то, что уже залито.

---

## ✅ Уже выполнено (с момента UI-REVIEW-2026-05-21)

Подтверждено чтением кода 2026-05-23:

### Tokens & Theme
- ✅ `--bg-hover` определён в `:root` (line 85 design-tokens.css): `--bg-hover: var(--bg-2);` — больше не undefined.
- ✅ Светлая тема имеет полный набор переменных: `--bg-0..4`, `--fg-1..4`, `--bd-1..3`, semantic colors с другими alpha для контраста на sand.
- ✅ `--brand-signal`, `--brand-ink`, `--brand-sand`, `--brand-signal-tint`, `--brand-signal-deep` определены через `[data-accent="signal"]`.

### Components
- ✅ `button.tsx:20` — `destructive` уже использует семантический токен: `bg-[var(--error)] text-white hover:opacity-90`.
- ✅ `badge.tsx:13–18` — `destructive` использует `bg-[var(--error-20)] text-[var(--error)]`.
- ✅ `LogCard.tsx:18–32` — `LEVEL_CLASSES` и `LEVEL_ROW_CLASSES` через семантические токены `--warning-12/40`, `--error-12/40`. Tailwind yellow/red больше нет.
- ✅ `ConnectionStatusBanner.tsx:32–40` — `bg-[var(--error-12)] border-[var(--error-40)] text-[var(--error)]`. Старая `bg-red-950` ушла.
- ✅ `EmptyState.tsx` существует с правильным API: `{ icon, title, description, cta }`.
- ✅ `StreamingStages.tsx` существует с маппингом `tool_name → русский label` (W3.2, 2026-05-22): `execute_query → "Выполняю запрос"` и т.д.
- ✅ `OnboardingDialog.tsx` уже на **4 шагах** с back-кнопками и skip на каждом шаге. **Не реализуй stepper заново** — улучшения мелкие, см. `07-onboarding-improvements.md`.

---

## ❌ Остаётся выполнить

### Блокеры (релизные)

| ID | Файл / Проблема | Где описано |
|---|---|---|
| **REM-1** | `frontend/lib/json-tree.tsx` — хардкод `text-green-300`, `text-orange-300`, `text-purple-300`, `text-red-400` | `02-codebase-cleanup.md` § REM-1 |
| **REM-2** | `frontend/app/settings/page.tsx:33` — текст «Запустите docker compose up» в Electron-сборке | `02-codebase-cleanup.md` § REM-2 |
| **REM-3** | Версии разнобой: Header показывает одну, StencilLockup другую, About третью | `02-codebase-cleanup.md` § REM-3 |
| **REM-4** | Терминология: «канал» / «MCP» / «Tool calls» в видимом UI — 14 мест | `02-codebase-cleanup.md` § REM-4 + `08-copy-glossary.md` |
| **REM-5** | `StreamingIndicator` (старый) сосуществует с `StreamingStages` — нужно удалить и заменить | `05-component-additions.md` § Streaming |

### High

| ID | Что | Где |
|---|---|---|
| HIGH-1 | Tailwind config v3-формата мёртв (v4 импорт) — utility-классы `bg-bg-1` не работают | `02-codebase-cleanup.md` § HIGH-1 |
| HIGH-2 | Focus-ring везде `ring-1` — поднять до `ring-2 + offset` | `02-codebase-cleanup.md` § HIGH-2 |
| HIGH-3 | Settings — разнобой p-4/p-5, rounded-md/rounded-lg | `02-codebase-cleanup.md` § HIGH-3 |
| HIGH-4 | `MCPConnectionList.tsx:33`, `MCPConnectionForm.tsx:324`, `ChannelSelector.tsx:273,296` — слово «канал» в видимом UI | `02-codebase-cleanup.md` § REM-4 |
| HIGH-5 | `window.confirm()` для удаления чата | `05-component-additions.md` § UndoToast |
| HIGH-6 | Двойной заголовок «Модель ИИ» (Settings + label в форме) | `02-codebase-cleanup.md` § HIGH-6 |

### Редизайн (нет в продакшене, целиком новый код)

| Что | Где |
|---|---|
| **Welcome → Composer Hub** — текущий welcome пустой, нужен hub с шаблонами и last-чатами | `06-screen-redesigns.md` § Welcome |
| **Channel selector enrichment** — добавить тип конфигурации (УТ/ERP/УСО), размер метаданных, last-sync | `06-screen-redesigns.md` § Channel |
| **TraceSummary** — двухуровневая модель: summary line + opt-in raw JSON | `05-component-additions.md` § TraceSummary |
| **Status page split** — высокоуровневый блок + collapsible «Технические подробности» | `06-screen-redesigns.md` § Status |
| **UndoToast** — заменить `window.confirm` оптимистичным удалением | `05-component-additions.md` § UndoToast |
| **LiveTestResult** — inline-результат «Тест» вместо только-toast | `05-component-additions.md` § LiveTestResult |
| **FieldError** — единый компонент валидации формы (сейчас inline `<p text-red-400>`) | `05-component-additions.md` § FieldError |

### Motion (нет ни в продакшене, ни в коде)

| Что | Где |
|---|---|
| Skeleton shimmer для loading-состояний | `04-motion-system.md` § Skeleton |
| Sparkline draw-in для MetricCard | `04-motion-system.md` § Sparkline |
| Send-flight (кнопка отправки) | `04-motion-system.md` § SendFlight |
| Connection pulse (online/connecting/offline) | `04-motion-system.md` § PingPulse |
| Drag-over composer | `04-motion-system.md` § DragOver |
| Sidebar collapse | `04-motion-system.md` § SidebarCollapse |
| Page enter-transitions (route changes) | `04-motion-system.md` § PageEnter |
| Toast slide-in (UndoToast) | `04-motion-system.md` § Toast |

---

## Priority view

```
Спринт 01 (1–2 дня)
  REM-1 json-tree colors
  REM-2 docker text
  REM-3 версия в одном месте
  REM-4 терминология
  HIGH-1 tailwind config decision
  HIGH-2 focus-ring 2px
  HIGH-6 двойной заголовок

Спринт 02 (2–3 дня)
  REM-5 StreamingIndicator → StreamingStages (удалить старый)
  HIGH-3 Settings padding/radius унификация
  Component additions: FieldError, LiveTestResult, UndoToast

Спринт 03 (2–3 дня)
  Welcome redesign (composer-hub)
  Channel selector enrichment
  TraceSummary (новый компонент + JSON-tree как expert-mode)
  Status page split
  Onboarding fine-tuning

Спринт 04 (3–4 дня)
  Motion system: skeleton, sparkline, send-flight, ping-pulse, drag-over,
                 sidebar collapse, page enter, toast slide-in
```

Дальше — детали по каждому пункту. См. `10-execution-plan.md` для пошаговой последовательности.
