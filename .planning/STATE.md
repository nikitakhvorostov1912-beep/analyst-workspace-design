---
gsd_state_version: 1.0
milestone: M6
milestone_name: "Hermes Integration — Memory + Context + Self-Learning + UX + Observability"
status: hermes_integration_complete
last_updated: "2026-05-20T15:30:00Z"
progress:
  total_sprints: 5
  completed_sprints: 5
  total_features: 30
  completed_features: 30
  percent: 100
note: "Все 5 спринтов Hermes integration закрыты (commits df76ed8 → dccb672). 30 фич, 652 backend pytests, 304 vitest, Chrome smoke по всем экранам. Backlog: A12/D2/F2/I1/H1/E3/E4/C7 + 3 pre-existing flaky."
---

# Project State

## Project Reference

См. `.planning/PROJECT.md` (updated 2026-05-13)

**Core value:** Аналитик пишет вопрос на NL → LLM сама дёргает MCP → ответ с inline-карточкой за ≤30 сек

**Current focus:** Post-Hermes — backlog или новый milestone

---

## Status

| Aspect | Value |
|--------|-------|
| **Current Milestone** | M6 — Hermes Integration ✓ COMPLETE |
| **Branch** | `main` |
| **Latest tag** | v1.2.2 (2026-05-19, pre-Hermes) |
| **Pending bump** | v1.3.0 — для Sprint 1-5 release |
| **Last commit** | `dccb672` feat(sprint-5): Hermes Polish & Observability |
| **Mode** | YOLO + atomic commits per sprint |
| **Last Update** | 2026-05-20 (Sprint 5 закрыт + Chrome smoke + docs phase started) |

## Milestone M6 — Hermes Integration (2026-05-20)

| # | Sprint | Status | Фич | Commit | Tests |
|---|---|---|---:|---|---:|
| 1 | Memory Foundation | ✓ Done | 5 | `df76ed8` | +21 pytest |
| 2 | Context & Resilience | ✓ Done | 8 | `1d5e060` | +87 pytest |
| 3 | Self-Learning | ✓ Done | 6 | `123418e` | +75 pytest |
| 4 | UX & Interactivity | ✓ Done | 6 | `5b8ea8d` | +64 pytest |
| 5 | Polish & Observability | ✓ Done | 5 | `dccb672` | +57 pytest |

**Overall:** Progress: ██████████ 100% (30/30 фич). 652 backend pytests passed (3 pre-existing flaky), 304 vitest, Chrome MCP smoke ✓.

## Milestone M5 — Post-v1.1 Expansion (предыдущий)

См. `.planning/phases/11-design-v2-import/PHASE-summary.md` + RELEASE-NOTES v1.2.0/v1.2.1/v1.2.2.

| Phase | Status |
|---|---|
| 1-5 (Foundation/MVP/Production/Demo/UX) | ✓ Complete (v1.0/v1.1) |
| 7 Desktop Installer | ✓ Complete (v1.1.0 released 2026-05-16) |
| 8 STACK Integration | ✓ Complete |
| 9 Sessions DB Init | ✓ Complete (VM smoke deferred) |
| 10 Learn Engine sqlite-vec/RAG | ⏸ DEFERRED — заменено Hermes Memory + Skills (Sprint 1/3) |
| 11 Design v2 Import | ✓ Complete (Stencil/Mono brand) |

## Что появилось в проекте от Hermes

### Backend (15+ модулей):

**Memory & Learning:**
- `memory/markdown_store.py` — MEMORY.md + USER.md per-channel
- `memory/injection_scan.py` — 10 regex patterns prompt injection
- `learning/trajectory.py` — ShareGPT JSONL logger
- `learning/skill_store.py` + `skill_provenance.py` + `skill_usage.py`
- `learning/curator.py` + `curator_backup.py` — auto-archive с rollback
- `learning/background_review.py` — aux LLM fire-and-forget post-turn

