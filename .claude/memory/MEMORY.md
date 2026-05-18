# Memory Index — 1С Аналитик (analyst-workspace-design)

> Проектная память. Полные записи — Read по триггеру.

## Требования пользователя
- [STACK / SESSIONS / LEARN](requirements-stack-sessions-learn.md) — 3 направления допила (MSG #10)
- [LLM-провайдеры](llm-providers.md) — cloud-only, MiMo приоритет, no Ollama
- [Distribution](distribution.md) — Electron + auto-update, multi-user
- [Design constraints](design-constraints.md) — чат во главе, никаких 8 экранов
- [Pivot history](pivot-history.md) — v0/v0b/v1, текущее v1.1.0
- [Open questions](open-questions.md) — что неясно, что в backlog

## Контракт сессии (для будущих Claude Code)
- Работаем ТОЛЬКО в `C:\CLOUDE_PR\projects\analyst-workspace-design\`
- НЕ ЛЕЗТЬ в `analyst-tools-1c` — другой проект (заброшенный v0)
- "Продолжай" = читать `.planning/STATE.md` + последний PHASE-summary
- Брутальная честность ↔ пушбэк
- Чат во главе. Никогда не предлагать work-modes/Object-IDE/Workflow-editor
