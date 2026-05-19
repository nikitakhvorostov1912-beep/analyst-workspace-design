# Design Bans (verbatim из CLAUDE.md)

## Из-за провальных итераций v0/v0b

- ❌ «Work-modes» Discovery/Triage/Investigate/Mapping/Knowledge
- ❌ Object-centric IDE с tree метаданных слева
- ❌ Workflow editor с карточками MCP-операций
- ❌ AI right-rail с «инсайтами» / «магическими» подсказками

## Из общей дизайн-философии

- ❌ Inter font, purple-cyan gradients, glass morphism, decorative emoji
- ❌ Mobile-first вёрстка (desktop only, ≥ 1280px)
- ~~❌ Светлая тема как опция~~ → **СНЯТО 2026-05-19**: brand Stencil содержит обе темы.
  Dark — default, Light (Sand) — опция через `<html data-theme="light">`.

## Из обратной связи 2026-05-13/17

- ❌ 8 экранов wizard в концепциях (max 4 — текущий Onboarding)
- ❌ Накидывание 6+ LLM провайдеров в UI верхнего уровня (один активный + Settings)
- ❌ PII shield / RAG / Memory tool как обязательные первые экраны (опт-ин в Step 3 Onboarding)

## ~~v1.2.0 design changes (Phase 11)~~ — ОТМЕНЕНО 2026-05-19

- ~~Accent: тёмно-синий `#3b82f6` (blue-500), не оранжевый~~
- ~~Variants: blue (default), clinical, indigo, orange (legacy fallback)~~
- ✅ Granular tokens: --bg-0..3, --fg-1..4, --bd-1..3 (сохраняются)
- ✅ 7 keyframes в design-tokens.css (сохраняются)

## v1.2.x brand Stencil/Mono (2026-05-19) — АКТУАЛЬНОЕ

Source-of-truth: `.brand/BRAND.md` + `.brand/source/stencil-v2.html`.

- **Accent**: Signal `#FF6A3D` (orange) — единственный, без вариантов
- **Шрифт лого**: IBM Plex Mono **700** uppercase (не Inter, не Plex Sans)
- **Служебный моно**: JetBrains Mono (subtitle, meta, eyebrow)
- **Палитра brand**: Signal · Tint #FFB38A · Ink #15161A · Sand #F3F1EC
- **Темы**: Dark (Ink) default + Light (Sand) опция через `data-theme`
- **Лого-замок**: `[orange bar] АНАЛИТИК / 1.2.1` + subtitle JetBrains Mono
- **Glyph**: тёмный squircle 18% + белая «А» Plex Mono 700 + signal marker top-left
- Design-tokens: `--brand-signal/tint/deep/ink/sand`, `--lockup-slash/version/subtitle`

Запреты brand:
- ❌ Подменять Signal на blue/purple/legacy-orange `#f97316`
- ❌ Менять Plex Mono → Inter/Roboto в лого-зоне
- ❌ Sparkles, gradient-text, glow, shadow на буквах
- ❌ Lowercase «Аналитик» в лого (только UPPERCASE)
- ❌ Создавать новые glyph-варианты сверх «squircle + А»

## Что МОЖНО (positive constraints)

- ✅ Chat-first layout (одна центральная панель)
- ✅ Inline cards в потоке сообщений (6 типов: table/object/log/metric/references/code)
- ✅ Collapsible tool trace (по умолчанию свёрнут)
- ✅ Channel selector в Header (multi-tenant)
- ✅ Anonymization toggle (amber pill когда ВКЛ)
- ✅ Streaming stages с иконками + переходами
- ✅ animate-fade-up / scale-in / blink / status-pulse (см. design-tokens.css)
