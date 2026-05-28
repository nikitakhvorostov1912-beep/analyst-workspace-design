---
gsd_state_version: 1.0
milestone: M-K2.5
milestone_name: "Knowledge Layer Real LLM Rebuild — NVIDIA NIM"
status: in_progress
last_updated: "2026-05-28T12:00:00Z"
progress:
  # M-K0 closed 100% (28/28) commits 6a1b228 → 00ab58e
  m_k0_total: 28
  m_k0_done: 28
  # M-K2.5 NIM rebuild прогресс (background python, watchdog ~30 мин)
  m_k2_5_total: 63203
  m_k2_5_done: 4115  # обновляется по факту, см. watchdog в PARALLEL-PLAN
  m_k2_5_percent: 6.5
  # Commerce plan (исторический контекст)
  commerce_plan:
    phase_1_done: 4  # P1.1-4 закрыты
    phase_2_done: 3
    phase_3_done: 4
    phase_4_done: 0  # smoke VM + release pending
note: "M-K0 закрыт 100% (28/28) коммитом 00ab58e от 2026-05-25. Активно: M-K2.5 NVIDIA NIM rebuild 63 203 карточек (qwen/qwen3.5-122b-a10b), 11 python процессов в фоне, ETA ~10-43 часа. Параллельно идёт `.planning/PARALLEL-PLAN-2026-05-28.md` — закрытие tech debt пока NIM крутится."
---

# Project State

## Project Reference

См. `.planning/PROJECT.md` (updated 2026-05-13)

**Core value:** Аналитик пишет вопрос на NL → LLM сама дёргает MCP → ответ с inline-карточкой за ≤30 сек

**Current focus:** M-K2.5 Knowledge Layer real LLM rebuild — 63 203 эталонных carts через NVIDIA NIM (qwen/qwen3.5-122b-a10b), фон. Параллельно tech debt cleanup по `.planning/PARALLEL-PLAN-2026-05-28.md`.

---

## Update — M-K0 Stabilization CLOSED 100% (2026-05-28)

**Ветка:** `feature/m-k0-stabilization` merged. M-K0 **28/28 findings (100%)** закрыт.

### M-K0 milestone summary (final)

| Wave | Subject | Status | Commit |
|---|---|---|---|
| 0 | Security (8 findings: SSRF, CSP, SQL validator, CORS, rate-limit, deprecation, injection) | ✅ DONE | `6a1b228` |
| 1 | Backend Quality (6 findings: pending race, task GC, silent failures, leak, card matching, batch commit) | ✅ DONE | `d24e22d` |
| 2 | Performance (3 findings: SQLite pool, LLMClient reuse, React Context cache) | ✅ DONE | `7f60e9d` |
| 3 | Prompts (3 findings: few-shot tools, memory recall + bonus injection в SEC-3) | ✅ DONE | `4db8313` |
| 4 | Frontend (3 findings: prefers-reduced-motion, WCAG AA контраст, stable attachment keys) | ✅ DONE | `4db8313` |
| 5 | Architecture (1 finding: contextvars для structured logging) | ✅ DONE | (W1-3 серия) |
| 6 | Docs+DevOps (4 findings: DOC-1 ARCHITECTURE rev, DOC-2 цифры, DEVOPS-1 cert process, DEVOPS-5 semver guard) | ✅ DONE | `f956a21` |
| 7 | Coverage push 60%+ | ✅ DONE | `8935b62` |
| 8 | Security re-audit (+ 2 HIGH) + test stabilization | ✅ DONE | `2e27522` |
| 9 | SUMMARY + STATE done + handoff | ✅ DONE | `00ab58e` |

**Honesty note (2026-05-28):** Эта таблица была устаревшей до 2026-05-28 — показывала Wave 6 🟡 в работе и Wave 7-9 pending, хотя реально milestone был закрыт ~3 дня назад. Параллельная сессия запустила NIM rebuild (M-K2.5) поверх закрытого M-K0, отсюда desync. Исправлено как часть A1 из `.planning/PARALLEL-PLAN-2026-05-28.md`.

### Цифры (актуальные на 2026-05-25)

- **Backend pytest:** ~970 passed (+ ~123 от M-K0); **1 pre-existing deselect**
  (`test_chat_llm_429_returns_rate_limit_with_retry_after_s` — Windows DNS
  suffix резолвит `fake-mcp` → `127.0.0.200`, SSRF guard корректно блокирует
  как DNS rebinding; тест нужно переписать на `http://127.0.0.1:1/mcp`).
- **Frontend vitest:** 322 / 322 (42 файла, +1 `config-cache.test.tsx`).
- **Build (`npx next build`):** PASS, 0 regressions.
- **loop.py:** **~1835 строк** (vs 870 → 689 в P1.2). PROMPT-1 + PROMPT-3 +
  ARCH-2 + few-shot блоки добавили ~250 строк system_prompt + декомпозиции.
  **ARCH-1 decompose loop.py (688→≤400)** перенесён в M-K3.0 preparatory.

### Связь с Knowledge Layer + M6 Handoff

- Knowledge Layer план: `.planning/knowledge-layer-2026-05-24/PLAN.md` v1.2
  (M-K0..M-K6 roadmap).
