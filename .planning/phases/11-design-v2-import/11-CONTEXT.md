# Phase 11: Design v2 Import — Context

**Gathered:** 2026-05-18
**Status:** Ready for planning
**Source:** Claude Design handoff `Рабочее место 1с Аналитик.zip` → `temp/from-claude-design-20260518-111524/`

<domain>
## Phase Boundary

**Что делает эта фаза:**
Импортирует визуальный язык из Claude Design v2 handoff в реальный проект. Это **визуальная итерация**, не functional pivot — backend API, useChatStream, SSE events, fetchConnections и вся бизнес-логика остаётся as-is. Меняется только UI: tokens, атомарные компоненты, layout Header, Onboarding wizard, StreamingStages, унифицированные Cards.

**Outcome:**
1. Открываю приложение на :3010 → новый Header (brand «1С Аналитик v1.1.0» + channel popover с search + anon pill amber + model badge + cmd-k)
2. Onboarding 4-step (MCP → LLM → Обучение → Готово) с progress bar и success animations
3. StreamingStages вместо текстового индикатора: 🔍 → 📚 → ⚙️ (spin) → ✓ → ✍️
4. 6 типов cards с унифицированным CardHeader + action menu
5. Smooth animations: fade-up на сообщениях, scale-in на popovers, dialogIn на modals
6. Tag v1.2.0, новый Electron installer
</domain>

<decisions>
## Implementation Decisions

### Source files (Claude Design output)

```
temp/from-claude-design-20260518-111524/
├── index.html              ← preview (196.8 KB)
├── app.jsx                 ← Header + Sidebar + AppShell (33.5 KB)
├── thread.jsx              ← UserMessage + StreamingStages + ToolTrace + AssistantMessage (27.3 KB)
├── cards.jsx               ← CardHeader + CardActionMenu + 6 cards + AnonText (28.1 KB)
├── modals.jsx              ← Onboarding 4-step + Settings + Cmd-K (40.6 KB)
├── data.jsx                ← mock data (не импортируем)
├── icons.jsx               ← custom Icon library (заменим на lucide-react)
└── tweaks-panel.jsx        ← Tweaks panel (для повторных итераций, не импортируем)
```

### Стратегия — VISUAL LANGUAGE ONLY

- **Берём:** tokens (CSS variables), structure (компоновка), animations (keyframes), layout patterns (Header columns, popover anchoring), micro-interactions (hover, focus, transitions)
- **НЕ берём:** mock data, custom Icon library, inline CSS-in-JS блоки (мигрируем в Tailwind), бизнес-логику (она наша)
- **Сохраняем:** все props контракты текущих компонентов, useChatStream API, SSE event types, backend client funcs

### Conversion plan: JSX → TSX + Tailwind

| Claude Design | Наш проект |
|---|---|
| `.jsx` files | `.tsx` + типы props |
| Inline `<style>{`...`}</style>` | Tailwind classes (через `theme.extend`) |
| Custom `Icon.X` | `lucide-react` → `<X />` |
| `MCP_CONNECTIONS` mock | `fetchConnections()` API |
| `window.ANONYMIZED` mock | реальный `submit_for_deanonymization` MCP call |
| `setStep()` local | OnboardingDialog state (уже есть, расширить) |
| CSS variables `--bg-1` | Tailwind tokens `bg-bg-1` (через safelist или class names) |
| Inline `<button>` popovers | shadcn `<Popover>`, `<DropdownMenu>` |

### Что КОНКРЕТНО получено от Claude Design (что взять)

**Header:**
- Brand mark «1С» 28×28 с accent-08 bg + accent-20 border
- Channel selector — center, button с StatusDot + name + url (mono muted) + chevron
- Channel popover — w-420, search input, items с StatusDot + name + url/lastPing + check
- Anon toggle pill amber (`var(--warning-12)`, `var(--warning-20)` border)
- Model badge с Sparkles icon + model mono + `· 0.3` temp
- Cmd-K trigger с ⌘K kbd hint
- Health + Help + Settings icon buttons

**Onboarding (4-step):**
- Progress bar сверху (заливается на 100%)
- Step pills: done (Check icon) / active (number, accent fill) / future (number, muted)
- Skip button «Пропустить настройку» сверху-справа
- Step 1 MCP: name + endpoint + ping с success result «124ms · 47 tools обнаружено»
- Step 2 LLM: endpoint + api_key (eye toggle) + model + temperature range
- Step 3 Learn opt-in: toggle card + info panel «Нужен отдельный API для embeddings»
- Step 4 Готово: confetti или success state + CTA «Начать»

