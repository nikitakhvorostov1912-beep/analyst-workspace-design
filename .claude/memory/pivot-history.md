# Pivot history (lessons learned)

| Версия | Подход | Статус | Дата |
|---|---|---|---|
| v0 | Object-centric IDE (tree + объект + AI rail) | REJECTED | до 2026-05-13 |
| v0b | Workflow editor (карточки операций как Postman steps) | REJECTED | до 2026-05-13 |
| **v1** | **Chat-first (NL → LLM → tool_calls → cards)** | **ACCEPTED** | 2026-05-13 |

## Wrong project warning
**`C:\CLOUDE_PR\projects\analyst-tools-1c\`** — **УДАЛЁН локально 2026-05-18** (1.16 GB освобождено).
Был v0 Object-IDE концепт (Monaco editor, multi-LLM router, EPF клиент) — НЕ путать с `analyst-workspace-design`.
GitHub репо остаётся: `https://github.com/nikitakhvorostov1912-beep/analyst-tools-1c.git` (можно вернуть `git clone` если когда-то понадобится — но не должно).

Если будущая Claude-сессия видит ссылки на `analyst-tools-1c` в каком-то rule/memory — игнорировать, проект больше не существует локально.

## Релизы
| Дата | Версия | Что |
|---|---|---|
| 2026-05-13 | — | GSD init проекта |
| 2026-05-14 | — | Phase 1 Foundation (backend + frontend skeleton) |
| 2026-05-14 | — | Phase 2 MVP Chat (orchestrator + cards + sessions + trace) |
| 2026-05-15 | — | Phase 3 Production Ready (security + tests + docs) |
| 2026-05-15 | — | Phase 4 Demo & Refine (anon + extra cards + slash/mention/cmd-k) |
| **2026-05-15** | **v1.0** | Phase 5 UX Polish (onboarding + settings UI) |
| **2026-05-16** | **v1.1.0** | Phase 7 Desktop Installer (Electron + NSIS, .exe 105.9 MB) |
