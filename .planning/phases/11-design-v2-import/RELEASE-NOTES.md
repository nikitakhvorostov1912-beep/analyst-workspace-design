# Release Notes — v1.2.0 Design v2 Import

**Date:** 2026-05-18
**Type:** Visual / UX upgrade (no backend changes)
**Tag:** v1.2.0 (pending manual smoke approval)
**Branch:** `feature/m5-design-v2-import` (8 commits)

---

## What's New

### Phase 11: Design v2 Import (from Claude Design)

После handoff из Claude Design — полная переработка визуального языка под единый design token system. Без breaking changes в backend API.

#### 1. Палитра + темы (Phase 11.1)

- **Тёмно-синий accent** (#3b82f6 / Tailwind blue-500) — заменил оранжевый (#f97316)
  - 3 алтернативных варианта через `<body data-accent="X">`: `blue` (default), `clinical`, `indigo`, `orange` (legacy)
- **Granular tokens**: `--bg-0..3` (background levels), `--fg-1..4` (foreground), `--bd-1..3` (borders)
- **Semantic colors**: success / warning / error c вариантами 12/20 opacity (`--warning-12`, `--error-20`, etc.)
- **7 keyframes** в `design-tokens.css`: `fade-up`, `fade-in`, `scale-in`, `dialog-in`, `blink`, `status-pulse`, `skeleton-pulse`, `streaming-shimmer`
- Tailwind theme.extend синхронизирован с CSS variables
- Backwards-compat aliases (`--bg`, `--fg`, `--border`) сохранены — legacy компоненты не сломаны

#### 2. Атомарные компоненты (Phase 11.2)

- **`StatusDot`** — точка статуса 3 состояния: `online` (pulse), `offline`, `connecting` (blink)
- **`EmptyState`** — пустое состояние с опциональной иконкой + CTA (button или anchor)
- **`ErrorBanner`** — баннер ошибок с 3 severity (info / warning / error) + retry/dismiss callbacks
- **`CardActionMenu`** — обёртка над shadcn DropdownMenu, типизированные `CardActionItem[]` с icons + kbd hints + destructive variant
- **`CardHeader`** — унифицированный header для 6 типов карточек (table/object/log/metric/references/code) с автоматическим accent цветом per type

#### 3. Header + Onboarding (Phase 11.3)

- **Header** redesign: 3-col grid layout, brand mark «1С» в accent-08 квадрате 28×28, version chip «v1.1.0»
- **AnonymizationToggle** — amber pill (`--warning-12/20`) когда ВКЛ, тёмный border-bd-2 когда ВЫКЛ
- **ModelBadge** — Sparkles icon в accent + mono model name + dimmed temperature
- **Onboarding wizard 3→4 шага**:
  - Шаг 1 — Подключение MCP (без изменений)
  - Шаг 2 — Настройка LLM (без изменений)
  - **Шаг 3 NEW** — Обучение на сессиях (privacy-first opt-in, switch + info callout)
  - Шаг 4 — Готово (с динамическим summary: connection name + learn flag)
- **StepIndicator** — теперь generic (любое количество шагов, опциональные labels[])

#### 4. Streaming pipeline (Phase 11.4)

- **`StreamingStages`** — pipeline визуализация этапов LLM call с иконками + переходами:
  - Analyzing (Search icon) → Tool (Cog + animate-spin) → Tool done (Check + duration) → Finalizing (PenLine)
  - 3 tone variants: muted / accent / success
  - 45% opacity для будущих этапов
- **Adapter** `buildStreamingStages()` — преобразует SSE state (streamingStage + currentToolName + tool_calls) в линейный `Stage[]`
- **`CardSkeleton`** — generic loading placeholder (header + N body rows, animate-skeleton-pulse)
- **`AssistantMessage`** теперь рендерит StreamingStages вместо плоского StreamingIndicator
- **`ChannelSelector`** — локальный StatusDot заменён на атомарный через `PingDot` wrapper (mapping PingStatus → ConnectionStatus)

#### 5. Animations (Phase 11.5)

- `animate-fade-up` на mount всех cards через CardRenderer wrapper
- `animate-status-pulse` на online StatusDot — сглаженная пульсация
- `animate-blink` на connecting status + active tool blinking dot в StreamingStages
- `animate-fade-up` на transitions между Onboarding шагами

---

## Метрики качества

| Metric | v1.1.0 | v1.2.0 | Delta |
|--------|--------|--------|-------|
| Vitest tests | 219 | **273** | +54 |
| Test files | 30 | **38** | +8 |
| Build time | 10.6s | **6.6s** | −38% |
| New components | — | **12** | StatusDot, EmptyState, ErrorBanner, CardActionMenu, CardHeader, StreamingStages, CardSkeleton + 4 rewrites + adapter |
| Breaking changes API | — | **0** | Backend, REQ-IDs, fetcChat, /sessions, /connections все идентичны |

---

## Что НЕ вошло в v1.2.0 (явный технический долг)

Эти задачи requ separate session — слишком инвазивные / требуют ручной верификации:

1. **6 cards refactor через CardHeader** — TableCard/ObjectCard/LogCard/MetricCard/ReferencesCard/CodeCard сохраняют legacy headers. Каждая card имеет уникальные тесты которые могут сломаться. CardHeader готов и протестирован, refactor — отдельной фазой.
2. **ToolTrace visual upgrade** — план 11.4 предполагал mini chips + accordion. Сохранено: `copy as curl` фича + все testids + текст. Visual upgrade deferred.
3. **CardRenderer skeleton при null payload** — нужны backend изменения (loading state в SSE events). Compount без backend бесполезно.
4. **Playwright `design-v2.spec.ts` smoke** — требует запущенного backend (:8010) + frontend (:3010). Manual smoke pending.
5. **Tailwind семантические aliases** — сейчас arbitrary `bg-[var(--bg-1)]` в новом коде. Семантические `bg-surface` / `bg-raised` — для читаемости (cosmetic).

---

## Phase 11 commit log (feature/m5-design-v2-import)

| Commit | Scope |
|--------|-------|
| `1031047` | feat(design-tokens): Phase 11.1 — palette + animations |
| `98ff863` | feat(ui): StatusDot + EmptyState + ErrorBanner |
| `3f23ec0` | feat(cards): CardActionMenu + CardHeader |
| `3b735fb` | feat(shell): Header + AnonymizationToggle + ModelBadge redesign |
| `b1e290d` | feat(onboarding): wizard 3→4 steps with Learn opt-in |
| `94857af` | feat(chat,cards): StreamingStages + CardSkeleton primitives |
| _AssistantMessage_ | feat(chat): integrate StreamingStages via SSE adapter |
| _ChannelSelector_ | feat(shell): ChannelSelector uses atomic StatusDot |
| _CardRenderer_ | feat(cards): animate-fade-up on mount via wrapper |

---

## Migration notes

- **Никаких изменений в backend** — DATABASE_URL, REQ-IDs, /chat SSE контракт, /sessions, /connections, /llm-config — все идентичны v1.1.0.
- **localStorage**: добавлен новый ключ `analyst.learn_enabled` (boolean). Default `false` для существующих юзеров (флаг отсутствует → лечится как false).
- **Существующие настройки сохраняются**: MCP connections, LLM config, sessions, активный канал, anon flag — все без миграции.
- **CSS variables**: backwards-compat aliases (`--bg`, `--bg-elevated`, `--fg`, `--fg-muted`, `--border`, `--accent`) сохранены — старые компоненты рендерятся правильно.

---

## Тестирование перед релизом (manual smoke на :3010)

1. **Запустить backend**: `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload`
2. **Запустить frontend**: `cd frontend && pnpm dev` (:3010)
3. **Открыть Chrome / Electron app**
4. **Проверить:**
   - [ ] Header показывает brand mark «1С» в синем accent
   - [ ] AnonymizationToggle переключается ВКЛ → amber pill
   - [ ] ModelBadge показывает Sparkles + model name
   - [ ] Channel selector dropdown работает, StatusDot пульсирует при `online`
   - [ ] Onboarding (если первый запуск) — 4 шага
   - [ ] Learn switch toggles, info callout появляется
   - [ ] Отправить сообщение → StreamingStages показывает pipeline-этапы с иконками
   - [ ] После завершения — Tool trace появляется, expand работает, copy as curl работает
   - [ ] Cards отображаются с fade-up анимацией mount

5. **Если всё ✅** — `git tag v1.2.0` + `git push origin v1.2.0`
6. **Если ✗** — фиксы + retest

---

## Coming Next

- **Phase 11.4 cards refactor** — 6 cards через CardHeader (отдельная фаза)
- **Phase 11.4 ToolTrace visual upgrade** — mini chips + accordion
- **Phase 8 STACK Integration** — `.claude/skills/` + локальный CLAUDE.md routing (protection from wrong-project context errors)
- **Phase 9 Sessions DB Init** — Electron `app.getPath('userData')` для DATABASE_URL
- **Phase 10 LEARN Engine** — SQLite-vec + embeddings + RAG-orchestrator
- **v1.3.0** — после всех 11.4 cards + 11.5 e2e smoke + Phase 8/9/10
