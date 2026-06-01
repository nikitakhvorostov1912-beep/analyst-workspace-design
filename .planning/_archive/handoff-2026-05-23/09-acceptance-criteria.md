# 09 · Acceptance Criteria

Чек-листы по каждому спринту. Прогоняй после завершения спринта **перед** PR.

---

## Спринт 01 — Codebase cleanup

### Tokens (`03-design-tokens.md`)

- [ ] В DevTools на `:root` видны новые токены: `--t-fast`, `--t-slow`, `--ease-out`, `--ease-spring`
- [ ] `--info`, `--info-12`, `--info-20`, `--info-40` определены в `:root` и `[data-theme="light"]`
- [ ] `--focus-ring`, `--focus-ring-offset` определены
- [ ] `--syntax-string`, `--syntax-number`, `--syntax-bool`, `--syntax-null` определены
- [ ] `--skeleton-bg-from`, `--skeleton-bg-to` определены
- [ ] `--ease-design-ease` и `--duration-normal` остались как aliases (старый код не сломался)
- [ ] `prefers-reduced-motion: reduce` отключает анимации (проверь через DevTools rendering panel)

### REM-1: json-tree

- [ ] `grep "text-green-300\|text-orange-300\|text-purple-300\|text-red-400" frontend/lib/json-tree.tsx` → пусто
- [ ] Раскрыв trace в чате, JSON-tree показывает: строки mint, числа signal-orange, boolean ochre, null muted, error red
- [ ] В light-теме все цвета остаются читаемыми (контраст ≥ 4.5:1)

### REM-2: docker text

- [ ] `grep "docker compose" frontend/` → пусто (или только в comments)
- [ ] `frontend/app/settings/page.tsx:33` показывает новое сообщение

### REM-3: версии

- [ ] `frontend/lib/app-version.ts` создан
- [ ] В Header, StencilLockup default, About — везде одно значение версии
- [ ] `process.env.NEXT_PUBLIC_APP_VERSION` берётся из `package.json` через `next.config`

### REM-4: терминология

Прогон автоматический:
```bash
rg 'aria-label="Выбор канала"' frontend/ → 0 матчей
rg 'инструмент.*MCP' frontend/app frontend/components → 0 матчей
rg 'обработка MCP_Toolkit' frontend/app frontend/components --type tsx → 0 матчей
rg 'DropdownMenuLabel>Канал<' frontend/ → 0 матчей
rg 'Канал: \{conn.channel\}' frontend/ → 0 матчей
rg '"Канал"' frontend/app frontend/components → 0 матчей (label-strings)
```

Прогон визуальный:
- [ ] В Header dropdown «Базы 1С» (не «Канал»)
- [ ] В `/settings/memory` empty state «Не выбрана база 1С» (не «канал»)
- [ ] В `/settings/skills` empty state «Не выбрана база 1С»
- [ ] В Insights метрика «Запросов к 1С» (не «Tool calls»)
- [ ] В Insights колонки таблицы «Запросов / Ошибок / % ошибок»
- [ ] В Insights «Топ баз 1С» (не «Top channels»)
- [ ] В Status основной блок не содержит «Канал», «Версия MCP», «Сервер MCP» — только в expert-collapsible

### HIGH-1: tailwind config

- [ ] Принято решение (вариант A или B из `02-codebase-cleanup.md` § HIGH-1)
- [ ] Если A — `@theme inline` блок в `globals.css` работает, `bg-bg-1` / `font-jb` / `duration-normal` валидны
- [ ] Если B — utility-классы `.font-jb`, `.font-plex-mono` в `globals.css`, inline `style={{ fontFamily }}` удалены

### HIGH-2: focus-ring 2px

- [ ] В `button.tsx` — `focus-visible:ring-2 ring-offset-2 ring-offset-[var(--bg-0)]`
- [ ] Любая кнопка при Tab навигации — видимое 2px ring + 2px offset
- [ ] В composer `<textarea>` focus — signal-color border (2px) без offset

### HIGH-3: settings padding/radius

- [ ] Все sections в `/settings` — `p-5 rounded-lg`
- [ ] Memory/Insights/Skills link-cards в отдельной группе под `<h2>Дополнительно</h2>`
- [ ] Внутренний `<div className="p-4">` обёртки MCPConnectionForm — убран

### HIGH-6: двойной заголовок

- [ ] В `/settings` под «Модель ИИ» нет повторного `<label>Модель ИИ</label>` — заменено на «Языковая модель»
- [ ] SelectItem рендерится плоско (label + dim description), не двухстрочно
- [ ] Trigger не двойной высоты при выбранном пресете

### HIGH-7: «Сначала сохраните»

- [ ] Кнопка «Тест» в disabled-state имеет tooltip с подсказкой
- [ ] Toast про «сначала сохраните» убран

### HIGH-8: kind cards высота

