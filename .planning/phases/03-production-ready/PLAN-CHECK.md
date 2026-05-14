# Phase 3 Plan Check Report

**Date:** 2026-05-14
**Reviewer:** gsd-plan-checker (sonnet)
**Initial verdict:** ISSUES_FOUND (3 blockers, 4 warnings)
**Post-fix verdict:** PASS_WITH_NOTES (0 blockers, 4 warnings)

---

## Blockers (исправлены инлайн перед execute)

### BLOCKER 1: REQUIREMENTS.md vs ROADMAP.md рассинхронизация
- **Проблема:** SEC-01..04 и DEVX-01..05 находились в секции `## v2 Requirements`, но ROADMAP.md и все 4 плана Phase 3 их закрывают
- **Fix:** Перемещены в `## v1 Requirements` как «Security (Phase 3)» и «DevX (Phase 3)»; traceability таблица расширена 9 строками
- **Verification:** REQUIREMENTS.md Coverage = 31/31 ✓

### BLOCKER 2: 03-03 неполный depends_on
- **Проблема:** `depends_on: ["03-01"]` не учитывал что 03-03 coverage gate ≥80% должен мерить кодовую базу ПОСЛЕ внедрения SEC из 03-02, а fixture `_reset_pending` ссылается на `safety._pending` из 03-02
- **Fix:** `depends_on: ["03-01", "03-02"]`
- **Verification:** `gsd-sdk query phase-plan-index "03"` должен показывать корректный wave dependency

### BLOCKER 3: 03-04 неполный files_modified
- **Проблема:** LogCard cursor-fetch требует prop chain `page → Thread → Message → AssistantMessage → CardRenderer → LogCard`, но `Thread.tsx`, `Message.tsx`, `app/sessions/[id]/page.tsx`, `app/page.tsx` не были в `files_modified`
- **Fix:** Добавлены 4 файла в `files_modified` плана 03-04
- **Verification:** load-more функция действительно достигает LogCard

---

## Warnings (документированы, не блокирующие — устраняются при execute)

### WARNING 1: Тройное изменение loop.py в 03-01 → 03-02 → 03-04
- Loop.py меняется в каждой волне. Risk регрессии при execute Wave 3.
- **Mitigation:** Executor Wave 3 обязан прочитать 03-01-SUMMARY и 03-02-SUMMARY перед редактированием loop.py; полный regression test run на pyproject.toml gate.

### WARNING 2: 03-03 routes coverage truth не верифицируется
- must_haves.truths упоминает routes ≥75%, но Action явно отказывается от gate в pyproject.toml.
- **Mitigation:** Executor может добавить опциональный second pytest run с `--cov=app/routes --cov-fail-under=75` либо убрать truth.

### WARNING 3: CI yml verify только парсит подстроки
- Task 3 проверяет наличие текста в `ci.yml`, фактический запуск на GitHub вне scope плана.
- **Mitigation:** Добавить минимальный `python -c "import yaml; yaml.safe_load(...)"` для синтаксической валидации.

### WARNING 4: single-worker requirement для safety._pending не в USER.md
- Module-level dict для async confirm требует `uvicorn --workers 1`. README предупредит, USER.md — нет.
- **Mitigation:** Executor добавит FAQ запись «Почему confirm dialog завис?» с указанием на single-worker.

---

## REQ Coverage (after fix)

| REQ | Plan | Task | Status |
|-----|------|------|--------|
| STATE-02 | 03-01 | 1 | Покрыто |
| STATE-03 | 03-01 | 1, 2 | Покрыто |
| TRACE-03 | 03-04 | 2 | Покрыто |
| SEC-01 | 03-02 | 1 | Покрыто |
| SEC-02 | 03-02 | 2 | Покрыто |
| SEC-03 | 03-02 | 1 | Покрыто |
| SEC-04 | 03-02 | 1 | Покрыто |
| DEVX-01 | 03-03 | 1 | Покрыто |
| DEVX-02 | 03-03 | 2 | Покрыто |
| DEVX-03 | 03-03 | 3 | Покрыто |
| DEVX-04 | 03-04 | 3 | Покрыто (README) |
| DEVX-05 | 03-04 | 3 | Покрыто (USER.md) |

**Coverage: 12/12 ✓** (после устранения BLOCKER 1)

---

## Wave-схема (после fix)

| Wave | Plans | Зависимости | Файлы пересечения |
|------|-------|-------------|-------------------|
| 1 | 03-01 | — | loop.py, events.py, types.ts, sse.ts |
| 2 | 03-02 → 03-03 | 03-02 ← [03-01]; 03-03 ← [03-01, 03-02] | 03-02 трогает loop.py (confirm branch); 03-03 пишет тесты с учётом полного кода |
| 3 | 03-04 | 03-04 ← [03-01, 03-02, 03-03] | loop.py третье изменение (card_state save); Thread/Message/page для prop chain |

---

## Final verdict

**PASS_WITH_NOTES** — все 3 blocker'а исправлены инлайн. 4 warning'а документированы и переданы executor'у как ordering constraints. Планы готовы к `/gsd:execute-phase 3`.

Wave 2 НЕ запускать чисто параллельно: сначала 03-02 (orchestrator модификации + frontend модал), затем 03-03 (тесты с учётом нового кода). 03-04 в Wave 3 после полного завершения Wave 2.
