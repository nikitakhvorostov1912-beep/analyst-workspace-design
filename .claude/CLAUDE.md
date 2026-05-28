# 1С Аналитик — project-local Claude routing

> Этот файл автоматически подгружается Claude Code при работе в проекте `analyst-workspace-design/`.
> Корневой `CLAUDE.md` (в `..`) — стратегический документ проекта.
> Этот файл — оперативный routing для меня (Claude).

---

## ⚠️ WRONG-PROJECT GUARD (читать ПЕРВЫМ)

**Работаем ТОЛЬКО в `C:\CLOUDE_PR\projects\analyst-workspace-design\`**.

НЕ ЛЕЗТЬ в:
- `C:\CLOUDE_PR\projects\analyst-tools-1c\` — **заброшенный v0** Object-IDE концепт (удалён 2026-05-18, может всплыть в индексах)
- Другие папки в `C:\CLOUDE_PR\projects\*` — другие проекты со своими CLAUDE.md
- `C:\CLOUDE_PR\voice-agent-1c\`, `C:\CLOUDE_PR\ai-ecosystem-1c\` — отдельные проекты Khvorostov

Если получил запрос на работу с другим проектом — переспросить пользователя.

---

## Концепция (verbatim из root CLAUDE.md)

**Аналог ChatGPT/Claude.ai/Perplexity**, но специализированный под 1С: аналитик пишет вопрос на естественном языке, LLM сама выбирает MCP-tool, формирует параметры, получает ответ, форматирует с inline-карточкой.

**Аналитик НЕ знает про get_metadata/execute_query/get_event_log** — это работа LLM. Может развернуть trace для проверки.

---

## Стек кратко

Next 15 + React 19 + shadcn/ui + Tailwind 4 (frontend, port 3010)
FastAPI + Pydantic v2 + SSE + SQLite via aiosqlite (backend, port 8010)
Electron + electron-builder + PyInstaller (desktop distribution, v1.1.0)

Подробнее: `.claude/rules/tech-stack.md`.

---

## Проектные скиллы (`.claude/skills/`)

| Скилл | Когда вызывать |
|---|---|
| `/awd-dev-up` | подними сервера, запусти dev, start, открой приложение |
| `/awd-quality-gate` | проверь качество, перед коммитом, всё ли зелёное |
| `/awd-claude-design-handoff` | хочу итерировать UI через claude.ai/design |

---

## Релевантные глобальные скиллы (READ-ONLY refs)

| Скилл | Путь | Триггер |
|---|---|---|
| `claude-design` | `~/.claude/skills/claude-design/SKILL.md` | дизайн через claude.ai/design |
| `playwright-test` | `~/.claude/skills/playwright-test/SKILL.md` | E2E тесты frontend |
| `reflect` | `~/.claude/skills/reflect/SKILL.md` | разбор полётов |
| `weekly-improve` | `~/.claude/skills/weekly-improve/SKILL.md` | еженедельный аудит |
| `inspect` | `~/.claude/skills/inspect/SKILL.md` | аудит кода/архитектуры |

**НЕ применимы к этому проекту** (1С-метаданные / EPF / БСП): `cf-*`, `epf-*`, `erf-*`, `skd-*`, `role-*`, `form-*`, `meta-*`, `mxl-*`, `subsystem-*`, `template-*`, `cfe-*`, `db-*` (1C), `web-*` (Apache), `1c-*` методики, `*-expert` (1C), `bsp-patterns`, `kafka-1c-adapter`, `requirements-list`, `to-be-optimization`, `erp-configuration-advisor`, `gap-analysis`. У них своя сфера — доработка метаданных 1С через EDT, не frontend/backend веб-приложения.

---

## Маршруты памяти (lazy-load)

Читать ТОЛЬКО при срабатывании триггера, не все сразу.

| Триггер / тема | Файл |
|---|---|
| Старт «Продолжай» / новая сессия без задачи | `.planning/STATE.md` + последний `phases/*/PHASE-summary.md` |
| LLM-провайдеры, Multi-LLM, MiMo, OpenAI-compatible | `.claude/memory/llm-providers.md` |
| Distribution, Electron, инсталлер, auto-update | `.claude/memory/distribution.md` |
| Design, UI, экраны, цвета, шрифты, claude.ai/design | `.claude/memory/design-constraints.md` |
| Какую фазу делать дальше | `.planning/ROADMAP.md` |
| Open questions / неопределённости | `.claude/memory/open-questions.md` |
| История pivots v0/v0b/v1 / почему wrong project | `.claude/memory/pivot-history.md` |
| STACK/SESSIONS/LEARN требования (MSG #10) | `.claude/memory/requirements-stack-sessions-learn.md` |
| Запреты дизайна | `.claude/rules/design-bans.md` |
| Стек версии | `.claude/rules/tech-stack.md` |
| Session contract (брутальная честность, etc.) | `.claude/rules/session-contract.md` |

Индекс: `.claude/memory/MEMORY.md`.

---

## Workflow «Продолжай» / «иди дальше по гсд»

При запросе «Продолжай» или старте сессии без явной задачи:

1. Read `.planning/STATE.md` → текущая `milestone`, `phase`, `progress`
2. Read последний active/done `.planning/phases/*/PHASE-summary.md` (если есть)
3. Если active phase имеет `<N>-CONTEXT.md` — Read его
4. Озвучить в ОДНОМ сообщении: на чём остановились + следующая фаза по ROADMAP + 2-3 опции что делать
5. **Ждать команды. НЕ начинать работу автономно.**

При команде «иди до конца» / «работай без пауз» — продолжать атомарными коммитами по плану до явной паузы / завершения / упирания в риск.

---

## Запреты (verbatim)

См. `.claude/rules/design-bans.md`. Главное:
- Никаких 8 экранов wizard
- Никаких work-modes / Object-IDE / Workflow editor
- Никаких AI right-rail инсайтов
- Inter font, purple-cyan gradients, glass morphism — запрет
- Mobile-first — запрет (desktop ≥ 1280px)
- Светлая тема — запрет

---

## Брутальная честность

- Я (Claude) брутально честен с пользователем
- Пользователь брутально честен со мной
- Проверять утверждения перед согласием — не молча пивотить
- Признаваться когда не помню / не знаю — НЕ выдумывать

См. `.claude/rules/session-contract.md`.

---

## Правило 3 итераций

Если за 3 раунда нет прогресса — STOP, передаём пользователю, переписываем руками.

---

## Текущее состояние (snapshot 2026-05-28)

- **Milestone:** **M-K2.5** — Knowledge Layer Real LLM Rebuild (NVIDIA NIM, in_progress)
- **Closed milestones:**
  - **M-K0 Stabilization** — 28/28 findings (100%) закрыт `00ab58e` 2026-05-25
  - **M6 Hermes Integration** — 30/30 фич (Memory + Skills + Curator)
  - **M7 Commerce Readiness** — code-ready, ждёт EV/OV cert + manual smoke v1.3.0
- **Активный фон:** NIM rebuild 63 203 карточек (`qwen/qwen3.5-122b-a10b`), 11 python процессов, ETA ~10-43 часа. Watchdog каждые ~30 мин.
- **v1.3.0** — installer собран (`analyst-setup-v1.3.0.exe` 183-187 МБ), ждёт smoke на VM + git tag + GitHub Release. Подпись отложена до EV/OV cert от admin.
- **Ветка:** `main` (M-K0 merged, M-K2.5 идёт прямо на main с атомарными коммитами по wave). Последние: `ad74cec` (NIM rebuild pipeline), `9846618` (wave5 partial), `5201893` (wave4 13-20).
- **Прогресс M-K2.5:** ~4115/63203 (6.5%) на момент 2026-05-28 12:00.

---

## Parallel tech debt (пока NIM крутится)

План: `.planning/PARALLEL-PLAN-2026-05-28.md`. Задачи A1-F2 (~5.5 ч):
- ✅ A1 — STATE.md Wave 6 → DONE (honesty fix)
- ✅ E1 — этот файл snapshot 2026-05-28
- 🟡 C1 — ruff E501 в loop.py (8 E501 в SYSTEM_PROMPT)
- 🟡 B1/B2 — MetricCard → CardHeader + Vitest
- 🟡 C2 — 7 flaky tests encoding fix (cp1251 на Windows)
- 🟡 E2/E3/E4/E5 — ARCHITECTURE/BACKLOG/ROADMAP/CERT-PROCESS uplift
- 🟡 F1 — `.planning/SMOKE-NIM-REBUILD.md` чек-лист

Технический долг v1.3.0+ (исторический):
- 6 cards refactor через CardHeader — B1 закрывает 1/6 (MetricCard)
- ToolTrace visual upgrade — рабочий, отложено
- Playwright design-v2.spec.ts smoke — 3 spec'а unskipped, ждут dev-stack
- Phase 10 (LEARN sqlite-vec/RAG) — DEFERRED, заменён Hermes Memory+Skills (M6)
