# Phase 8: STACK Integration — Context

**Gathered:** 2026-05-18
**Status:** Ready for planning
**Source:** MSG #10 verbatim, см. `.claude/memory/requirements-stack-sessions-learn.md`

<domain>
## Phase Boundary

**Что делает эта фаза:**
Подцепляет релевантные глобальные ресурсы Claude Code (skills, rules) к проекту `analyst-workspace-design` так, чтобы будущие Claude-сессии в проекте имели **точечный** контекст. Этот проект — UI чата над MCP, ему НЕ нужны 100+ 1С-метаданных скиллов (cf-init, epf-build, skd-compile итд).

**Outcome:**
1. Открываю проект в Claude Code → локальный `.claude/CLAUDE.md` подгружается автоматически (lazy-load по filename pattern)
2. Вижу: проектные скиллы (`awd-dev-up`, `awd-quality-gate`, `awd-claude-design-handoff`) + ссылки на 5 релевантных глобальных + жёсткий ban на работу в `analyst-tools-1c`
3. `/awd-dev-up` поднимает backend + frontend одной командой с verify
4. `/awd-quality-gate` гоняет pytest+vitest+playwright+build → PASS/FAIL
5. «Продолжай» → читает `.planning/STATE.md` + последний `PHASE-summary.md`

**Что НЕ доставляется:**
- Изменение глобальных скиллов в `~/.claude/skills\` или `C:\CLOUDE_PR\.claude\skills\` — read-only
- Подключение всех 100+ глобальных 1С-метаданных скиллов — НЕ применимо
- Hooks (post-bsl-edit) — глобальные, не дублировать
- Изменение `.mcp.json` registrations — глобально
</domain>

<decisions>
## Implementation Decisions

### Шорт-лист глобальных скиллов (Claude's discretion — 5 шт.)

| Skill | Path | Когда вызывать |
|---|---|---|
| `claude-design` | `~/.claude/skills/claude-design/` | UI-итерации через claude.ai/design |
| `playwright-test` | `~/.claude/skills/playwright-test/` | E2E тесты frontend |
| `reflect` | `~/.claude/skills/reflect/` | разбор полётов после фейлов |
| `weekly-improve` | `~/.claude/skills/weekly-improve/` | аудит наработок раз в неделю |
| `inspect` | `~/.claude/skills/inspect/` | аудит кода / архитектуры |

**Исключены (НЕ применимы — 1С-метаданные / EPF-инструменты):**
cf-*, epf-*, erf-*, skd-*, role-*, form-*, meta-*, mxl-*, subsystem-*, template-*, cfe-*, db-* (1C), web-* (Apache), interface-*, help-add, img-grid, 1c-* (методики), erp-configuration-advisor, gap-analysis, kafka-1c-adapter, bsp-patterns, requirements-list, to-be-optimization, write-1c-skill, role-expert, subsystem-expert, epf-expert, erf-expert, mxl-expert.

### Локальный CLAUDE.md (`.claude/CLAUDE.md`)

Структура:
1. **Wrong-project guard** (жирно, первый блок): ban на работу вне `analyst-workspace-design/`
2. **Концепция «чат во главе»** (extract из корневого CLAUDE.md)
3. **Стек кратко** (Next 15 + FastAPI + Electron) с ссылкой на корневой
4. **Проектные скиллы** — таблица 3 шт. с triggers
5. **Релевантные глобальные** — таблица 5 шт. (см. выше)
6. **Memory lazy-load карта** — аналог `knowledge-router.md`
7. **Workflow «Продолжай»** — `STATE.md` → последний `PHASE-summary.md`
8. **Запреты** — extract bans (no 8 экранов, Inter, glass morphism, etc.)
9. **Брутальная честность** — обязательно

### `.claude/rules/` (3 файла — extract из корневого CLAUDE.md)
- `design-bans.md` — все «❌ ...» из секции «Что НЕ делаем»
- `tech-stack.md` — стек таблица + версии
- `session-contract.md` — workflow Продолжай, MCP-is-everything, brutal honesty

### Проектные скиллы (`.claude/skills/`)

#### awd-dev-up
- `SKILL.md` — описание + триггеры («подними сервера», «запусти dev», «start»)
- `scripts/up.ps1` — PowerShell:
  1. `Stop-Process` процессов на :3010 и :8010 (если есть)
  2. `Start-Process` uvicorn `app.main:app --reload --port 8010` в `backend/` через venv
  3. `Start-Process` `npx next dev -p 3010` в `frontend/`
  4. Polling :8010/health + :3010 до Ready (timeout 60 сек)
  5. Verify: `<title>1С Аналитик</title>` в HTML ответа :3010
- Exit code 0 = оба сервера готовы

#### awd-quality-gate
- `SKILL.md` — описание + триггер («проверь качество», «quality gate», «перед коммитом»)
- `scripts/gate.ps1` — последовательно (НЕ fail-fast):
  1. `pytest backend/tests` (timeout 120s) — backend tests
  2. `pnpm --filter ./frontend vitest run` — frontend unit
  3. `pnpm --filter ./frontend build` — production build
  4. `pnpm --filter ./frontend playwright test --reporter=line` — E2E
- Output: 4 строки `[PASS|FAIL] <step>` + общий вердикт
- Exit code 0 если все PASS

#### awd-claude-design-handoff
- `SKILL.md` — описание + триггер («хочу итерировать дизайн», «claude design», «итерация UI»)
- `scripts/bundle.ps1` — собирает context bundle в `temp/design-bundle-<timestamp>/`:
  - копирует `CLAUDE.md`, `PROJECT.md`, `REQUIREMENTS.md`
  - копирует `.claude/memory/design-constraints.md`
  - снимает скриншоты через Playwright headed: главная, OnboardingDialog, Settings → сохраняет в `screenshots/`
  - генерирует `PROMPT.md` — готовый шаблон для claude.ai/design (с verbatim ban-list)
- Output: путь к папке. Пользователь сам открывает claude.ai/design, drag-and-drop папку.
</decisions>

<canonical_refs>
## Canonical References

### Project
- `CLAUDE.md` (root)
- `PROJECT.md`, `ARCHITECTURE.md`, `REQUIREMENTS.md`
- `ROADMAP.md` — Phase 8 секция (полная)
- `.claude/memory/` — 7 файлов

### Global (READ-ONLY refs)
- `C:\CLOUDE_PR\.claude\rules\knowledge-router.md` — пример lazy-load карты
- `~/.claude/skills/claude-design/SKILL.md` — пример проектного скилла
- `C:\CLOUDE_PR\.claude\rules\1c\1c-rules.md` — пример rules split

### External
- Claude Code skill format: <https://docs.claude.com/en/docs/claude-code/skills>
- Next CLI: <https://nextjs.org/docs/app/api-reference/cli/next>
</canonical_refs>

<specifics>
## Specifics

### Lazy-load карта в локальном CLAUDE.md

```markdown
## Маршруты памяти проекта

