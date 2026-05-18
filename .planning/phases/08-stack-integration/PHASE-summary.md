# Phase 8 — STACK Integration: Summary

**Status:** COMPLETE (auto verification PASS, manual smoke deferred — требует fresh Claude session)
**Branch:** `feature/m5-design-v2-import`
**Date:** 2026-05-18
**Effort:** ~45 мин engineering + 15 мин documentation

---

## Goal achieved

Создана инфраструктура проектных скиллов + правил + локальный `.claude/CLAUDE.md` routing с wrong-project guard. Это разблокирует:
- Защиту от lost context при работе в parallel projects (analyst-tools-1c уже удалён, но папка может всплыть в индексах)
- Быстрые операции через slash commands (`/awd-dev-up`, `/awd-quality-gate`, `/awd-claude-design-handoff`)
- Lazy-load memory map для эффективного использования context window

---

## What was built

### `.claude/skills/` — 3 проектных скилла

1. **awd-dev-up** (`SKILL.md` + `scripts/up.ps1`)
   - Останавливает существующие процессы на :8010 / :3010
   - Стартует backend uvicorn (через `.venv/Scripts/python.exe`) + frontend `npx next dev -p 3010`
   - Polling 60s до Ready через `/health` 200 + HTML с `<title>`
   - Exit 0 если оба сервера живы, exit 1 если timeout

2. **awd-quality-gate** (`SKILL.md` + `scripts/gate.ps1`)
   - 4 независимых шага (НЕ fail-fast): pytest + vitest + pnpm build + playwright
   - Structured output: 4 строки `[PASS/FAIL]` + overall verdict
   - Exit 0 если все PASS, exit 1 если хотя бы один FAIL

3. **awd-claude-design-handoff** (`SKILL.md` + `scripts/bundle.ps1`)
   - Verify серверы (auto `awd-dev-up` if needed)
   - Создаёт `temp/design-bundle-<timestamp>/` с CLAUDE.md + PROJECT.md + REQUIREMENTS.md + design-constraints.md
   - Playwright headless screenshots: `/`, `/settings`, `/status` @ 1440×900
   - Генерирует PROMPT.md с verbatim ban-list + палитрой + референсами

### `.claude/rules/` — 3 файла правил

1. **design-bans.md** — verbatim запреты из CLAUDE.md (v0/v0b mistakes + fonts + dimensions + темы) + Phase 11 v1.2.0 design changes + «что МОЖНО» positive constraints
2. **tech-stack.md** — locked versions table (Next 15 + React 19 + Tailwind 4 + FastAPI + Pydantic 2 + Electron 33 + PyInstaller 6 + sqlite-vec TBD) + «что НЕ используем» anti-list
3. **session-contract.md** — брутальная честность + MCP-only workflow + «Продолжай» / «иди до конца» workflows + wrong-project guard + 3-iterations rule

### `.claude/CLAUDE.md` — project-local routing

- **Wrong-project guard FIRST block** — explicit list of forbidden paths (analyst-tools-1c, voice-agent-1c, ai-ecosystem-1c)
- Концепция verbatim из root CLAUDE.md
- 3 проектных скилла (с triggers) + 5 глобальных RW-only references
- Anti-list of 25+ 1С-metadata skills NOT applicable to this project
- Lazy-load memory map: 10 triggers → 10 files
- «Продолжай» / «иди до конца» workflow definition
- Current snapshot: M5 / Phase 11 / v1.1.0 released / v1.2.0 pending

---

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| 3 проектных скилла со SKILL.md + scripts | ✅ done |
| 3 rules файла в `.claude/rules/` | ✅ done |
| Локальный `.claude/CLAUDE.md` с wrong-project guard первым блоком | ✅ done |
| Smoke: новая Claude-сессия «Продолжай» → читает STATE.md | ⏸ deferred — требует fresh Claude session |
| Smoke: «подними сервера» → вызывает `/awd-dev-up` | ⏸ deferred |
| Smoke: skill manifest validation (YAML frontmatter, PS1 paths) | ✅ via visual inspection |

**Coverage: 4/6 done, 2 deferred (smoke validation requires manual fresh Claude session).**

---

## Files created (12 total)

```
.claude/
├── CLAUDE.md                                            (project routing)
├── skills/
│   ├── awd-dev-up/
│   │   ├── SKILL.md
│   │   └── scripts/up.ps1
│   ├── awd-quality-gate/
│   │   ├── SKILL.md
│   │   └── scripts/gate.ps1
│   └── awd-claude-design-handoff/
│       ├── SKILL.md
│       └── scripts/bundle.ps1
└── rules/
    ├── design-bans.md
    ├── tech-stack.md
    └── session-contract.md

.planning/phases/08-stack-integration/
└── SMOKE.md  (deferred test cases)
```

---

## Commits

- `e10c27b` feat(claude): Phase 8 STACK Integration — project skills + rules + CLAUDE.md routing

**1 atomic commit, 12 files created.**

---

## Phase 8 unblocks

- **Future sessions** — Claude автоматически читает `.claude/CLAUDE.md` при работе в проекте, защищён от wrong-project context errors
- **`/awd-dev-up`** — однострочный запуск dev environment (used by Phase 11 manual smoke checklist)
- **`/awd-quality-gate`** — pre-commit / pre-release validation (used by future Phase 9/10 tests)
- **`/awd-claude-design-handoff`** — repeatable workflow для итераций UI через claude.ai/design

---

## Lessons learned

1. **PowerShell .ps1 портабельность** — `Get-Command npx.cmd` лучше чем `npx` для Windows (нужен .cmd extension для Process.Start)
2. **Path resolution через `Resolve-Path $PSScriptRoot\..\..\..\..`** — 4 уровня вверх от `.claude/skills/<name>/scripts/` до root проекта
3. **Lazy-load memory более ценен чем eager-load** — 10 файлов памяти загружаются только по триггеру, экономия context window
4. **Wrong-project guard в первом блоке** — Claude видит запрет раньше любой другой инструкции, снижает риск
