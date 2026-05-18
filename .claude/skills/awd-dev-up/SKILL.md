---
name: awd-dev-up
description: Поднять backend (:8010) + frontend (:3010) для analyst-workspace-design с автоматическим verify
---

# /awd-dev-up

Запускает оба сервера проекта одной командой с health check.

## Когда вызывать

- «подними сервера», «запусти dev», «start», «открой приложение»
- В начале сессии когда нужно поработать с UI
- Перед `/awd-quality-gate playwright` (нужны live серверы)

## Что делает

1. Останавливает процессы на :8010 и :3010 (если есть)
2. Стартует backend uvicorn в `backend/.venv`
3. Стартует `npx next dev -p 3010` в `frontend/`
4. Polling до Ready (timeout 60 сек): `/health` 200 + HTML с title «1С Аналитик»
5. Output: URLs обоих сервисов

## Запуск

```powershell
pwsh .claude/skills/awd-dev-up/scripts/up.ps1
```

## Caveat

- Требует `pnpm` или `npx` в PATH
- Требует `.venv` в `backend/` (создаётся через `python -m venv .venv` + `pip install -e .`)
- На чистой машине: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (если блокирует .ps1)
- Серверы стартуют в `-WindowStyle Hidden` — для остановки используй `Get-Process node, python | Stop-Process -Force` или `awd-dev-down` (TBD)
