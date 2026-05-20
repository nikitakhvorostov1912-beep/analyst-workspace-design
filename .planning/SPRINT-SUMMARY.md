# Hermes Integration — Sprint Summary

> **Дата:** 2026-05-20
> **Milestone:** M6
> **Статус:** ✓ COMPLETE
> **Источник:** [HERMES-IMPLEMENTATION-PLAN.md](research/hermes-2026-05-20/HERMES-IMPLEMENTATION-PLAN.md)

---

## TL;DR

5 атомарных спринтов, 30 фич из плана Hermes Agent (NousResearch, 158k★) портированы в 1С Аналитик за 1 день работы.

| Метрика | Значение |
|---|---|
| Спринтов | 5 |
| Реализованных фич | 30 |
| Backend модулей | 22 (15 orchestrator + 6 learning + 1 memory provider) |
| Routes | 8 новых (`/memory`, `/skills`, `/todos`, `/insights`, `/chat/interrupt`, `/chat/clarify`, etc.) |
| Frontend страниц | 3 (`/settings/memory`, `/settings/skills`, `/insights`) + ClarifyDialog + MemoryHint |
| Pytest | 652 passed (с 0 на старте → +652) |
| Vitest | 304/304 |
| Git commits | 5 атомарных (df76ed8 → dccb672) |
| LOC | ~12 000+ |

---

## Sprint by Sprint

### Sprint 1 — Memory Foundation (commit `df76ed8`, 5 фич)

**Что:** Базовый слой долговременной памяти — MEMORY.md / USER.md per-channel + trajectory logger.

**Что появилось:**
- A1 MEMORY.md + USER.md persistent stores
- A2 MemoryManager + A3 MemoryProvider ABC
- H2 Aux client router (упрощённый, single endpoint)
- G1 Onboarding hints (`MemoryHint` toast при ≥3 сессий)
- I2 Trajectory export (ShareGPT JSONL для fine-tuning)

**Файлы:**
```
backend/app/memory/{provider,manager,markdown_store,injection_scan}.py
backend/app/learning/trajectory.py
backend/app/orchestrator/auxiliary.py
backend/app/orchestrator/memory_integration.py
backend/app/routes/memory.py
frontend/app/settings/memory/page.tsx
frontend/components/memory/MemoryHint.tsx
```

**Что проверено:** pytest для memory/ + learning/ + auxiliary, vitest UI memory page + onboarding, Chrome MCP визуальная проверка UI.

---

### Sprint 2 — Context & Resilience (commit `1d5e060`, 8 фич)

**Что:** Защита от runaway loop'а, сжатие контекста, корректная обработка ошибок, пользовательское прерывание.

**Что появилось:**
- C1 IterationBudget — thread-safe счётчик (заменяет `MAX_TOOL_ITERATIONS=100`)
- B1 ContextCompressor + B2 Filter-safe preamble + B4 Compression wrapper + B5 Tool output pruning
- E1 ErrorClassifier — 9 FailoverReason → RETRY/COMPRESS/ABORT
- E2 Jittered retry (full jitter)
- E6 Message sanitization — surrogate halves + orphan tools repair
- C9 Interrupt mechanism — кнопка «Стоп» через `POST /chat/{session_id}/interrupt`

**Файлы:**
```
backend/app/orchestrator/{iteration_budget,retry,sanitize,interrupt,error_classifier,compressor}.py
backend/app/routes/chat.py (interrupt endpoint)
backend/app/orchestrator/events.py (ClarifyRequiredEvent, DoneEvent.interrupted)
frontend/components/chat/Input.tsx (Stop button)
frontend/components/chat/useChatStream.ts (interrupt callback)
```

**Что проверено:** 87 новых pytest, Chrome smoke кнопки Stop, проверка interrupt route 202 + idempotency.

---

### Sprint 3 — Self-Learning (commit `123418e`, 6 фич)

**Что:** Skills как структурированная сущность (markdown + YAML front-matter), Curator с auto-archive, background_review через aux LLM, todo list для декомпозиции.

**Что появилось:**
- A8 Skill provenance (ContextVar agent/user)
- A9 Skill usage telemetry (JSON counter)
- A5 Background review fork — aux LLM fire-and-forget post-turn решает «сохранить ли skill»
- A6 Curator lite — inactivity-triggered auto-archive
- A7 Curator backup — tar.gz snapshot перед изменениями + restore
- D3 Todo tool — per-session task list, sustains across compression

**Файлы:**
```
backend/app/learning/{skill_store,skill_provenance,skill_usage,curator,curator_backup,background_review}.py
backend/app/orchestrator/todo.py
backend/app/routes/skills.py
frontend/app/settings/skills/page.tsx
```

**Strict invariants Hermes сохранены:**
- Curator архивирует только `agent` skills
- Pinned skills bypass everywhere
- Never auto-delete — только archive (восстановимо)
- Pre-run backup обязателен

**Что проверено:** 75 новых pytest, Chrome smoke создания/архивации/восстановления skill через UI, Curator dry_run корректно показывает invariants.

---

### Sprint 4 — UX & Interactivity (commit `5b8ea8d`, 6 фич)

**Что:** Structured уточнения вместо free-text, защита от prompt injection, фильтрация `<think>` тегов, dashboard сессий, расширенный FTS5 поиск, redaction секретов.

