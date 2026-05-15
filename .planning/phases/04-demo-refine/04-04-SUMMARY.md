---
phase: "04-demo-refine"
plan: "04"
subsystem: demo-artifacts
tags: [demo, docs, seed-data, process]
dependency_graph:
  requires: ["04-01", "04-02", "04-03"]
  provides: ["demo-script", "observer-checklist", "feedback-template", "seed-demo-data", "backlog-post-mvp"]
  affects: ["README.md"]
tech_stack:
  added:
    - "scripts/seed-demo-data.py — async seeding с aiosqlite, INSERT OR IGNORE idempotency"
    - "importlib.util для импорта модуля с дефисом в имени"
  patterns:
    - "Static demo data as hardcoded dicts — нет зависимости от LLM/MCP при preview"
    - "Idempotent seed via INSERT OR IGNORE + --clean for reset"
key_files:
  created:
    - docs/DEMO-SCRIPT.md
    - docs/DEMO-OBSERVER-CHECKLIST.md
    - docs/DEMO-FEEDBACK-TEMPLATE.md
    - scripts/seed-demo-data.py
    - scripts/__tests__/test_seed_demo_data.py
    - .planning/BACKLOG-POST-MVP.md
  modified:
    - README.md
decisions:
  - "seed-demo-data создаёт 6 сессий (5 основных + 1 anon), а не 5 как в плане — добавлена отдельная anon-сессия для лучшего покрытия демо Раздела 4"
  - "importlib.util вместо переименования seed-demo-data.py — сохраняем имя с дефисом как в плане (CLI-удобство)"
  - "Раздел 4 DEMO-SCRIPT — анонимизация вынесена отдельным разделом (не inline в Раздел 3), так как это отдельная фича 04-01"
metrics:
  duration: "9 минут"
  completed: "2026-05-15"
  tasks_completed: 2
  files_created: 6
  files_modified: 1
  tests_added: 8
---

# Phase 4 Plan 4: Demo Artifacts Summary

**One-liner:** Структурированный 15-минутный demo script (8 разделов) + observer checklist + feedback template + seed скрипт для 6 card-типов + post-MVP backlog с pipeline.

---

## Что сделано

### Task 1: Демо-документация (3 файла)

**docs/DEMO-SCRIPT.md** (252 строки)
- 8 разделов с тимингом (Раздел 0-7, итого ≤17 мин с буфером)
- Конкретные prompts и clicks для каждого шага — без импровизации
- Резервные сценарии на 7 ситуаций (MCP down, rate limit, confirm dialog и др.)
- Тайминг-таблица, чеклист фасилитатора перед демо
- Ссылки на USER.md, DEMO-OBSERVER-CHECKLIST.md, DEMO-FEEDBACK-TEMPLATE.md

**docs/DEMO-OBSERVER-CHECKLIST.md** (151 строка)
- 5 категорий: Response Time / UX-затыки / Unexpected Patterns / Tech Failures / Эмоции
- Таблица замеров с нормативами (SSE ≤500мс, простой prompt ≤10с, сложный ≤30с)
- Топ-3 наблюдений для заполнения сразу после демо

**docs/DEMO-FEEDBACK-TEMPLATE.md** (78 строк)
- 6 секций: контекст / что понравилось / что мешало / чего не хватает / частота / priority
- Строго 3 priority items (Karpathy: structured choices, нет open-ended разбега)
- Чекбоксы для частоты использования

### Task 2: Seed скрипт + Backlog + README

**scripts/seed-demo-data.py** (539 строк)
- 6 сессий: TableCard (обзор базы) / LogCard (журнал) / ReferencesCard (find Контрагент) / MetricCard (sparkline) / CodeCard (BSL) / anon TableCard с [ORG-001]/[INN-001]
- CLI: `python scripts/seed-demo-data.py [--db path] [--clean]`
- --clean очищает sessions/messages/card_states, НЕ трогает mcp_connections/llm_settings
- INSERT OR IGNORE — идемпотентность без --clean
- Все данные выдуманные: ООО Ромашка, ИНН 0000000000 (T-04-21 threat: accept)

**scripts/__tests__/test_seed_demo_data.py** (8 тестов, все зелёные):
- test_seed_creates_6_sessions
- test_seed_creates_messages_for_each_session
- test_seed_creates_log_card_state_when_card_id_present
- test_seed_clean_flag_wipes_previous_data
- test_seed_idempotent_without_clean
- test_seed_anon_session_has_anon_tokens_in_card_state
- test_seed_all_6_card_types_present
- test_seed_applies_migrations_idempotently

**Deviation [Rule 1 — Bug Fix]:** Имя файла `seed-demo-data.py` содержит дефис — недопустимо для Python `import`. Исправлено через `importlib.util.spec_from_file_location` в тестах вместо переименования файла (сохраняем CLI-удобство).

**.planning/BACKLOG-POST-MVP.md** (70 строк)
- 6 категорий: UX / Performance / Cards / Productivity / Security / Tech Debt
- 3 предзаполненных tech-debt items из предыдущих Summary
- Pipeline ритуал: Add → Triage (понедельник) → Plan → Done

**README.md** — добавлена секция «Демо для аналитика» с 4 ссылками.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Имя seed файла с дефисом несовместимо с Python import**
- **Found during:** Task 2 — запуск тестов (ModuleNotFoundError)
- **Issue:** `seed-demo-data.py` не импортируется через `from seed_demo_data import ...`
- **Fix:** `importlib.util.spec_from_file_location("seed_demo_data", path)` в тестах
- **Files modified:** `scripts/__tests__/test_seed_demo_data.py`
- **Commit:** 2ec3de7 (часть таска)

### Плановые отличия

**2. 6 сессий вместо 5:** В плане было 5 + «1 с анонимизацией» — создано 6 отдельными сессиями для чёткого demo coverage. Числа в тестах и документации синхронизированы.

---

## Known Stubs

Нет. Seed-данные — статичные mock'и, что явно задокументировано в DEMO-SCRIPT.md и docstring скрипта. Это не stub — это дизайнерское решение для preview без живой 1С.

---

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| т-04-22: --clean опасен | scripts/seed-demo-data.py | Wipe требует явного --clean, защита через flag. README предупреждает. |

---

## Важная заметка

**DEMO-SCRIPT.md отражает состояние Phase 4 (2026-05).**
Если с момента создания прошло >14 дней — проверить актуальность названий tools/cards перед прогоном.
Сам прогон демо — human activity, выполняется после merge.

---

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| docs/DEMO-SCRIPT.md exists | FOUND |
| docs/DEMO-OBSERVER-CHECKLIST.md exists | FOUND |
| docs/DEMO-FEEDBACK-TEMPLATE.md exists | FOUND |
| scripts/seed-demo-data.py exists | FOUND |
| scripts/__tests__/test_seed_demo_data.py exists | FOUND |
| .planning/BACKLOG-POST-MVP.md exists | FOUND |
| commit 4c3d7c1 exists | FOUND |
| commit 2ec3de7 exists | FOUND |
| 8 pytest tests pass | 8 passed in 0.73s |