**StreamingStages:**
- Horizontal flex с stage items + `→` separators
- 5 типов: analyzing (Search) / learn (BookOpen, accent) / tool (Cog spin) / tool_done (Check, success) / finalizing (PenLine)
- Active stage: bg accent-08, blink dot
- Done stage: opacity 1 + Check icon replaces
- Future stage: opacity 0.45

**Tool Trace:**
- Compact head: chevron + count + total ms + mini chips names
- Expanded body: per-call с status dot (green/red) + name (mono) + duration

**Unified CardHeader:**
- Type icon (28×28 rounded-7) — color per type: metric=success, log=warning, code/table/object/refs=accent
- Title (font-medium 13.5px) + meta line (12px muted) с tool chip
- Anon pill справа (если anonymizable)
- Action menu `...` с items: Copy / Pin / Maximize / Export CSV / Refresh / Hide

**Animations:**
- `fade-up` — translateY(8px) → 0, opacity 0 → 1, 200ms ease
- `scale-in` — scale(0.95) → 1, opacity 0 → 1, 150ms ease (popovers)
- `dialogIn` — scale(0.96) → 1, opacity 0 → 1, 200ms ease (modals)
- `spin` — rotate 0→360, 1s linear infinite
- `blink` — opacity 1→0.4→1, 0.9s infinite
- Status dot pulse 2s infinite (custom keyframe)

### Что НЕ покрыто Claude Design'ом (нужно делать руками после импорта)

- Sidebar (search input + virtualization + pin) — Phase 11.3 включит
- 6 cards body (TableCard sticky header, LogCard severity timeline, MetricCard sparkline) — Phase 11.4 импорт + кастомные доделки
- LocalDataSection (Phase 9) и LearnSection (Phase 10) — отдельные фазы M5
- LearnContextBadge — частично в Claude Design (BookOpen иконка в StreamingStages есть), отдельный компонент под message — в Phase 10.2

### Risk surface

- **Tailwind 4 не понимает `var(--xyz)`** в class names напрямую — нужны utility classes (через `theme.extend.colors` `bg-1: 'var(--bg-1)'`) или прямое использование как inline style
- **shadcn `<Popover>` отличается от Claude Design popover** — нужно мапить onOpenChange + content positioning
- **JSX без типов** — нужно вручную выводить props interface для каждого компонента
- **vitest могут сломаться** — текущие тесты ассертят конкретные классы/data-testid, после рефакторинга обновлять
- **Visual regression** — без screenshot-tests легко не заметить расхождение; будем сверяться вручную с `index.html`
</decisions>

<canonical_refs>
## Canonical References

### Project (читать перед каждым plan)
- `CLAUDE.md` — концепция, баны
- `.claude/memory/design-constraints.md` — verbatim запреты
- `.planning/ROADMAP.md` — Phase 11 секция
- `frontend/components/` — все 70+ существующих `.tsx`
- `frontend/lib/types.ts` — `SSEEvent` union, `Card` types

### Claude Design source
- `temp/from-claude-design-20260518-111524/index.html` — single-page preview (открыть в browser для reference)
- `temp/from-claude-design-20260518-111524/app.jsx` — Header + Sidebar logic
- `temp/from-claude-design-20260518-111524/thread.jsx` — StreamingStages + ToolTrace + UserMessage
- `temp/from-claude-design-20260518-111524/cards.jsx` — CardHeader + CardActionMenu + 6 cards
- `temp/from-claude-design-20260518-111524/modals.jsx` — Onboarding 4-step

### External
- Tailwind 4 theme extend: <https://tailwindcss.com/docs/theme>
- shadcn Popover: <https://ui.shadcn.com/docs/components/popover>
- lucide-react icons: <https://lucide.dev/icons/>
</canonical_refs>

<specifics>
## Specifics

### Mapping таблица CSS variables → Tailwind tokens

