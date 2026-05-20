# Brand — 1С Аналитик · Stencil/Mono

> Direction 06 · Stencil · Mono (Refined). Утверждено 2026-05-19.
> Source-of-truth для всех визуальных решений приложения.

Эта папка — **зафиксированный фирменный стиль**. При любых сомнениях по
цвету / типографике / лого открой этот файл и `source/stencil-v2.html`
в браузере — там полный лого-лист (8 секций, hero, вариации, конструкция,
размерная лестница, иконки, применения, правила).

## TL;DR — 4 факта

1. **Палитра**: Signal `#FF6A3D` (orange) · Ink `#15161A` (dark) · Sand `#F3F1EC` (cream) · Tint `#FFB38A`.
2. **Шрифт логотипа**: IBM Plex Mono **700** uppercase, letter-spacing +0.02em.
3. **Лого-замок**: `[orange bar 0.52em] АНАЛИТИК / 1.2.1` + subtitle `PRODUCTION · STABLE` (JetBrains Mono).
4. **Glyph (favicon)**: чёрный squircle (radius ~18%) + белая «А» (Plex Mono 700) + оранжевый маркер top-left (size ~14%, offset ~13%).

## Палитра — цветовые токены

| Имя | HEX | Назначение | CSS var |
|---|---|---|---|
| Signal | `#FF6A3D` | Primary accent — кнопки, маркер, focus | `--brand-signal`, `--accent` |
| Tint | `#FFB38A` | Hover state на signal | `--brand-signal-tint` |
| Deep | `#C84A23` | Press state на signal | `--brand-signal-deep` |
| Ink | `#15161A` | Dark текст / dark squircle / dark bg | `--brand-ink`, `--fg-1` (light theme) |
| Sand | `#F3F1EC` | Light bg primary | `--brand-sand`, `--bg-0` (light theme) |
| Sand-2 | `#E7E4DC` | Light bg secondary (surface) | `--brand-sand-2`, `--bg-2` (light theme) |

