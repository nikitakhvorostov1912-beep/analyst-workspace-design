---
name: awd-quality-gate
description: Прогнать pytest + vitest + pnpm build + playwright и вернуть PASS/FAIL по каждому
---

# /awd-quality-gate

Полный качественный прогон перед коммитом / релизом.

## Когда вызывать

- «проверь качество», «quality gate», «перед коммитом», «всё ли зелёное»
- Перед `git tag` любого релиза
- Перед merge feature branch → master

## Что делает (НЕ fail-fast — все 4 шага независимо)

1. **`pytest backend/tests`** (timeout 120s)
2. **`pnpm vitest run`** в `frontend/`
3. **`pnpm build`** в `frontend/`
4. **`pnpm playwright test --reporter=line`** в `frontend/` (требует live :3010)

Output — 4 строки с `[PASS]`/`[FAIL]` + общий вердикт.

## Запуск

```powershell
pwsh .claude/skills/awd-quality-gate/scripts/gate.ps1
```

## Exit codes

- **0** — все 4 PASS
- **1** — хотя бы один FAIL

## Caveat

- Playwright требует запущенный `awd-dev-up` (:3010 живой). Если не запущен — Playwright FAIL.
- Backend tests требуют `.venv` с installed deps.
- На медленной машине шаг 3 (build) занимает до 60 сек.