- [ ] KindCards «Встроенный сервер» / «Прокси» одинаковой высоты (`min-h-[88px]`)

### HIGH-10: header height

- [ ] AppShell gridTemplateRows = `52px 1fr auto` (либо `56px`, но синхронно с Header)
- [ ] Под header нет 4px пиксельной щели

### REM-5: StreamingIndicator → Stages

- [ ] `frontend/components/chat/StreamingIndicator.tsx` удалён
- [ ] `grep "StreamingIndicator" frontend/` → 0 матчей
- [ ] При streaming видны stages (мульти-стадийная визуализация), не «Анализирую...»

---

## Спринт 02 — Полировка и new components

### FieldError

- [ ] `frontend/components/ui/FieldError.tsx` создан
- [ ] Все 17+ inline `<p className="text-xs text-red-400">{errors.X}</p>` заменены на `<FieldError message={errors.X} />`
- [ ] Каждый input с ошибкой имеет `aria-invalid="true"` и `aria-describedby`

### LiveTestResult

- [ ] `frontend/components/ui/LiveTestResult.tsx` создан
- [ ] В MCPConnectionForm рядом с «Тест» виден inline-результат (success/error/testing chip)
- [ ] В LLMConfigForm — то же
- [ ] При success виден ms отклика
- [ ] При error виден короткий error message

### UndoToast

- [ ] `frontend/components/ui/UndoToast.tsx` + `UndoToastHost.tsx` + `lib/undo-toast.ts` созданы
- [ ] `<UndoToastHost />` подключён в `app/layout.tsx`
- [ ] `window.confirm()` в `SessionList.tsx:84` заменён на optimistic delete + UndoToast
- [ ] При клике «Удалить» — чат пропадает из UI мгновенно
- [ ] В правом нижнем углу появляется toast с кнопкой «↺ Отменить» и progress-баром на 5 сек
- [ ] При клике Undo — чат возвращается, backend DELETE не вызывается
- [ ] При истечении 5 сек — DELETE вызывается, toast уезжает с slide-down animation
- [ ] Hover на toast — pause progress-bar (animation-play-state: paused)

### Skeleton

- [ ] `frontend/components/ui/Skeleton.tsx` создан
- [ ] Loading на `app/page.tsx:174`, `sessions/[id]/page.tsx:188`, `settings/page.tsx:78`, `insights/page.tsx:84` использует Skeleton (нет голого текста «Загрузка...»)
- [ ] Skeleton имеет shimmer animation (1.6s linear infinite)

---

## Спринт 03 — Screen redesigns

### Welcome → Composer Hub

- [ ] `frontend/components/chat/ComposerHub.tsx` создан
- [ ] `app/page.tsx:226-292` (старый welcome) заменён на `<ComposerHub />`
- [ ] Eyebrow показывает active базу + config type + status pulse
- [ ] Большой composer на главной — focal point
- [ ] Templates chips strip — 4-6 шаблонов
- [ ] «↺ Повторить последний» — динамический (берётся из последней user-сессии)
- [ ] Recent chats strip — счётчик + ссылка на sidebar focus
- [ ] Старые две сине-подчёркнутые ссылки удалены

### Channel selector enrichment

- [ ] `MCPConnection` модель расширена: `config_type`, `metadata_object_count`, `metadata_last_sync`
- [ ] Backend `/connections/{id}/info` возвращает эти поля
- [ ] Dropdown item показывает:
  - имя + config_type chip (УТ / ERP / УСО)
  - `{n} объектов · {n} инструментов · обновлено {relative-time}`
- [ ] Active item имеет `bg-[var(--accent-08)]` подсветку
- [ ] Offline item: «Офлайн · последняя связь N · ↻ Перепроверить»
- [ ] Поле «Канал: ...» — удалено из dropdown
- [ ] DropdownMenuLabel «Базы 1С» (не «Канал»)
- [ ] При null `config_type` — chip не рисуется (gracefully)

### TraceSummary

- [ ] `frontend/components/chat/TraceSummary.tsx` создан
- [ ] `frontend/lib/tool-summary.ts` создан с маппингом для всех tool_names из `mcp-tool-descriptions.ts`
- [ ] В `ToolTrace.tsx` при expanded — рендерится `<TraceSummary>` per tool_call
- [ ] Каждый шаг показывает: индекс / «что сделал» / «что получил» / duration_ms
- [ ] Кнопка «JSON» раскрывает raw view с правильными --syntax-* цветами
- [ ] Свёрнутое состояние trace — короткое summary в шапке (3 шага · 872 мс)

### Status page split

- [ ] Верхний блок: status-dot + «Всё в порядке» / «Найдены проблемы»
- [ ] Три карточки: Базы 1С / Модель ИИ / Серверная часть
- [ ] Под ними — `<details>Технические подробности (для разработчика)</details>`
- [ ] В expert-блоке: endpoint URL, channel, mcp version, tools loaded count
- [ ] Основной блок не содержит технических терминов