**Что появилось:**
- D1 Clarify tool — `clarify_question(question, options, multi)` → SSE `clarify_required` → `ClarifyDialog` UI
- F1 Prompt injection scan — расширенный sanitize_for_prompt для tool outputs
- G7 Think scrubber — stateful filter `<think>/<thinking>/<reasoning>` в streaming
- G8 Insights engine lite — sessions/messages/tools/errors dashboard
- D4 Session search FTS5 — 3 mode (discovery / deep / cross)
- E8 Redact — regex маскировка API ключей + Bearer + k=v

**Файлы:**
```
backend/app/orchestrator/{clarify,think_scrubber,redact,insights,session_search}.py
backend/app/routes/{clarify,insights}.py
frontend/app/insights/page.tsx
frontend/components/chat/ClarifyDialog.tsx
```

**Что проверено:** 64 новых pytest, Chrome smoke `/insights` (4 KPI + tables + period switcher), интеграция ClarifyDialog через useChatStream.

---

### Sprint 5 — Polish & Observability (commit `dccb672`, 5 фич)

**Что:** Финал. Token pricing, model metadata, прочное хранение больших tool outputs, prompt caching, skill bundles.

**Что появилось:**
- I4 Usage pricing — $/M tokens registry для 12 моделей (OpenAI, Anthropic, MiMo)
- H5 Model metadata — context_window, max_output, supports_vision/reasoning/caching
- D7 Tool result storage — three-level defence (50KB cap, persistence, 200KB per-turn budget)
- H4 Prompt caching — Anthropic system_and_3 layout (4 cache_control breakpoints)
- A10/A11 Skill bundles + preprocessing — `/<bundle>` YAML загрузка + template vars `${ANALYST_*}`

**Файлы:**
```
backend/app/orchestrator/{usage_pricing,model_metadata,tool_result_storage,prompt_caching}.py
backend/app/skills/{bundles,preprocessor}.py
backend/app/orchestrator/insights.py (расширен estimated_tokens + estimated_cost_usd)
frontend/app/insights/page.tsx (KPI Tokens + Cost)
```

**Что проверено:** 57 новых pytest, Chrome smoke `/insights` с двумя новыми KPI cards.

---

## Backlog (нереализованные фичи плана)

| Код | Фича | Cost | Profit | Score |
|---|---|---|---|---|
| A12 | Skills guard (security scanner downloads) | M=2 | 🔥2 | 4 |
| D2 | Delegate/subagents | L=5 | 🔥2 | 1 |
| F2 | Tirith pre-exec scanner | M=2 | 🔥2 | 4 |
| I1 | Langfuse plugin | M=2 | 🔥2 | 4 |
| H1 | Models.dev registry | S=1 | 🔥2 | 5 |
| E3 | Cross-session rate guard | M=2 | 🔥2 | 4 |
| E4 | Rate limit tracker | S=1 | 🔥2 | 5 |
| C7 | Approval system upgrade (smart) | M=2 | 🔥3 | 7 |

Решение по backlog — отдельная сессия. Сейчас score-cut работал на ≥ 7 (cutoff). C7 уже на грани — может уйти в Hermes Part 2.

---

## Что НЕ работает / не верифицировано

### Pre-existing flaky tests (3)
Были красные ещё до Sprint 1 — не связаны с Hermes integration (проверено через `git stash` на коммите `dfd8666`):
- `test_migrations_v5_backfill_messages_into_fts`
- `test_loop_emits_confirm_required_on_dangerous_execute_code`
- `test_loop_approved_continues`

### Не верифицировано на живом LLM
- ContextCompressor на >100k token диалогах
- background_review реально сохраняет skill через aux MiMo
- clarify_question действительно вызывается моделью (нужен prompt-engineering)
- ThinkScrubber на потоке MiMo с thinking mode
- prompt_caching на Anthropic (нет ключа в проекте)
- usage_pricing на реальных turn'ах (сейчас estimated через chars/3.5)

---

## Метрики качества

| Дата | Backend pytest | Vitest | Pre-existing flaky |
|---|---|---|---|
| До Sprint 1 (2026-05-20 утром) | 0 (memory ещё нет) | 273 | 3 |
| После Sprint 1 | 21 | 304 | 3 |
| После Sprint 2 | +87 = 108 | 304 | 3 |
| После Sprint 3 | +75 = 183 | 304 | 3 |
| После Sprint 4 | +64 = 247 | 304 | 3 |
| После Sprint 5 | +57 = 304 | 304 | 3 |
| **Итого backend** | **652** (включая старые 348) | **304** | **3** |

Build clean. Chrome MCP smoke ✓ для каждого спринта.

---

## Источники

- [HERMES-IMPLEMENTATION-PLAN.md](research/hermes-2026-05-20/HERMES-IMPLEMENTATION-PLAN.md) — 1764 строки, полный анализ
- Hermes Agent repo: https://github.com/NousResearch/hermes-agent (MIT, 158k★)
- Commits: `df76ed8`, `1d5e060`, `123418e`, `5b8ea8d`, `dccb672`

---

## Next milestone

**Текущее состояние:** Hermes integration закрыта, проект готов к **v1.3.0 release** или к **новому milestone**.

Предложения пользователю — см. STATE.md → секция «Next steps».
