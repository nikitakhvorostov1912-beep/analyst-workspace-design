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

## Текущее состояние (snapshot 2026-05-29)

- **Единый роадмап:** `.planning/ROADMAP-2026-05-29.md` + `Workflow_1C_Analyst_2026-05-29.xlsx` — форвард-источник истины (свёл продуктовую арку M1-M7 и Knowledge Layer M-K0..M-K6).
- **Milestone:** **M-K3** — Relational + Behavioral + EPF/CFE Delivery (in_progress).
- **Closed:** M-K0 (28/28 `00ab58e`) · M-K1 (15/17) · M-K2 Triple RAG (12/13) · M6 Hermes · M7 Commerce (код).
- **M-K3 прогресс:** EPF-скелет 13a.0/13a.1 (`0a3b702`); guardrail G2 `3bd4e5d` (аванс из M-K4). Дальше по плану: M-K3.0 decompose loop.py → собрать ≥20 diagnose-кейсов → **Knowledge Graph (крит. путь 17.1)** → дожать EPF.
- **Аванс M-K4** (hybrid retrieval + phantom guardrails): `581fec9`,`aff4fb2`,`049680b`,`4dbb60d`,`3bd4e5d` — **на паузе до L2-графа**.
- **Параллельный фон:** M-K2.5 NIM rebuild карточек ~6.5% (не блокер; проверить жив ли процесс — действие D3).
- **Ветка:** `feature/m-k3-relational-cfe` (атомарные коммиты; в remote НЕ пушим без запроса).
- **Гигиена релиза:** код `desktop` v1.4.8, последний git-тег v1.2.2 — сборки не тегались (smoke VM + EV/OV cert pending).

---

## Параллельные треки и тех-долг

`PARALLEL-PLAN-2026-05-28.md` **архивирован** (`.planning/_archive/`). Актуальный список — лист «Параллельные треки» в `Workflow_1C_Analyst_2026-05-29.xlsx`:
- M-K2.5 NIM-карточки (фон, не блокер)
- Гигиена релиза: smoke VM + EV/OV cert + git tag v1.4.x + 3 Playwright spec
- Тех-долг: 6 cards refactor (1/6), 7 flaky (cp1251), F841/E501 в loop.py, ToolTrace upgrade

Технический долг v1.3.0+ (исторический):
- 6 cards refactor через CardHeader — B1 закрывает 1/6 (MetricCard)
- ToolTrace visual upgrade — рабочий, отложено
- Playwright design-v2.spec.ts smoke — 3 spec'а unskipped, ждут dev-stack
- Phase 10 (LEARN sqlite-vec/RAG) — DEFERRED, заменён Hermes Memory+Skills (M6)