| Claude Design CSS var | Tailwind token (theme.extend.colors) | Использование |
|---|---|---|
| `--bg-1` | `bg.root` (#0a0a0a) | Body, header, app shell |
| `--bg-2` | `bg.surface` (#141414) | Cards, popovers |
| `--bg-3` | `bg.raised` (#1a1a1a) | Hover, raised |
| `--fg-1` | `fg.primary` (#e5e5e5) | Main text |
| `--fg-2` | `fg.secondary` (#a5a5a5) | Secondary text |
| `--fg-3` | `fg.muted` (#8a8a8a) | Muted text |
| `--fg-4` | `fg.subtle` (#5a5a5a) | Subtle text |
| `--bd-1` | `bd.subtle` (#1f1f1f) | Subtle borders |
| `--bd-2` | `bd.emphasis` (#2a2a2a) | Emphasis borders |
| `--bd-3` | `bd.strong` (#3a3a3a) | Hover borders |
| `--accent` | `accent.DEFAULT` (#5cb8ff) | Primary action |
| `--accent-08` | `accent.08` (rgba(92,184,255,0.08)) | Tinted bg |
| `--accent-20` | `accent.20` (rgba(92,184,255,0.20)) | Tinted border |
| `--success` | `success.DEFAULT` (#4ade80) | Success states |
| `--warning` | `warning.DEFAULT` (#fbbf24) | Warning, anon |
| `--warning-12` | `warning.12` | Anon pill bg |
| `--warning-20` | `warning.20` | Anon pill border |
| `--error` | `error.DEFAULT` (#f87171) | Error states |

### Mapping таблица animation tokens

| Claude Design | Tailwind |
|---|---|
| `--t-micro: 150ms` | `transitionDuration: { micro: '150ms' }` |
| `--t-normal: 200ms` | `transitionDuration: { normal: '200ms' }` |
| `--t-large: 300ms` | `transitionDuration: { large: '300ms' }` |
| `--ease: cubic-bezier(0.4, 0, 0.2, 1)` | `transitionTimingFunction: { 'design-ease': 'cubic-bezier(0.4, 0, 0.2, 1)' }` |

### Mapping таблица keyframes

```ts
// tailwind.config.ts theme.extend
keyframes: {
  'fade-up': {
    '0%': { opacity: '0', transform: 'translateY(8px)' },
    '100%': { opacity: '1', transform: 'translateY(0)' },
  },
  'scale-in': {
    '0%': { opacity: '0', transform: 'scale(0.95)' },
    '100%': { opacity: '1', transform: 'scale(1)' },
  },
  'dialog-in': {
    '0%': { opacity: '0', transform: 'scale(0.96)' },
    '100%': { opacity: '1', transform: 'scale(1)' },
  },
  'blink': {
    '0%, 100%': { opacity: '1' },
    '50%': { opacity: '0.4' },
  },
  'status-pulse': {
    '0%, 100%': { boxShadow: '0 0 0 0 rgba(74,222,128,0.4)' },
    '50%': { boxShadow: '0 0 0 4px rgba(74,222,128,0)' },
  },
},
animation: {
  'fade-up': 'fade-up 200ms cubic-bezier(0.4,0,0.2,1)',
  'scale-in': 'scale-in 150ms cubic-bezier(0.4,0,0.2,1)',
  'dialog-in': 'dialog-in 200ms cubic-bezier(0.4,0,0.2,1)',
  'blink': 'blink 0.9s infinite',
  'status-pulse': 'status-pulse 2s infinite',
},
```

### Sequence

Plan 11.1 (tokens) → 11.2 (atoms) → 11.3 (shell + onboarding) → 11.4 (thread + cards) → 11.5 (animations + smoke + release).

Каждый plan = атомарный commit (или 2-3 commit'а внутри). После каждого — vitest + build + manual smoke.

### Что НЕ доставляется в Phase 11

- Sidebar virtualization (react-window) — Phase 12 если понадобится
- LearnSection / LocalDataSection — Phase 9/10 отдельно
- Voice input / attach file — out of MVP
- Cards body deep customization (только header + action menu) — body адаптируется, но без novelties
- macOS / Linux Electron — Out of Roadmap
</specifics>

<deferred>
## Deferred (НЕ в Phase 11)

- Tweaks panel из `tweaks-panel.jsx` — он только для дальнейшей итерации в Claude Design, в продукт не идёт
- Mock data adapters — реальный API уже работает
- Theme switcher light/dark — только dark
- Custom Icon library — заменяем на lucide-react целиком
- Sidebar full rebuild — частично (search) в 11.3, virtualization отдельно
</deferred>

---
*Phase: 11-design-v2-import*
*Context gathered: 2026-05-18 после Claude Design handoff*