| Триггер / тема | Файл |
|---|---|
| Старт «Продолжай» | `.planning/STATE.md` + последний `PHASE-summary.md` |
| LLM-провайдеры, Multi-LLM | `.claude/memory/llm-providers.md` |
| Distribution / Electron | `.claude/memory/distribution.md` |
| Design-итерации, UI | `.claude/memory/design-constraints.md` |
| Какую фазу делать | `.planning/ROADMAP.md` |
| Open questions / неопределённости | `.claude/memory/open-questions.md` |
| История pivots v0/v0b/v1 | `.claude/memory/pivot-history.md` |
| STACK/SESSIONS/LEARN требования | `.claude/memory/requirements-stack-sessions-learn.md` |
```

### Workflow «Продолжай» в локальном CLAUDE.md

```markdown
## При запросе «Продолжай» или старте сессии без явной задачи

1. Read `.planning/STATE.md` → текущая `milestone`, `phase`, `progress`
2. Read последний завершённый или активный `.planning/phases/*/PHASE-summary.md`
3. Если active phase имеет `<N>-CONTEXT.md` — Read его
4. Озвучить пользователю в ОДНОМ сообщении: на чём остановились + что следующее по roadmap + 2-3 опции что делать
5. Ждать команды. НЕ начинать работу автономно.
```

### Caveat: скиллы — не симлинки

Symlinks на Windows без admin падают. Локальный CLAUDE.md — просто текстовая ссылка `~/.claude/skills/<name>/`. Claude Code сам подгружает глобальные при slash-командах.

### Caveat: prefix `awd-` для проектных скиллов

Чтобы не конфликтовать с глобальными названиями. `awd` = analyst-workspace-design.

### Caveat: bundle.ps1 для Claude Design

Сборка screenshot'ов через Playwright headed требует чтобы серверы были подняты. Скрипт сначала вызывает `awd-dev-up` если :3010 не отвечает.
</specifics>

<deferred>
## Deferred (НЕ в Phase 8)

- Hooks (post-edit, pre-commit) — глобальные, не локальные
- MCP server конфиги — глобально через `.mcp.json`
- CI/CD интеграция скиллов — Phase 11+
- Подключение `claude-design-workflow.md` rule — отдельный rule import
- Per-skill telemetry / usage counter — Out of MVP
</deferred>

---
*Phase: 08-stack-integration*
*Context gathered: 2026-05-18 — yolo mode, defaults applied (5-skill shortlist + 3 project skills)*
