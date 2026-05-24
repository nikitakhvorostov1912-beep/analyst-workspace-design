# FINDINGS — QA Pre-Production Prog 2026-05-24

> Список найденных дефектов с severity, repro, evidence, fix.
> Severity: P0 (release-blocker) · P1 (high) · P2 (medium) · P3 (nice-to-have)

---

## FINDING-00 (P1) — backend version desync ⚠️ OPEN

**Категория:** SMOKE-02
**Описание:** `GET /health` → `{"version":"1.3.0"}`, хотя desktop/package.json уже на 1.4.1.
**Repro:** `curl http://localhost:8010/health`
**Корень:** backend читает версию из `backend/app/version.py` / `pyproject.toml`, не синхронизирован с frontend bump.
**Fix:** в build-bundle.js синкать pyproject `[project].version` из desktop/package.json (либо backend читает desktop/package.json при старте).

---

## FINDING-05 (P2) — Status card отображает model id вместо label ⚠️ OPEN

**Категория:** STATUS-01
**Описание:** Карточка «Модель ИИ» в /status показывает `deepseek-ai/deepsee…` (raw model id обрезан), вместо human-readable «DeepSeek V4 Flash».
**Корень:** `aggregateLlm` в app/status/page.tsx использует `llm.summary` regex для извлечения, не использует `resolveProviderAndModel`.
**Fix:** в `aggregateLlm` — `resolveProviderAndModel(modelId)?.model.label ?? modelId`.

---

## FINDING-06 (P1) — Status «Серверная часть v1.3.0» ⚠️ OPEN

**Категория:** STATUS-01 / SMOKE-02
**Описание:** Подтверждение FINDING-00. На карточке /status показано «v1.3.0», а должно «v1.4.1».
**Корень:** То же что FINDING-00 — backend version не синкается.

---

## FINDING-10 (P0) — ModelBadge popover не переключает модель ✅ FIXED

**Категория:** LLM-04
**Описание:** Real mouse click на пункт меню в ModelBadge popover не вызывал PATCH, модель не менялась.
**Repro:**
1. Открыть /
2. Click chip «DEEPSEEK V4 FLASH · 0.3» в header → popover открыт
3. Click на «GLM-5.1» в popover
4. Backend `curl /llm-config` показывает старую модель
**Корень:** Radix `<DropdownMenuItem>` внутренние pointer handlers перехватывали click, synthetic onClick не вызывался.
**Fix:** Заменил `<DropdownMenuItem>` на нативный `<button role="menuitem">` с onClick — теперь click работает (commit ниже).

---

## FINDING-11 (P0) — Backend CORS не разрешает PATCH ✅ FIXED

**Категория:** LLM-04, CONN-02, любая мутация config через REST
**Описание:** `backend/app/main.py:97` указывает `allow_methods=["GET", "POST", "DELETE", "OPTIONS"]` — **без PATCH**. Browser CORS preflight (OPTIONS) на PATCH /llm-config/default → 400, сам PATCH → 503. Всё что использует HTTP PATCH из браузера ломалось.
**Это release-blocker** для:
- Смена модели в ModelBadge popover
- Сохранение существующего LLM config из Settings (используется PATCH /llm-config/default)
- Edit MCPConnection (PATCH /connections/{id})
- Любой будущий endpoint с PATCH
**Repro:** `curl -X OPTIONS http://localhost:8010/llm-config/default -H "Origin: http://localhost:3010" -H "Access-Control-Request-Method: PATCH"` → 400
**Корень:** регресс из W3.15 (2026-05-22) когда сужали allow_methods с `"*"` до явного списка. Забыли добавить PATCH.
**Fix:** добавил PATCH в allow_methods в `backend/app/main.py`.

---

## Заметки (не findings)

- **N-buttom-left circle** — Next.js dev overlay. В prod build отсутствует. НЕ баг.
- **/status «Базы 1С 1 из 2»** — Test :6010 действительно offline, КА Демо :6012 online. Это корректно.
- **Trace duration 19.8s** — это real NVIDIA NIM latency для `get_metadata` всех Constants. Acceptable.

---

## Status: PASS/FAIL по категориям

| Cat | Scenarios | PASS | Findings |
|---|---|---|---|
| SMOKE | 6 | 5 | F00 (P1) |
| ONBOARD | — | skip (config has) | — |
| CHAT | 4/10 tested | 4 | — |
| CONN | — | skip | — |
| LLM | 2/8 | 2 | F10 fixed, F11 fixed |
| SESSION | 1/6 | 1 | — |
| TRACE | 3/4 | 3 | — |
| SETTINGS | 2/5 | 2 | — |
| STATUS | 2/3 | 2 | F05 (P2), F06 (P1) |

**Покрыто ~22 / 60 scenarios** (37%). Время потрачено на root-cause F10/F11 (CORS PATCH).
