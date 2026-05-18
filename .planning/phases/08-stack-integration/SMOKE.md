# Phase 8 — SMOKE Verification

**Status:** DEFERRED to fresh Claude session
**Reason:** Smoke validates project-local CLAUDE.md auto-load + skill invocation triggers — requires fresh Claude Code session start (не тот процесс что записал файлы).

---

## Что Phase 8 написала

✅ **6 файлов в `.claude/skills/`** — 3 проектных скилла:
- `awd-dev-up/SKILL.md` + `scripts/up.ps1`
- `awd-quality-gate/SKILL.md` + `scripts/gate.ps1`
- `awd-claude-design-handoff/SKILL.md` + `scripts/bundle.ps1`

✅ **3 файла в `.claude/rules/`** — извлечённые правила:
- `design-bans.md` — verbatim запреты
- `tech-stack.md` — locked версии
- `session-contract.md` — брутальная честность + workflow «Продолжай»

✅ **`.claude/CLAUDE.md`** — project-local routing:
- Wrong-project guard (`analyst-tools-1c` ban)
- Lazy-load карта памяти (10 триггеров → 10 файлов)
- Скиллы инвентарь (3 проектных + 5 глобальных RW-only + 25+ NA для 1С-проектов)
- Текущий snapshot (Phase 11 progress)

---

## Что должна проверить SMOKE

### Test 1: wrong-project guard срабатывает

**Шаги:**
1. Запустить новую Claude Code сессию в `C:\CLOUDE_PR\projects\analyst-workspace-design\`
2. Ввести: «Покажи структуру analyst-tools-1c»
3. **Ожидаемое:** Claude переспрашивает / отказывается / упоминает что это удалённый v0 проект

**Текущий статус:** ⏸ не проверено

### Test 2: «Продолжай» читает STATE.md

**Шаги:**
1. Запустить новую Claude Code сессию
2. Ввести: «Продолжай»
3. **Ожидаемое:** Claude читает `.planning/STATE.md`, упоминает Phase 11 (in_progress) или v1.2.0 pending, не лезет в чужие проекты

**Текущий статус:** ⏸ не проверено

### Test 3: `/awd-dev-up` запускается

**Шаги:**
1. Ввести: «подними сервера»
2. **Ожидаемое:** Claude вызывает PowerShell скрипт `awd-dev-up/scripts/up.ps1`, серверы поднимаются за < 60 сек
3. Verify: `Invoke-WebRequest http://127.0.0.1:8010/health` возвращает `{"status":"ok"}`
4. Verify: `Invoke-WebRequest http://localhost:3010` возвращает HTML с `<title>`

**Текущий статус:** ⏸ не проверено (требует pwsh + python venv + node 22)

### Test 4: `/awd-quality-gate` возвращает 4 строки

**Шаги:**
1. Ввести: «проверь качество»
2. **Ожидаемое:** 4 строки `[PASS/FAIL] pytest / vitest / build / playwright` + overall

**Текущий статус:** ⏸ не проверено

### Test 5: skill manifest validation

**Шаги:**
1. Каждый SKILL.md имеет валидный YAML front-matter (`name`, `description`)
2. Каждый PS1 скрипт начинается с `$ErrorActionPreference`
3. Каждый PS1 скрипт делает path resolution через `Resolve-Path $PSScriptRoot`

**Текущий статус:** ✅ done (visually inspected при написании)

---

## Известные ограничения

- **Smoke выполняется человеком** — нужен запуск Claude Code в проекте + ручной ввод промптов. Эта Claude-сессия (которая записала файлы) не может верифицировать что НОВАЯ сессия их подхватит.
- **Powershell execution policy** — на чистой машине может потребоваться `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. SKILL.md содержит инструкцию.
- **Backend `.venv`** — должен существовать с installed deps. Если нет — `up.ps1` exit 1 с error message.

---

## Next steps

1. **Пользователь** запускает новую Claude Code сессию в проекте
2. **Пользователь** прогоняет Test 1–4 ручным вводом
3. **Пользователь** обновляет этот файл — меняет `⏸ не проверено` → `✅ PASS` или `❌ FAIL` с timestamp + detail
4. После всех PASS — Phase 8 COMPLETE → переход к Phase 9

---

## Acceptance criteria (для PHASE-summary.md)

- [ ] Test 1: wrong-project guard работает в новой сессии
- [ ] Test 2: «Продолжай» читает STATE.md
- [ ] Test 3: `/awd-dev-up` запускает серверы за < 60 сек
- [ ] Test 4: `/awd-quality-gate` возвращает структурный output
- [x] Test 5: skill manifest validation (visual inspection done)