- M6 handoff (от параллельной сессии): `.planning/handoff/m6-quality-
  expansion/` (12 файлов).
- Unified roadmap: `.planning/milestones/M6-INTEGRATED-PLAN.md`.
- 22 решения + 6 user resolutions: `INTEGRATION-DECISIONS.md`.
- 15 gap'ов после ревизии: `.planning/milestones/AUDIT-GAPS.md` →
  13 tracked tasks (G1-G15) привязаны к M-K1..M-K5 фазам.

---

## Honesty gap — заявления M6 → реальность (2026-05-22)

Прошлая запись STATE.md заявляла M6 «100% / 30/30 фич». Глубокое ревью 9 направлений (architecture/backend/frontend/security/tests/UX/perf/completeness/devops) вскрыло:

- ~~**Sprint 3 (Self-Learning) — code-only complete, НЕ wired в runtime.**~~ → **Поправка от W1.8 (2026-05-22 вечер):** аудит-агент ошибся. Sprint 3 был wired в коде (loop.py:469-481 init skill_store, 528-542 skills_block в prompt, 532-539 usage.increment, 1184-1199 schedule_review). Но был **скрытый dep-bug**: `aux_compressor_client` создавался ТОЛЬКО при `compression_enabled=True`, и schedule_review тихо skip'ался без aux. → Зависимость развязана: aux создаётся при `compression_enabled OR learning_enabled`. End-to-end интеграционный тест подтверждает что цепочка работает: skill реально создаётся на диске после turn'а и попадает в system prompt следующего вопроса.
- **«652 backend pytests passed»** — цифра близка к правде (681 collected / 672 passed), НО **общее coverage 26.58%, не 80%**. На критичных модулях: `loop.py` 11%, `persistence.py` 13%, `mcp_pool.py` 15%, `cards.py` 28%. → Wave 2.6 (test coverage 60% на критичных).
- **«Chrome MCP smoke по всем экранам»** не покрывает SSE-стриминг — 3/5 Playwright spec'ов **skipped** (`setup-and-prompt`, `sessions-history`, `channel-switch`). Главный happy-path (отправить сообщение → SSE → карточка) не тестируется E2E. → Wave 2.5.
- **«Multi-tenant через channel selector»** изоляция per-session, не per-channel. Глобальные dict'ы `INTERRUPTS`/`_pending`/`CLARIFY` в memory module-level. → Wave 2.2.

Подробный отчёт ревью: ответ ассистента в сессии 2026-05-22 «Глубокое ревью приложения».

---

## Status

| Aspect | Value |
|--------|-------|
| **Current Milestone** | M7 — Commerce Readiness (in_progress) |
| **Branch** | `feature/v1.3.0-commerce` |
| **Latest tag** | v1.2.2 (2026-05-19, pre-Hermes) |
| **Pending tag** | v1.3.0 — installer уже собран (a070b21), ждёт smoke + release |
| **Last commit** | `5b76e0c` P1.2 phase3 step3 + `94b7864` TD-7 + `bd40d3d` TD-4 + `57fc20a` TD-3 final |
| **Mode** | Atomic commits per ticket, тесты обязательны |
| **Last Update** | 2026-05-24 12:00 — POST-RELEASE-DEBT основные пункты закрыты, fresh installer pending |

### Verification status (2026-05-24 12:00)

- **Backend pytest:** **847 / 847 passed** (было 800 → 837 → 844 → 847). 0 flaky.
- **Backend новые тесты (P1.2 phase1+2+3 + P2.1 + P2.2 + P2.3 + P3.2):** 149 / 149 passed
- **Backend coverage:** **88.1%** orchestrator+clients (target ≥80%, TD-2 закрыт)
  - loop.py: 81.9%, persistence.py: 88.4%, sql_validator: 89%, cards: 93%
- **Frontend vitest:** 323 / 323 passed (43 файла)
- **Frontend `npx tsc --noEmit`:** 0 errors
- **Backend `ruff check` loop.py:** 8 errors (всё E501 — длинные строки в SYSTEM_PROMPT)
- **Frontend E2E:** 3 ранее-skipped spec'а unskipped — требуют `pnpm exec playwright test`
  на dev-stack для финальной верификации (TD-4)
- **Установщик v1.3.0 (свежий)** пересобран 2026-05-24 11:00 — 183 МБ.
  Лежит в `1C-Analyst-v1.3.0/analyst-setup-v1.3.0.exe` + `desktop/dist/`.
  Включает все правки до `9ba4c1c` (включая skills UI «Что система
  выучила» + P1.2 phase3 + decomposed loop.py). Готов к smoke на VM.
- **Артефакты для smoke / release:**
  - `.planning/SMOKE-v1.3.0.md` — 9-секционный чек-лист
  - `.planning/RELEASE-NOTES-v1.3.0-DRAFT.md` — текст для GitHub Release
  - `.planning/POST-RELEASE-DEBT.md` — 14 пунктов тех долга для будущих spike

### Commerce Plan Phase 1-4 (2026-05-23, поверх Wave 1-4)

