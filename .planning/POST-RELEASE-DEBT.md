# Тех. долг после v1.3.0 — реестр для следующего spike

**Создан:** 2026-05-23 · **Закрыт по основным пунктам:** 2026-05-24
**Источник:** что не вошло в COMMERCE-PLAN-2026-05-23 как «critical для первой продажи»

## Сводка закрытия (2026-05-24)

| Пункт | Статус | Коммит |
|---|---|---|
| TD-1 | 🟡 Частично — `run_chat_loop` 870 → 689 строк (-181), цель ≤400 не достигнута | phase 1/2/3 step 1-3 |
| TD-2 | ✅ Done — orchestrator+clients coverage **88.1%** (выше target ≥60%) | существующая база |
| TD-3 | ✅ Done — 7/7 flaky починены (encoding + migration setup + race timeout) | `57fc20a`, `3075b26` |
| TD-4 | ✅ Done — 3 skipped E2E specs unskipped + fixtures расширены | `bd40d3d` |
| TD-5 | ✅ Done — ruff loop.py 35 → 8 (8 — E501 в SYSTEM_PROMPT контенте) | `260ad44` |
| TD-6 | ✅ Done — 5 cards уже через CardHeader, Metric+Chart намеренно не нуждаются | re-eval |
| TD-7 | ✅ Done — ToolTrace цветной accent per категории (mcp/memory/todo/clarify) | `94b7864` |
| TD-8 | ✅ N/A — react-window не используется, ResultSizeGate (P2.2) режет 500 строк | re-eval |

**Осталось только** TD-9..14 — архитектурное (по запросу клиентов).

Документ — НЕ план реализации, а **навигация** для следующих спайков. Каждая запись = одна потенциальная фокусная сессия.

---

## Приоритет 1 — короткий технический долг

### TD-1 · Decompose loop.py phase 2/3 (~6h)

**Состояние:** P1.2 phase 1 завершён (`469460c`) — 3 pure helper'а извлечены и покрыты юнит-тестами. `run_chat_loop` сейчас 812 строк. Цель ≤400 строк.

**Что осталось:**

1. **`_handle_internal_tool(...)`** — объединить memory_tool / clarify_tool / todo_tool ветки (run_chat_loop:953-1073, ~120 строк). Каждая ветка:
   - Сравнить tool_name с `is_*_tool` (memory/clarify/todo)
   - Dispatch через `dispatch_*_tool`
   - yield ToolResultEvent
   - Append в accumulated_tool_calls + messages
2. **`_handle_mcp_tool(...)`** — MCP path с retry / safety / result_gate (run_chat_loop:1075-1136, ~62 строки).
3. **`LoopContext` dataclass** — обернуть mutable state (messages, accumulated_*, budget, etc.) в один объект, передавать в helpers как ссылку.

**Риски:** medium-high. Внутренние ветки используют `yield format_sse(...)` — должны остаться async generators. LoopContext refactor может затронуть 30+ orchestrator-тестов.

**Стратегия:** делать в отдельной сессии 6-10h без UI работы параллельно. Атомарные коммиты по одному helper. После каждого — полный pytest backend.

---

### TD-2 · Coverage gap (26.58% aggregate → ≥60%) (~8h)

**Состояние:** агрегированное покрытие 26.58% (заявлялось 80% в STATE.md ранее — было неточно из-за legacy кода).

**Хот-spots с низким покрытием:**

| Модуль | Coverage | Приоритет |
|---|---|---|
| `app/orchestrator/loop.py` | ~11% | P1 (главный business logic) |
| `app/orchestrator/persistence.py` | ~13% | P1 |
| `app/orchestrator/cards.py` | ~25% | P2 |
| `app/clients/llm.py` | ~30% | P2 |
| `app/routes/sessions.py` | ~40% | P3 |

**Что делать:** unit-tests на critical paths. Не гнаться за 80% — целить в **критичные сценарии**: error handling, edge cases, security.

---

### TD-3 · Pre-existing flaky тесты (~3h)

7 тестов в `backend/tests/` фейлят на Windows-1251 / unicode console:

- `test_memory.py::test_markdown_store_*` (3 шт)
- `test_migrations_v5_backfill_messages_into_fts`
- `test_orchestrator_loop_confirm` (2 шт — pre-existing)
- `test_trajectory_handles_multimodal_content` (Windows console encoding)

**Что делать:** заменить `open()` без encoding на `encoding='utf-8'` явный. Эти тесты пишут русскоязычные строки в файлы — на Windows default cp1251.

---

### TD-4 · E2E spec coverage gaps (~5h)

3 ключевых пользовательских flow без E2E:
- `setup-and-prompt` (онбординг + первый запрос)
- `sessions-history` (история / load-more)
- `channel-switch` (multi-tenant)