**Orchestrator:**
- `auxiliary.py` — aux client (compressor + curator + review)
- `compressor.py` — head/tail protect + aux summarize + prune
- `iteration_budget.py` — thread-safe counter
- `retry.py` — full jitter exponential backoff
- `sanitize.py` — surrogate halves + orphan tools repair
- `interrupt.py` — set-based реестр для «Стоп»
- `error_classifier.py` — 9 FailoverReason
- `clarify.py` — structured multiple-choice вопросы
- `think_scrubber.py` — `<think>` filter в SSE stream
- `redact.py` — regex маскировка секретов
- `insights.py` — sessions/messages/tools dashboard
- `session_search.py` — 3 mode FTS5
- `todo.py` — per-session task list
- `usage_pricing.py` — $/M tokens registry для 12 моделей
- `model_metadata.py` — context window per model
- `tool_result_storage.py` — three-level defence для больших outputs
- `prompt_caching.py` — Anthropic system_and_3 layout

**Routes:**
- `/memory/{channel_id}` — GET/PUT
- `/skills/{channel_id}` — GET/POST/DELETE + archive/unarchive
- `/skills/{channel_id}/curator/run` — auto-archive
- `/todos/{session_id}` — GET/action
- `/chat/{session_id}/interrupt` — POST 202
- `/chat/clarify` — POST 204
- `/insights` — GET с period
- `/diagnostics/trajectory`

### Frontend (5 новых страниц/компонентов):
- `/settings/memory` — MEMORY.md / USER.md редактор
- `/settings/skills` — Skills CRUD + Curator dry-run/run + archive UI
- `/insights` — 6 KPI cards + tables top tools/channels + period switcher
- `MemoryHint` — one-time toast про MEMORY.md
- `ClarifyDialog` — radio/checkbox + custom answer
- Stop button в Composer вместо Send при isStreaming

## Backlog (нереализованные Hermes фичи)

- A12 Skills guard (security scanner для downloaded skills)
- D2 Delegate/subagents
- F2 Tirith security scanner
- I1 Langfuse observability plugin
- H1 Models.dev registry (auto-discovery моделей)
- E3 Cross-session rate guard
- E4 Rate limit tracker
- C7 Approval system upgrade (smart approval через aux LLM)

## Pre-existing flaky tests

НЕ моя регрессия от Hermes — были красные ещё до Sprint 1 (verified через `git stash` на `dfd8666`).

- `tests/test_migrations_v5.py::test_migration_v5_backfill_messages_into_fts`
- `tests/test_orchestrator_loop_confirm.py::test_loop_emits_confirm_required_on_dangerous_execute_code`
- `tests/test_orchestrator_loop_confirm.py::test_loop_approved_continues`

## Что НЕ верифицировано в живой среде (M6 → M7?)

- ContextCompressor на длинном диалоге (>100k tokens)
- background_review с реальным aux LLM сохранением skill
- clarify_question через MiMo (требует prompt-engineering — модель должна решать «уточнять или нет»)
- ThinkScrubber на потоке от reasoning-модели
- prompt_caching на Anthropic Claude
- usage_pricing на реальных turn'ах (сейчас estimated через chars/3.5)

## Artifacts Status

- [x] [PROJECT.md](./PROJECT.md) — vision (post-pivot v1)
- [x] [REQUIREMENTS.md](./REQUIREMENTS.md) — 22 v1 requirements
- [x] [ROADMAP.md](./ROADMAP.md) — 4 coarse phases
- [x] `.planning/research/hermes-2026-05-20/HERMES-IMPLEMENTATION-PLAN.md` — 1764 строки, 30 фич (все done)
- [x] `.planning/SPRINT-SUMMARY.md` — итоговый документ Hermes Integration (2026-05-20)
- [x] STATE.md (этот файл) — M6 Complete

## Next steps (опции)

1. **Release v1.3.0** — bump package.json, RELEASE-NOTES, Electron installer, git tag v1.3.0 + merge
2. **End-to-end smoke на живом LLM** — реальный длинный диалог с MiMo чтобы пощупать compressor / background_review / clarify в работе
3. **Fix 3 pre-existing flaky** — починить test_migrations_v5 + 2 confirm-теста
4. **Backlog Hermes** — A12 Skills guard / D2 Delegate / E4 Rate tracker
5. **Новый milestone M7** — что угодно по запросу пользователя
