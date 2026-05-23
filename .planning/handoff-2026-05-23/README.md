# Handoff: «1С Аналитик» — UX/UI Audit & Redesign

**Целевой инструмент:** Claude Code в репозитории `analyst-workspace-design/`
**Дата handoff:** 2026-05-23
**Базовый аудит:** `.planning/UI-REVIEW-2026-05-21.md` (часть фиксов уже выполнена — этот пакет учитывает текущее состояние кода)

---

## Что это

Полный технический handoff: бери и делай. Сюда входят:
- актуальная карта **что уже починено** vs **что осталось** (часть блокеров из исходного аудита от 21 мая уже залита: LogCard, ConnectionStatusBanner, Button destructive, `--bg-hover` определён),
- **точные file:line диффы** для всех оставшихся правок,
- **спецификации новых компонентов** (UndoToast, TraceSummary, FieldError, LiveTestResult, EnhancedChannelCard и т.д.) — props, поведение, стили,
- **редизайн пяти экранов** в брендовой системе Stencil/Mono с подробной разметкой,
- **motion-система** — keyframes, длительности, easing, integration points,
- **acceptance criteria** для каждого спринта.

Папка `reference/visual-audit-report.html` — единый интерактивный визуал-отчёт, где все эти решения показаны вживую. Открывай в браузере, чтобы увидеть глазами то, что описано здесь словами.

---

## О формате design files

Файлы внутри `reference/` — **визуальный референс**, HTML-прототипы, демонстрирующие намеренный вид и поведение. Это **не** копировать в продакшен напрямую — задача в том, чтобы воспроизвести их в существующем стеке (Next.js 15 / React 19 / Tailwind v4 / shadcn/ui), используя уже существующие компоненты `frontend/components/ui/*` и токены из `frontend/styles/design-tokens.css`.

## Fidelity

**High-fidelity.** Все цвета (hex), типографика (font-family, size, weight, letter-spacing, line-height), отступы и моушн (длительности, easing, свойства) указаны точно. Воспроизводи pixel-perfect, не переинтерпретируй.

---

## Структура папок

```
design_handoff_audit_redesign/
├── README.md                          ← этот файл
├── 01-context-and-status.md           ← что уже сделано, что осталось
├── 02-codebase-cleanup.md             ← оставшиеся хардкод/term фиксы (file:line + diffs)
├── 03-design-tokens.md                ← добавляемые токены: motion, info, focus
├── 04-motion-system.md                ← keyframes + правила + integration map
├── 05-component-additions.md          ← новые компоненты (5 шт.) + ревизии существующих
├── 06-screen-redesigns.md             ← Welcome, Chat, Channel, Status — layout-specs
├── 07-onboarding-improvements.md      ← мелкие улучшения OnboardingDialog
├── 08-copy-glossary.md                ← терминологическая таблица замен
├── 09-acceptance-criteria.md          ← чек-листы по спринтам
├── 10-execution-plan.md               ← порядок выполнения, dependencies между файлами
└── reference/
    └── visual-audit-report.html       ← интерактивный визуальный референс (открыть в браузере)
```

## Порядок чтения

1. **`10-execution-plan.md`** — общая стратегия и порядок спринтов (читай первым)
2. **`01-context-and-status.md`** — что уже сделано, ничего не дублируй
3. **`02-codebase-cleanup.md`** — спринт 01 (1–2 дня) — терминология и хардкод
4. **`03-design-tokens.md`** — спринт 01 (одновременно) — токены
5. **`04-motion-system.md`** — спринт 04
6. **`05-component-additions.md`** — спринт 02–03
7. **`06-screen-redesigns.md`** + **`07-onboarding-improvements.md`** — спринт 03
8. **`08-copy-glossary.md`** — лежит рядом, сверяйся при любых изменениях текста
9. **`09-acceptance-criteria.md`** — после каждого спринта прогоняй чек-лист

---

## Ключевые принципы (не нарушать)

1. **Brand = Stencil/Mono.** Signal `#FF6A3D`, Ink `#15161A`, Sand `#F3F1EC`. IBM Plex Mono 700 uppercase для display, JetBrains Mono для eyebrow/meta, IBM Plex Sans для body. Без gradient-text на signal, без glass-morphism, без Inter.
2. **Аналитик ≠ разработчик.** В видимом UI нет слов «MCP», «channel», «endpoint», «tool_call», «BSL» — это работа LLM. Технические детали — только в expert-блоках (collapsible).
3. **Light-тему уважаем.** Все цвета через CSS-переменные. Хардкод-цвета Tailwind (`text-red-*`, `bg-green-*`, `text-purple-*`) — запрещены. См. остаточный список в `02-codebase-cleanup.md`.
4. **Один EmptyState на всё приложение.** Не плодить локальные дубли.
5. **Motion уважает `prefers-reduced-motion: reduce`.** Любая анимация дольше 500ms респектит этот медиа-запрос.
6. **Доступность.** Focus-ring 2px + offset, hit-area ≥ 32px на icon-buttons, `aria-label` обязательно для иконочных кнопок.

---

## Текущий стек (locked)

- **Frontend:** Next.js 15 App Router, React 19, shadcn/ui, Tailwind v4
- **Шрифты:** `IBM Plex Sans`, `IBM Plex Mono`, `JetBrains Mono` — подключены в `frontend/app/layout.tsx` через `next/font/google`
- **State:** Zustand (`useSessionsStore`), localStorage для API-ключей и preferences
- **Стили:** CSS-переменные в `frontend/styles/design-tokens.css` + Tailwind arbitrary-values (`bg-[var(--bg-1)]`). Tailwind config v3-формата сейчас не работает с v4-импортом — обходимся arbitrary, см. H-5 в `02-codebase-cleanup.md`.

## Контакт-точки в коде (где что лежит)

| Что | Файл |
|---|---|
| Токены | `frontend/styles/design-tokens.css` |
| Globals (animations, scrollbar) | `frontend/app/globals.css` |
| Bootstrap (шрифты + theme) | `frontend/app/layout.tsx` |
| Shell | `frontend/components/shell/{Header,Sidebar,AppShell,ChannelSelector,BrandMark,StencilLockup}.tsx` |
| Chat | `frontend/components/chat/{Thread,Input,AssistantMessage,StreamingStages,StreamingIndicator,ToolTrace,Markdown}.tsx` |
| Cards | `frontend/components/cards/{TableCard,LogCard,ObjectCard,MetricCard,ChartCard,CodeCard,ReferencesCard}.tsx` |
| Settings | `frontend/components/settings/{LLMConfigForm,MCPConnectionForm,MCPConnectionList,LocalDataSection}.tsx` |
| Onboarding | `frontend/components/onboarding/{OnboardingDialog,StepIndicator}.tsx` |
| UI primitives | `frontend/components/ui/{button,badge,input,select,dropdown-menu,EmptyState,StencilChip,Marker,SectionHead,StatusDot,toast}.tsx` |
| Brand reference | `.brand/BRAND.md`, `.brand/source/stencil-v2.html` |

Поехали.