**Что делать:** Playwright spec'и через `@playwright/test` с mock MCP + mock LLM. Реальные base не нужны.

---

### TD-5 · Ruff baseline cleanup в loop.py (~1h)

35 ошибок pre-existing:
- 23 × E402 — VISION_MODEL const между импортами (line 61)
- 8 × E501 — длинные строки (SYSTEM_PROMPT строки)
- 1 × I001 — unsorted imports
- 1 × F401 — unused import
- 1 × UP041 — timeout-error-alias
- 1 × UP042 — устранено в P4.2 commit (`StrEnum`)

**Что делать:** переместить VISION_MODEL вверх (до from-imports), убрать unused, отформатировать длинные SYSTEM_PROMPT строки. 30 минут работы, 0 функциональных изменений.

---

## Приоритет 2 — UX полировка

### TD-6 · 6 cards через CardHeader (~4h)

`CardHeader` компонент уже есть (Phase 11.4). Используется только в TableCard. Остаётся:
- ObjectCard
- LogCard
- MetricCard
- ReferencesCard
- CodeCard
- ChartCard

**Что даёт:** единый стиль шапки (title + action menu), меньше дублирования.

### TD-7 · ToolTrace visual upgrade (~3h)

Текущий ToolTrace — функциональный, но не «брутальный минимализм». Можно сделать:
- Цветной prefix per tool name (orange = MCP, blue = memory, etc.)
- Inline `→` показывающее цепочку
- Collapsed state с одной строкой summary

### TD-8 · TanStack Virtual в больших таблицах (~2h)

Сейчас `TableCard` с 100+ строк виртуализирован только в `react-window`. Миграция на `@tanstack/react-virtual` (v3) — современный API, лучше SSR support.

---

## Приоритет 3 — Архитектурные / large

### TD-9 · Cells + Reactive Graph (3 недели)

Из IDEAS-FROM-STACK: реактивная модель карточек. Большой invasive рефакторинг. Без гарантии adoption — пользователь может не заметить разницу. Откладываем до запроса от 3+ клиентов.

### TD-10 · Presidio PII Shield (1 неделя)

Анонимизация PII перед отправкой в LLM. **Не нужно если LLM в РФ (default Cloud.ru с 152-ФЗ)**. Только если клиент захочет US-based LLM (NVIDIA NIM по умолчанию — но клиент даст согласие на trans-border data).

### TD-11 · Langfuse observability (1 неделя)

Дашборды LLM trace / latency / cost. Нужен при 5+ корп-клиентах. Сейчас 0 клиентов — преждевременно.

### TD-12 · Microsoft DeepEval (1 неделя)

Автоматизированный quality benchmark для LLM модели. Полезно когда выбираем модель для нового клиента или сравниваем NVIDIA vs Cloud.ru vs прямой DeepSeek.

---

## Приоритет 4 — Distribution

### TD-13 · macOS / Linux installers

Сейчас только Windows NSIS. После первой РФ продажи может прилететь корп-клиент на Mac.

**Что нужно:**
- electron-builder DMG target для macOS
- AppImage / DEB для Linux
- CI matrix в `release.yml` для трёх OS
- Code signing per-OS (notarization для Mac)

**Бюджет:** ~10h после первого пилотного клиента.

### TD-14 · Standalone server installer

Сейчас Electron = клиент + backend в одном инсталляторе. Корп-клиент может захотеть:
- Backend как Windows Service / systemd на отдельном сервере
- Несколько desktop клиентов подключаются к одному backend
- LDAP/AD auth

**Бюджет:** ~20h. Только при первом entreprise запросе.

---

## Не делать вообще

- ❌ Mobile app — desktop-only продукт по дизайн-контракту
- ❌ Web SaaS hosted нами — клиенты хотят on-prem из-за 152-ФЗ
- ❌ Voice input — out of scope
- ❌ 1С Toolkit как часть нашего installer — он внешний, ставится отдельно

---

## Рекомендуемый порядок после v1.3.0

1. **Smoke v1.3.0** (P4.1) + Release notes + GitHub Release
2. **TD-3 Pre-existing flaky** (3h) — самый быстрый low-hanging fruit
3. **TD-1 Decompose loop.py phase 2/3** (6h) — закрытие P1.2
4. **TD-2 Coverage gap** (8h) — поверх задекомпозированного loop.py легче добавлять тесты
5. **TD-5 Ruff baseline** (1h) — заодно с TD-1
6. **TD-4 E2E spec gaps** (5h) — закрытие тестового долга
7. **Wait for first customer** — потом TD-6/7/8 (UX), затем TD-13/14 (distribution)
