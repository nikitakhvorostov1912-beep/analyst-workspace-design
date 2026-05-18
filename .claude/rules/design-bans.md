# Design Bans (verbatim из CLAUDE.md)

## Из-за провальных итераций v0/v0b

- ❌ «Work-modes» Discovery/Triage/Investigate/Mapping/Knowledge
- ❌ Object-centric IDE с tree метаданных слева
- ❌ Workflow editor с карточками MCP-операций
- ❌ AI right-rail с «инсайтами» / «магическими» подсказками

## Из общей дизайн-философии

- ❌ Inter font, purple-cyan gradients, glass morphism, decorative emoji
- ❌ Mobile-first вёрстка (desktop only, ≥ 1280px)
- ❌ Светлая тема как опция

## Из обратной связи 2026-05-13/17

- ❌ 8 экранов wizard в концепциях (max 4 — текущий Onboarding)
- ❌ Накидывание 6+ LLM провайдеров в UI верхнего уровня (один активный + Settings)
- ❌ PII shield / RAG / Memory tool как обязательные первые экраны (опт-ин в Step 3 Onboarding)

## v1.2.0 design changes (Phase 11)

- Accent: тёмно-синий `#3b82f6` (blue-500), не оранжевый
- Variants: blue (default), clinical, indigo, orange (legacy fallback)
- Granular tokens: --bg-0..3, --fg-1..4, --bd-1..3
- 7 keyframes в design-tokens.css

## Что МОЖНО (positive constraints)

- ✅ Chat-first layout (одна центральная панель)
- ✅ Inline cards в потоке сообщений (6 типов: table/object/log/metric/references/code)
- ✅ Collapsible tool trace (по умолчанию свёрнут)
- ✅ Channel selector в Header (multi-tenant)
- ✅ Anonymization toggle (amber pill когда ВКЛ)
- ✅ Streaming stages с иконками + переходами
- ✅ animate-fade-up / scale-in / blink / status-pulse (см. design-tokens.css)