| Тикет | Статус | Заметка |
|---|---|---|
| P1.1 | ✓ Done | Verification stamp: Sprint 3 уже wired |
| P1.2 phase 1 | ✓ Done | 4 pure helpers (`469460c`) + 22 теста (`6a299a5`) |
| P1.2 phase 2 | ✓ Done | `_dispatch_sync_internal_tool` (`afebab8`) + 11 тестов (`90ba493`) |
| P1.2 phase 3 step1 | ✓ Done | `_execute_mcp_tool` (`7f2b89c`) + 7 тестов (`9ba4c1c`) |
| P1.2 phase 3 step2 | ✓ Done | skill_store / openai_tools / vision helpers (`f6816b9`) |
| P1.2 phase 3 step3 | ✓ Done | history + skills_block helpers (`5b76e0c`). **870 → 689 строк (-181)** |
| P1.3 | ✓ Code ready | electron-builder.yml + GH workflow; ждёт EV/OV cert от admin |
| P1.4 | ✓ Done | electron-updater интегрирован, UpdateBanner в Header |
| P2.1 | ✓ Done | user_secrets таблица + AES-GCM + REST + chat.py priority |
| P2.2 | ✓ Done | ResultSizeGate (500 row cap) + TableCard truncated banner |
| P2.3 | ✓ Done | sql_validator.py через sqlparse + защита от bypass |
| P3.1 | ✓ Done | NVIDIA NIM база, Cloud.ru 152-ФЗ альтернатива (rev3: DeepSeek V4 Flash default) |
| P3.2 | ✓ Done | resolve_default_api_key + endpoint detection tests |
| P3.3 | ✓ Done | Compliance badges в LLMConfigForm |
| P3.4 | ✓ Done | CHANGELOG + memory/llm-providers.md обновлены |
| P4.1 | ⏸ Manual | Smoke на чистой Win11 VM — checklist `.planning/SMOKE-v1.3.0.md` (9 секций) |
| P4.2 | ✓ Done | TypeScript 0 errors, ruff на новых файлах clean, build clean (`41cd18f`) |
| P4.3 | ⏸ Manual | Re-build с подписью — ждёт EV/OV cert. Текущий `analyst-setup-v1.3.0.exe` 187 МБ работоспособен |
| P4.4 | ⏸ Manual | git tag v1.3.0 + GitHub Release — после P4.1 smoke PASS |
| P4.5 | ⏸ Manual | STATE.md M7 close + M8 open — после P4.4 release |

## Milestone M7 — Commerce Readiness (2026-05-22 в работе)

Чек-лист: `.planning/CHECKLIST-COMMERCE-2026-05-22.md`. Baseline: `.planning/BASELINE-2026-05-22.md`.

### Wave 1 — CRITICAL (pilot-blockers, 16h оценка)

| # | Тикет | Статус | Тесты |
|---|---|---|---|
| W1.1 | LLM ключ из installer .env | ✓ Done | electron-builder filter |
| W1.2 | Keyword-scanner на execute_query | ✓ Done | +9 pytest |
| W1.3 | MAX_TOOL_CALLS_PER_TURN лимит | ✓ Done | +2 pytest |
| W1.4 | Rate-limit /chat (slowapi) | ✓ Done | +2 pytest |
| W1.5 | LLMClient leak verify | ✓ Done (false-positive) | n/a |
| W1.6 | XSS Prism CodeCard (DOMPurify) | ✓ Done | +6 vitest |
| W1.7 | AbortController useChatStream | ✓ Done | 15/15 useChatStream |
| W1.8 | Sprint 3 Hermes wire-up | ✓ Done | +2 e2e pytest |
| W1.9 | STATE.md honesty gap update | ✓ Done | n/a |

### Wave 2 — HIGH (commerce-blockers, 55h)

Code signing, auto-update, decompose loop.py (1157→400), test coverage 60%, E2E streaming, robust injection scan, Docker multi-stage, slash-команды.

### Wave 3 — MEDIUM polish (12h)

UI токены, tool name mapping, PRAGMA tuning, httpx reuse, lazy load, A11y.

### Wave 4 — Release v1.3.0 (5h)

Smoke, quality gate, build, release notes, tag.

---

## Milestone M6 — Hermes Integration (2026-05-20)

| # | Sprint | Status | Фич | Commit | Tests |
|---|---|---|---:|---|---:|
| 1 | Memory Foundation | ✓ Done | 5 | `df76ed8` | +21 pytest |
| 2 | Context & Resilience | ✓ Done | 8 | `1d5e060` | +87 pytest |
| 3 | Self-Learning | ⚠ Code-only | 6 | `123418e` | +75 pytest, runtime НЕ wired |
| 4 | UX & Interactivity | ✓ Done | 6 | `5b8ea8d` | +64 pytest |
| 5 | Polish & Observability | ✓ Done | 5 | `dccb672` | +57 pytest |

**Honesty update 2026-05-22:** Sprint 3 был помечен как Done без верификации в runtime. Тесты есть, файлы есть, но fire-and-forget вызов из `loop.py` НЕ активирован. Откатывать не имеет смысла — закроем через W1.8 wire-up.

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
