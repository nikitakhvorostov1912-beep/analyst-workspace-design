---
name: awd-claude-design-handoff
description: Собрать context bundle для claude.ai/design — скриншоты + ban-list + промпт-шаблон
---

# /awd-claude-design-handoff

Готовит handoff bundle для итерации UI через claude.ai/design в браузере пользователя.

## Когда вызывать

- «хочу итерировать дизайн через claude design»
- «обнови UI», «новый дизайн страницы X»
- Пользователь сам говорит про claude.ai/design

## Что делает

1. Проверяет что сервера запущены (если нет — вызывает `awd-dev-up`)
2. Создаёт `temp/design-bundle-<timestamp>/`
3. Копирует контекст: `CLAUDE.md`, `PROJECT.md`, `REQUIREMENTS.md`, `.claude/memory/design-constraints.md`
4. Снимает скриншоты через Playwright headed (1440×900):
   - `/` (Onboarding или Thread)
   - `/settings`
   - `/status`
5. Генерирует `PROMPT.md` — шаблон для claude.ai/design с ban-list verbatim

## После генерации

Пользователь:
1. Открывает `claude.ai/design` в своём браузере
2. Drag-and-drop папку `temp/design-bundle-<ts>/`
3. Копирует промпт из `PROMPT.md` в чат Claude Design
4. Итерирует визуал
5. Export ZIP → импорт обратно через ручной разбор (Phase 11 workflow)

## Запуск

```powershell
pwsh .claude/skills/awd-claude-design-handoff/scripts/bundle.ps1
```

## Caveat

- Первый запуск Playwright качает Chromium (~200 MB)
- Если backend не отвечает — скриншоты будут «Backend недоступен» (то что увидит юзер в реале)