### Onboarding improvements

- [ ] localStorage persistence работает (закрой вкладку → продолжай с того же шага)
- [ ] Шаг 3 переименован на «Память»
- [ ] Шаг 4 «Готово!» — добавлены quick-start examples
- [ ] При success — `clearProgress()` отрабатывает

---

## Спринт 04 — Motion polish

### Skeleton M01

- [ ] `.skeleton` класс работает с `@keyframes skeleton-shimmer`
- [ ] Все 4 loading-страницы используют Skeleton

### Streaming stages M02

- [ ] Stages вылетают по очереди с 80ms stagger
- [ ] Активная стадия pulse'ит точкой

### Sparkline draw-in M03

- [ ] В MetricCard линия sparkline рисуется один раз при mount (1.6s)
- [ ] Заливка появляется с задержкой 0.4s
- [ ] `getTotalLength()` вызывается корректно для динамической длины

### Send-flight M04

- [ ] Send button короткий spring press при клике (240ms)
- [ ] Анимация не блокирует submit

### Connection pulse M05

- [ ] StatusDot online → pulse, connecting → blink, offline → статика

### Drag-over M06

- [ ] Composer при dragover плавно подсвечивается + лёгкий scale(1.005)
- [ ] При dragleave — плавно возвращается

### Sidebar collapse M07

- [ ] AppShell имеет `data-sidebar="collapsed/expanded"` атрибут
- [ ] Grid-template-columns анимируется (320ms)
- [ ] State сохраняется в localStorage `analyst.sidebar-collapsed`
- [ ] Кнопка «PanelLeft» в Header работает

### Page enter M08

- [ ] Между маршрутами короткий fade-up при смене страницы
- [ ] Тяжёлый state (chat history) не пересоздаётся

### Toast slide-in M09

- [ ] UndoToast slide-up из низа экрана (280ms, ease-spring)
- [ ] Exit — slide-down (240ms)
- [ ] Progress-bar — linear width 100→0 за durationMs

---

## Global Acceptance (после всех спринтов)

### Accessibility

- [ ] Все интерактивные элементы Tab-навигируемы
- [ ] Focus-ring 2px виден везде
- [ ] Иконочные кнопки имеют `aria-label`
- [ ] Декоративные иконки имеют `aria-hidden="true"`
- [ ] Контраст текста ≥ 4.5:1 на всех фонах (тестируй через Lighthouse / axe-core)
- [ ] WCAG 2.4.7 — keyboard focus visible везде
- [ ] `prefers-reduced-motion: reduce` — все анимации мгновенные

### Light theme

- [ ] Каждая страница (welcome, chat, settings, status, insights, about, guide, onboarding) визуально читаема в light-теме
- [ ] Scrollbar в light-теме — тонкий нейтральный (не тёмные жирные полосы)
- [ ] Dialog overlay в light — не чёрный, не грязно-серый
- [ ] Все семантические цвета (success/warning/error) имеют контраст ≥ 4.5:1 на sand-фоне

### Branding

- [ ] Лого Stencil/Mono консистентно (Header, Onboarding, About — одинаковый шрифт IBM Plex Mono 700, marker orange)
- [ ] Версия одинаковая во всех местах
- [ ] Eyebrow-pattern (JB Mono 10px tracking 0.18em uppercase) применён в:
  - Channel selector eyebrow
  - StatusCard label
  - Settings section sub-titles
  - ComposerHub eyebrow
  - Welcome recent chats strip
- [ ] Marker (оранжевый квадрат) — на Sidebar новый чат, section heads
- [ ] Brand-tick (22×2 оранжевая черта) — на composer

### Tests

- [ ] `pnpm test` — все unit tests зелёные
- [ ] `pnpm test:e2e` — все Playwright tests зелёные
- [ ] Никаких новых console errors / warnings в браузере

### Performance

- [ ] Lighthouse Performance ≥ 90 на главной
- [ ] CSS bundle size не вырос больше чем на 5KB

---

## Финальная проверка score (по столпам)

Исходный baseline 47/100. Целевой 86/100. После всех спринтов прогоняй self-audit по тем же 6 столпам:

| Столп | Цель |
|---|---|
| 1. Visual consistency | ≥ 14/16 (после редизайна экранов и токенов) |
| 2. Information hierarchy | ≥ 14/16 (после убирания дублей и копи-правок) |
| 3. Affordance & feedback | ≥ 14/16 (после LiveTestResult, FieldError, focus-ring, UndoToast) |
| 4. Density & rhythm | ≥ 14/16 (после унификации settings и header alignment) |
| 5. Empty / error / loading | ≥ 14/16 (после Skeleton, BackendDownBanner, FieldError) |
| 6. Accessibility | ≥ 16/20 (после focus-ring и aria-labels) |

Итого ≥ 86/100.