**Запрещено**: градиенты на signal, gradient-text, glass-morphism, purple/cyan/blue
как primary, любые сторонние оранжевые (#F97316 legacy запрещён).

## Типографика

| Назначение | Шрифт | Вес | Стиль |
|---|---|---|---|
| Лого АНАЛИТИК | IBM Plex Mono | 700 | uppercase, ls +0.02em |
| Версия 1.2.1 | IBM Plex Mono | 500 | mixed, ls +0.02em, opacity 0.55 |
| Slash «/» | IBM Plex Mono | 600 | opacity 0.22 (dark) / 0.28 (light) |
| Subtitle PRODUCTION · STABLE | JetBrains Mono | 500 | uppercase, ls +0.18em, opacity 0.45 |
| Eyebrow / meta | JetBrains Mono | 400 | uppercase, ls +0.2em, ink-dim |
| Заголовки секций H2 | IBM Plex Mono | 600 | uppercase, ls +0.05em |
| Основной UI текст | IBM Plex Sans | 400/500 | — |

## Лого-замок — структура

```
[orange bar 0.52em] АНАЛИТИК [/ slash dim] [1.2.1 dim]
                   PRODUCTION · STABLE
```

Реализация — компонент `frontend/components/shell/StencilLockup.tsx`.

### Размерная лестница

| Контекст | Font-size АНАЛИТИК | Где |
|---|---|---|
| Hero / splash | 48 px | onboarding, about |
| Window header | 24 px | titlebar окна |
| App header | 16–18 px | основной header (наш дефолт = 16) |
| Inline / chip | 12 px | meta-блоки, footer |
| Minimum | 10 px | без версии и slash |

## Glyph (иконка приложения)

```
┌───────────────┐
│ ▪             │   ▪ — оранжевый маркер #FF6A3D
│               │       size 14%, offset 13%
│       А       │   А — белая, IBM Plex Mono 700
│               │       size 47%
└───────────────┘  Фон #15161A (Ink)
                   Squircle radius 18%
```

Реализация — компонент `frontend/components/shell/BrandMark.tsx`.

### Геометрия по размеру

| size | radius | marker | font А |
|---|---|---|---|
| 128 | 20 (15.6%) | 18×18 @ 16,16 | 60 |
| 64 | 12 (18.8%) | 10×10 @ 9,9 | 30 |
| 40 | 7 (18%) | 6×6 @ 5,5 | 19 |
| 32 | 7 (21.9%) | 5×5 @ 5,5 | 15 |
| 16 | 3 (18.8%) | 3×3 @ 2,2 | 8 |

## Темы

### Dark (default) — Ink

- Фон: `#0a0a0a` (`--bg-0`)
- Текст: `#e5e5e5` (`--fg-1`)
- Лого АНАЛИТИК: белый
- Маркер: signal orange
- Slash/version/subtitle: rgba(255,255,255, .22 / .55 / .45)

### Light — Sand

Активируется через `<html data-theme="light">`. Сохраняется в localStorage
ключом `analyst-theme`.

- Фон: `#f3f1ec` (`--bg-0`)
- Текст: `#15161a` (`--fg-1`)
- Лого АНАЛИТИК: ink (тёмный)
- Маркер: signal orange (тот же)
- Slash/version/subtitle: rgba(0,0,0, .28 / .55 / .45)
- Glyph остаётся **тёмным squircle с белой А** — как favicon, иконка
  приложения. Это часть identity, не подстраивается под фон.

### Что НЕ темизуется

- Signal #FF6A3D — primary, не меняется между темами.
- Glyph (BrandMark) — всегда тёмный фон + белая А.
- Print-варианты (mono-black, mono-white) — отдельный кейс, не привязаны к UI-теме.

## Правила DO / DON'T (из лого-листа)

### DO

- Держать ритм и маркер слева
- IBM Plex Mono 700 uppercase для АНАЛИТИК
- Маркер 0.52em квадрат, border-radius 2px
- Минимум 10 px по высоте знака

### DON'T

- ❌ Не менять гарнитуру (никаких Inter / Arial для лого)
- ❌ Без gradient-text
- ❌ Не наклонять / не растягивать / не skew
- ❌ Без эффектов: glow, shadow на буквах, sparkle, glass
- ❌ Не использовать lowercase для АНАЛИТИК
- ❌ Без декоративных emoji рядом с лого

## Source-of-truth файлы

- `source/stencil-v2.html` — официальный лого-лист с CSS и SVG (8 секций)
- `source/stencil-v1.html` — ранняя итерация (для истории)
- `source/uploads/target.png` — мудборд target дизайна
- `source/uploads/before.png` — было до внедрения

## Куда применяется в коде

| Файл | Что в нём |
|---|---|
| `frontend/styles/design-tokens.css` | Все CSS-переменные (`--accent`, `--brand-*`, `--lockup-*`, `[data-theme="light"]`) |
| `frontend/app/layout.tsx` | Подключение шрифтов (Plex Sans/Mono + JetBrains Mono), `data-accent="signal"`, inline-script для применения сохранённой темы до hydration |
| `frontend/components/shell/BrandMark.tsx` | Glyph (squircle + А + маркер) |
| `frontend/components/shell/StencilLockup.tsx` | Inline-замок с текстом |
| `frontend/components/shell/ThemeToggle.tsx` | Переключалка dark ↔ light |
| `frontend/components/shell/Header.tsx` | Использует всё перечисленное |

## История версий бренда

| Дата | Версия | Изменение |
|---|---|---|
| 2026-05-20 | Stencil/Mono Redesign | **Текущий** — расширение Stencil v2 на весь shell: chips, eyebrow, group headers, brand-tick на composer, mint success #7cf0c4, warm warning #f7c948 |
| 2026-05-19 | Stencil v2 | IBM Plex Mono 700 uppercase + orange marker (direction 06) |
| 2026-05-18 | Blue v1.2.0 | Blue `#3b82f6` accent (Phase 11 design v2) — отменён |
| ~2026-05 | Orange legacy | `#f97316` (v1.0–v1.1.x) — отменён |

## v1.2.x Stencil/Mono Redesign (2026-05-20)

Расширение brand на весь интерфейс приложения, не только лого-зону.

### Новые токены

| Токен | Dark | Light | Назначение |
|---|---|---|---|
| `--bg-4` | `#262626` | `#cfcabd` | Strongest step — disabled inputs, send-rest |
| `--code-bg` | `#0d0e11` | `#0d0e11` (same) | Code surface — всегда тёмная независимо от темы |
| `--code-fg` | `#e5e5e5` | same | Текст в code blocks |
| `--accent-32` | `rgba(255,106,61,.32)` | same | Border на signal chips |
| `--success-40` | `rgba(124,240,196,.4)` | `rgba(45,185,140,.4)` | Border на success chips |
| `--warning-40` | `rgba(247,201,72,.4)` | `rgba(198,147,20,.4)` | Border на warn chips |
| `--error-40` | `rgba(248,113,113,.4)` | `rgba(220,38,38,.4)` | Border на error chips |

### Обновлённая семантика

- **Success**: `#7cf0c4` (мятный) — было `#4ade80`. Brand-friendly соседствует с signal.
- **Warning**: `#f7c948` (тёплая охра) — было `#fbbf24`. Согласован с sand-палитрой.
- **Light bg-1**: `#faf8f3` (почти белый sand) — было `#ebe8e0`. Для карточек/header нужен сильный контраст с основным sand-фоном.

### Новые primitives (`components/ui/`)

- **`StencilChip`** — фирменная капсула с 6 тонами: muted, signal, success, warn, error, solid. Шрифт — JetBrains Mono uppercase ls .16em.
- **`Marker`** — оранжевый квадрат-якорь (по умолчанию 10×10, signal-цвет, border-radius 2). Ставится перед лого, разделами, кнопкой «Новый чат».
- **`SectionHead`** — паттерн `01 · TITLE ──────── tag` для крупных секций.

### Изменённые компоненты shell

- **AnonymizationToggle** → StencilChip tone=warn/muted. «Аноним · ВКЛ» / «Аноним · ВЫКЛ».
- **ModelBadge** → StencilChip tone=muted с success-dot. Модель показывается uppercase: «MIMO-V2.5-PRO», «GPT-4O».
- **Search button в Header** → mono uppercase «SEARCH ⌘K».
- **ChannelSelector** → eyebrow «БАЗА 1С» (Database icon в signal-цвете) + название Plex Mono 600 + статус-dot + chevron. Empty state — пунктирный warn-frame с уточнением «Настроить →».
- **Sidebar** → группы дней с паттерном `СЕГОДНЯ ────── 03` (количество тонкой полосой + счётчик). Кнопка «Новый чат» с Marker слева.
- **SessionItem** → brand-eyebrow `#A4F2 · 12 сооб. · 14:32`. Активная строка — signal-bar слева 2×16 px.
- **ChatInput (composer)** → оранжевый brand-tick 22×2 сверху-слева, send button signal-фон при value, hint-row mono uppercase + token-counter справа.

### Source-of-truth файлы (redesign-v2)

- `.brand/source/redesign-v2/src/tokens.jsx` — полная палитра + `pal(theme)` helper
- `.brand/source/redesign-v2/src/primitives.jsx` — StChip, StMarker, StLockup, StGlyph, StSectionHead, StDot, StButton, StIconBtn, Icon set
- `.brand/source/redesign-v2/src/shell.jsx` — Header, Sidebar, ChannelSelector, Composer reference
- `.brand/source/redesign-v2/src/cards.jsx` — Table, Object, Log, Metric, References, Code, Chart reference
- `.brand/source/redesign-v2/src/dialog-screens.jsx` — Settings, About, Status, Guide экраны
- `.brand/source/redesign-v2/src/intro.jsx` — Splash / Onboarding
- `.brand/source/redesign-v2/Stencil-Redesign-Full.html` — собранный демо-стенд
