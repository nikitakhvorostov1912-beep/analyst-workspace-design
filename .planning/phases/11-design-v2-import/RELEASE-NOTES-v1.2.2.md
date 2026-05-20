# Release v1.2.2 — Stencil/Mono brand redesign

**Дата:** 2026-05-20
**Артефакт:** `desktop/dist/analyst-setup-v1.2.2.exe` · 106.3 MB
**Тэг:** `v1.2.2`

## Что внутри (одно предложение на пункт)

- Расширил Stencil-brand на весь shell — chips, eyebrow «БАЗА 1С», group headers `СЕГОДНЯ ─── 03`, signal-marker в active session, brand-tick на composer.
- Добавил полноценную светлую тему **Sand** (`<html data-theme="light">`) с переключателем Sun/Moon в шапке, выбор сохраняется на устройстве.
- Поднял бренд из лого-зоны в общесистемные tokens: новые `--bg-4`, `--code-bg`, `--accent-32`, `--success-40`, `--warning-40`, `--error-40`; semantic пере-окрашен (success → mint `#7cf0c4`, warning → warm `#f7c948`).
- Создал три новых primitive в `components/ui/`: **`StencilChip`** (6 тонов), **`Marker`**, **`SectionHead`** — теперь любые pill / badge / status-метки идут через системный chip.
- Добавил отдельный маршрут `/guide` — полное руководство аналитика (9 разделов, sticky TOC, brand-стилизованные ToolCard для 10 MCP-инструментов, 6 сценариев работы).
- Зафиксировал brand как source-of-truth в репозитории — `.brand/BRAND.md` + `.brand/source/redesign-v2/` (8 JSX reference-файлов + HTML-стенд от пользователя).

## Что под капотом

### Tokens (`design-tokens.css`)

| Что | Было | Стало |
|---|---|---|
| `--accent` | `#3b82f6` blue | `#ff6a3d` signal orange |
| success | `#4ade80` | `#7cf0c4` mint |
| warning | `#fbbf24` | `#f7c948` warm |
| Light `--bg-1` | `#ebe8e0` | `#faf8f3` почти белый sand |
| `--bg-4` | — | `#262626` dark / `#cfcabd` light |
| `--code-bg` | — | `#0d0e11` (фирменный code ground) |
| `--accent-32`, `--success-40`, `--warning-40`, `--error-40` | — | новые для chip borders |
| `--lockup-slash/version/subtitle` | хардкод | переменные, темо-зависимы |

### Shell

| Компонент | Изменение |
|---|---|
| `Header` | Plex Mono lockup, BookOpen иконка `/guide` рядом с About, Sun/Moon переключатель темы |
| `AnonymizationToggle` | StencilChip warn/muted, «АНОНИМ · ВКЛ/ВЫКЛ» |
| `ModelBadge` | StencilChip muted + StatusDot, модель UPPERCASE («MIMO V2.5 PRO») |
| `ChannelSelector` | eyebrow «БАЗА 1С» (Database icon) + название Plex Mono 600 + KindBadge + порт + dot + chevron |
| Search button | mono uppercase «SEARCH ⌘K» с kbd-капсулой |
| `Sidebar` | «Новый чат» с Marker + Plex Mono uppercase |
| Session group | `СЕГОДНЯ ──────── 03` (label + полоса + счётчик, JetBrains Mono ls .22em) |
| `SessionItem` | brand-eyebrow `#A4F2 · 12 СООБЩ. · 14:32`, active = absolute signal-bar 2×16 px |
| `ChatInput` (composer) | оранжевый brand-tick 22×2 сверху-слева, send signal-фон при value, hint mono + token-counter |

### Routes

- `/` — welcome + chat (Stencil-стилизация)
- `/sessions/[id]` — полноценный чат с brand-composer
- `/guide` — **новый**, 9 разделов с TOC
- `/about` — добавлен CTA-блок в `/guide`
- `/settings` — токены автоматически обновились
- `/status` — токены автоматически обновились

## Quality gate (перед сборкой)

- **vitest 300/300** ✓ (2 теста SessionList адаптированы под brand-pattern; `AnonymizationToggle` тесты прошли благодаря `aria-pressed` в `StencilChip`)
- **next build clean** — 5 routes, без ошибок типов
- **HTTP smoke** `localhost:3010` — все страницы → 200
- **CSS tokens** в `layout.css` подтверждены через grep
- **Visual smoke в Chrome** — все 5 экранов проверены через Chrome MCP, обе темы работают

## Бренд как source-of-truth

`.brand/BRAND.md` обновлён секцией v1.2.x Stencil/Mono Redesign. Полные исходники в `.brand/source/redesign-v2/`:

- `src/tokens.jsx` — палитра + `pal(theme)` helper
- `src/primitives.jsx` — StChip, StMarker, StLockup, StGlyph, StSectionHead, StDot, StButton, StIconBtn, Icon set
- `src/shell.jsx` — Header, Sidebar, ChannelSelector, Composer reference
- `src/cards.jsx` — Table, Object, Log, Metric, References, Code, Chart reference
- `src/dialog-screens.jsx` — Settings, About, Status, Guide экраны
- `src/intro.jsx` — Splash / Onboarding
- `Stencil-Redesign-Full.html` — собранный демо-стенд

`memory/feedback_analyst_stencil_mono_redesign.md` фиксирует решение в долговременной памяти.

## Что НЕ вошло в v1.2.2 (backlog для v1.2.3+)

Намеренно ограничился shell-слоем чтобы не сломать всё разом. Карточки в чате работают на token-уровне (получили новую палитру автоматически), но **visual treatment** карточек по паттерну из `cards.jsx` (KIND-chip + meta-row `TABLE · 847 строк · 124 мс`) — следующая итерация:

- TableCard / ObjectCard / LogCard / MetricCard / ReferencesCard / CodeCard / ChartCard под brand pattern из reference
- Settings — leg-сегменты и mono inputs из `dialog-screens.jsx`
- Splash / Onboarding — hero-экран из `intro.jsx`
- Decorative slash-chips в composer (`/ ОТЧЁТ / JOURNAL / EXPLAIN @ ОБЪЕКТ`) — статичные из reference vs наш динамический SlashPopover

## Артефакт сборки

```
desktop/dist/analyst-setup-v1.2.2.exe         106.3 MB
desktop/dist/analyst-setup-v1.2.2.exe.blockmap
```

Компоненты:
- backend.exe (PyInstaller, FastAPI) — 14.7 MB
- frontend (Next.js standalone) — 61 MB
- Electron 33.4.11 runtime — основной объём

## Установка / запуск

1. Скачать `analyst-setup-v1.2.2.exe`.
2. Запустить установщик. Установка per-user (без admin).
3. Из меню Пуск или ярлыка — «1С Аналитик».
4. При первом запуске — мастер настройки (подключение к 1С + LLM ключ).

## Чек-лист smoke после релиза

- [ ] Установить v1.2.2 на чистую машину
- [ ] Открыть — увидеть Stencil glyph + lockup в шапке
- [ ] Переключить тему (Sun/Moon) — Sand палитра применилась
- [ ] Открыть `/guide` — все 9 разделов видны, TOC работает
- [ ] Создать тестовое подключение и задать вопрос — карточки рендерятся
