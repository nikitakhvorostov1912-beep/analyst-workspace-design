# M-K0 — Stabilization: закрытие дыр перед Knowledge Layer

**Milestone:** M-K0 (PRE-Knowledge Layer)
**Срок:** 3-4 недели, до **20.06.2026**
**Parent plan:** `../../PLAN.md`
**Branch:** `feature/m-k0-stabilization`
**Источник findings:** `.planning/development-plan-2026-05-24/План_развития_1С_Аналитик_2026-05-24.xlsx`

---

## Цель милстоуна (одна фраза)

Закрыть 9 CRITICAL + 14 критичных HIGH из общего аудита (99 findings) ПЕРЕД  
стартом Knowledge Layer, чтобы фундамент был стабильным, безопасным и
коммерчески пригодным.

---

## Почему M-K0 ПЕРЕД M-K1

Если строить Knowledge Layer на нестабильном фундаменте:
- **SSRF (SEC-1)** — атакующий через MCP endpoint попадает в интранет → блок enterprise
- **SQLite single connection (PERF-1)** — Knowledge Layer добавляет heavy writes → deadlock при scale
- **LLMClient recreate (PERF-2)** — каждый tool call = 11 TCP handshakes → Knowledge Layer Diagnose с 10 шагами = 30+ сек overhead
- **`_pending` race (BE-1)** — multi-tenant scenarios сломаются → блок Team tier
- **God-function loop.py (ARCH-1)** — каждая новая Knowledge Layer integration увеличивает risk регрессий

Эти 5 пунктов **блокируют M-K3** (Knowledge Layer Behavioral). Лучше закрыть  
сейчас одним milestone, чем тушить пожары по ходу.

---

## Что входит — раскладка по wave'ам

### Wave 0: Security CRITICAL+HIGH (8 findings, ~5 дней)

Самый высокий приоритет — закрывает enterprise SOC review blockers.

| ID | Severity | Subject | Days |
|----|----------|---------|------|
| SEC-1 | **CRITICAL** | SSRF: валидация MCP endpoint (169.254.169.254, Redis, DNS rebinding) | 2 |
| SEC-2 | HIGH | Electron CSP + sandbox:true + webSecurity:true явно | 0.5 |
| SEC-3 | HIGH | Prompt injection: unicode normalize + history scan | 2 |
| SEC-4 | HIGH | SQL validator: WITH + RETURNING bypass | 0.5 |
| SEC-5 | HIGH | shell:open-path IPC path whitelist | 0.5 |
| SEC-6 | HIGH | CORS allow_headers wildcard → явный список | 0.5 |
| SEC-7 | HIGH | admin/reset rate-limit + CSRF | 0.5 |
| SEC-12 | LOW | X-LLM-API-Key deprecation deadline + warning header | 0.5 |

**Подытог Wave 0:** ~6.5 дней календарно, ~5 дней работы.

### Wave 1: Backend Quality CRITICAL+HIGH (6 findings, ~4 дня)

Закрывает race conditions и silent failures — обязательно перед M-K3.

| ID | Severity | Subject | Days |
|----|----------|---------|------|
| BE-1 | **CRITICAL** | `_pending` dict race condition (asyncio.Event loop affinity) | 2 |
| BE-2 | **CRITICAL** | `_run_auto_title` task без ссылки — утечка при disconnect | 0.5 |
| BE-3 | HIGH | Silent failures в loop.py (message_id='unknown' + logger.debug на error) | 0.5 |
| BE-4 | HIGH | CLARIFY registry leak при GeneratorExit | 0.5 |
| BE-5 | HIGH | `_TOOL_FOR_CARD_TYPE` теряет args при 2+ execute_query | 2 |
| BE-6 | HIGH | SQLite write contention — batch commit() | 2 |

**Подытог Wave 1:** ~7.5 дней. Эти задачи можно делать параллельно с Wave 0  
(разные файлы).

### Wave 2: Performance CRITICAL (3 findings, ~3 дня)

Прямой uplift latency end-to-end.

| ID | Severity | Subject | Days |
|----|----------|---------|------|
| PERF-1 | **CRITICAL** | Один SQLite connection на всё приложение → connection-aware | 2 |
| PERF-2 | **CRITICAL** | LLMClient recreate per iteration → reuse через try/finally на уровне loop | 0.5 |
| PERF-3 | HIGH | 2 HTTP roundtrip перед каждым сообщением → React Context cache | 0.5 |

**Подытог Wave 2:** ~3 дня.

### Wave 3: AI/Prompts CRITICAL (3 findings, ~2 дня)

Эти 3 — самые лёгкие из CRITICAL и качество AI взлетает.

| ID | Severity | Subject | Days |
|----|----------|---------|------|
| PROMPT-1 | **CRITICAL** | Нет few-shot tool decision tree → дрейф MiMo/R1 | 2 |
| PROMPT-2 | **CRITICAL** | Indirect prompt injection через tool_results | 0.5 |
| PROMPT-3 | **CRITICAL** | Memory recall не работает — нет trigger в SYSTEM_PROMPT | 0.5 |

**Подытог Wave 3:** ~3 дня.

### Wave 4: Frontend CRITICAL + критичный HIGH (3 findings, ~1.5 дня)

A11y и UX блокеры.

| ID | Severity | Subject | Days |
|----|----------|---------|------|
| FE-1 | **CRITICAL** | prefers-reduced-motion не отключает animate-fade-up (WCAG 2.3.1 A) | 0.5 |
| FE-3 | HIGH | --fg-4 контраст 3.33:1 на Sand light → не AA | 0.5 |
| FE-4 | HIGH | key={i} для attachments → артефакты превью | 0.5 |

**Подытог Wave 4:** ~1.5 дня.

### Wave 5: Architecture CRITICAL (2 findings, ~7 дней — самый дорогой)

Долгожданный decompose loop.py + чистка globals.

| ID | Severity | Subject | Days |
|----|----------|---------|------|
| ARCH-1 | HIGH | Завершить decompose run_chat_loop (688→≤400 строк, P1.2 phase 2/3) | 5 |
| ARCH-2 | HIGH | Module-level globals → contextvars (multi-tenant) | 2 |

**Подытог Wave 5:** ~7 дней.

**Решение:** ARCH-1 можно отложить и сделать частью M-K3 (когда Knowledge Layer  
интеграция в loop.py уже потребует чистоты). НО ARCH-2 (globals) — обязательно  
сейчас, иначе ARCH-1 будет ещё дороже потом.

→ **В M-K0 включаем ARCH-2 (2 дня). ARCH-1 переносим в M-K3.0 (preparatory phase).**

### Wave 6: Документация + DevOps критичный HIGH (3 findings, ~1.5 дня)

Гигиена + EV cert pipeline.

| ID | Severity | Subject | Days |
|----|----------|---------|------|
| DOC-1 | HIGH | ARCHITECTURE.md полная ревизия под M6/M7 + schema v3→v10 | 0.5 |
| DOC-2 | MEDIUM | STATE.md правка loop.py 1506 vs 689 | 0.5 |
| DEVOPS-1 | HIGH | EV/OV code signing — process initiation + GitHub Secrets ready | 0.5 |
| DEVOPS-5 | MEDIUM | Auto-update semver.gt check (downgrade attack) | 0.5 |

**Подытог Wave 6:** ~2 дня.

---

## Итоговая раскладка M-K0

| Wave | Findings | Days | % Total |
|------|----------|------|---------|
| Wave 0 — Security | 8 | 6.5 | 21% |
| Wave 1 — Backend Quality | 6 | 7.5 | 24% |
| Wave 2 — Performance | 3 | 3 | 10% |
| Wave 3 — AI/Prompts | 3 | 3 | 10% |
| Wave 4 — Frontend | 3 | 1.5 | 5% |
| Wave 5 — Architecture (только ARCH-2) | 1 | 2 | 6% |
| Wave 6 — Docs + DevOps | 4 | 2 | 6% |
| **Buffer + tests + review** | — | 5.5 | 18% |
| **ИТОГО** | **28** | **31 дня** | 100% |

**31 рабочий день ≈ 6 календарных недель** при последовательной работе.  
С параллелизацией waves 0+1+4+6 (разные файлы) можно сжать до **3-4 недель**.

---

## Definition of Done всего M-K0

- [ ] Все 9 CRITICAL findings из общего аудита закрыты (SEC-1, BE-1, BE-2,  
  PERF-1, PERF-2, PROMPT-1, PROMPT-2, PROMPT-3, FE-1)
- [ ] Закрыты HIGH security: SEC-2, SEC-3, SEC-4, SEC-5, SEC-6, SEC-7
- [ ] Закрыты HIGH backend: BE-3, BE-4, BE-5, BE-6
- [ ] Закрыты HIGH frontend: FE-3, FE-4
- [ ] Закрыта ARCH-2 (multi-tenant globals)
- [ ] Закрыты DOC-1, DEVOPS-1 (process), DEVOPS-5
- [ ] `pytest` все тесты зелёные (847+ → не меньше)
- [ ] `vitest` все тесты зелёные (323+ → не меньше)
- [ ] **Coverage real** через `pytest --cov=app` (не subset) — ≥ 60% общий
- [ ] Smoke на чистой Windows-VM проходит
- [ ] **Security re-audit** через `security-reviewer` agent — 0 CRITICAL, ≤ 2 HIGH
- [ ] CHANGELOG.md обновлён с разделом «M-K0 Stabilization»
- [ ] STATE.md обновлён, M-K0 closed, готовы к M-K1

---

## Phases внутри M-K0

```
Week 1 (параллельно):
├── M-K0.1 Security Wave 0    [5d]  ●○○○○○○○○ pending  (SEC-1..7, SEC-12)
└── M-K0.2 BE Wave 1          [4d]  ●○○○○○○○○ pending  (BE-1..6)

Week 2 (параллельно):
├── M-K0.3 Perf Wave 2        [3d]  ●○○○○○○○○ pending  (PERF-1..3)
├── M-K0.4 Prompts Wave 3     [3d]  ●○○○○○○○○ pending  (PROMPT-1..3)
└── M-K0.5 Frontend Wave 4    [1.5d] ●○○○○○○○○ pending  (FE-1, FE-3, FE-4)

Week 3:
├── M-K0.6 ARCH-2 globals     [2d]  ●○○○○○○○○ pending  (ARCH-2)
└── M-K0.7 Docs + DevOps      [2d]  ●○○○○○○○○ pending  (DOC-1, DOC-2, DEVOPS-1/5)

Week 3-4:
├── M-K0.8 Coverage push      [3d]  ●○○○○○○○○ pending  (real --cov=app до 60%+)
├── M-K0.9 Security re-audit  [1d]  ●○○○○○○○○ pending  (full security-reviewer прогон)
└── M-K0.10 SUMMARY + handoff [1d]  ●○○○○○○○○ pending  (CHANGELOG, STATE, M-K1 ready)
```

**Параллелизация:** M-K0.1 + M-K0.2 — разные файлы, можно одновременно.  
M-K0.3 + M-K0.4 + M-K0.5 — разные подсистемы, можно одновременно.

---

## Phase-by-phase: что конкретно делаем

### M-K0.1 — Security Wave 0

**Файлы изменяются:**
- `backend/app/routes/connections.py` (SSRF validate)
- `backend/app/clients/mcp.py` (SSRF guard)
- `desktop/main.js` (CSP + sandbox + IPC whitelist)
- `backend/app/memory/injection_scan.py` (unicode normalize)
- `backend/app/orchestrator/loop.py` (history scan)
- `backend/app/orchestrator/sql_validator.py` (WITH + RETURNING)
- `backend/app/main.py` (CORS allow_headers explicit list)
- `backend/app/routes/admin.py` (rate-limit + CSRF)
- `backend/app/routes/chat.py` (deprecation header)

**Тесты добавляются:**
- `tests/test_ssrf_validation.py` — 15+ test cases (private IPs, link-local, DNS rebinding)
- `tests/test_sql_validator_with.py` — bypass attempts через WITH/RETURNING
- `tests/test_unicode_injection.py` — homoglyphs

**Acceptance:**
- SSRF: `POST /connections {"endpoint": "http://169.254.169.254/"}` → 400
- CSP: chrome devtools показывает CSP header
- Sandbox: `process.sandboxed === true` в renderer
- Injection: `"Игнор" (с кириллической о)` → detected
- SQL: `WITH cte AS (INSERT...) SELECT...` → 400

**Estimate:** 5 дней.

### M-K0.2 — Backend Quality Wave 1

**Файлы изменяются:**
- `backend/app/orchestrator/safety.py` (_pending → contextvars или per-loop)
- `backend/app/orchestrator/clarify.py` (get_running_loop)
- `backend/app/orchestrator/loop.py` (_run_auto_title task ref, message_id error, CLARIFY try/finally, card_id matching)
- `backend/app/orchestrator/persistence.py` (batch commit)

**Тесты:**
- `tests/test_pending_concurrent.py` (multi-loop scenario)
- `tests/test_clarify_genexit_cleanup.py`
- `tests/test_card_id_matching_2queries.py`

**Acceptance:**
- Multi-worker pytest зелёный (`pytest -n 4`)
- Long disconnect scenario — no leak (memory profile)
- 2× execute_query в одном turn — карточки разные args

**Estimate:** 4 дня.

### M-K0.3 — Performance Wave 2

**Файлы изменяются:**
- `backend/app/storage/db.py` (connection pool / writer + readers)
- `backend/app/orchestrator/loop.py` (LLMClient reuse выше while)
- `frontend/components/chat/useChatStream.ts` (React Context для config/connections)
- `frontend/app/page.tsx` (provider setup)

**Тесты:**
- `tests/test_sqlite_pool.py` (concurrent writes)
- `tests/test_llm_client_reuse.py`
- `frontend/__tests__/useChatStream.test.tsx` (no double-fetch)

**Acceptance:**
- Concurrent 5 sessions × pytest 10 messages each — no deadlock
- 10-tool chain end-to-end: latency ≤ 15 сек (было 25-30)
- Send message: 1 fetch вместо 3

**Estimate:** 3 дня.

### M-K0.4 — AI/Prompts Wave 3

**Файлы изменяются:**
- `backend/app/orchestrator/loop.py` (SYSTEM_PROMPT — добавить few-shot, memory trigger, indirect injection guard)

**Тесты:**
- `tests/test_prompts_few_shot.py` (golden dataset из 10 вопросов)
- `tests/test_memory_recall.py`

**Acceptance:**
- Golden dataset accuracy: ≥ 80% (baseline measured)
- При первом запуске с pre-loaded MEMORY.md — LLM учитывает контент в 90% случаев
- Indirect injection (комментарий в 1С с «ignore...») не пробивает

**Estimate:** 3 дня.

### M-K0.5 — Frontend Wave 4

**Файлы изменяются:**
- `frontend/styles/design-tokens.css` (`@media (prefers-reduced-motion: reduce) *:not(.skeleton) { animation: none; }`)
- `frontend/styles/design-tokens.css` (`--fg-4` от 0.5 до 0.60 alpha)
- `frontend/components/chat/Input.tsx` (stable key для attachments)

**Тесты:**
- Playwright `e2e/a11y-reduced-motion.spec.ts` (с emulated `prefers-reduced-motion: reduce`)

**Acceptance:**
- WCAG 2.3.1 A pass через axe-core
- Контраст --fg-4 на Sand: ≥ 4.5:1
- 3 attachments, удалить 1-й, превью 2-3 корректны

**Estimate:** 1.5 дня.

### M-K0.6 — ARCH-2 globals → contextvars

**Файлы изменяются:**
- `backend/app/orchestrator/safety.py` (_pending → ContextVar или request-scoped store)
- `backend/app/orchestrator/interrupt.py` (set без threading.Lock)
- `backend/app/orchestrator/clarify.py` (per-loop futures)

**Тесты:**
- `tests/test_multi_loop_isolation.py`

**Acceptance:**
- `pytest -n 4` зелёный без flake
- Documented limits: «single-user per backend instance», явный assert в startup

**Estimate:** 2 дня.

### M-K0.7 — Docs + DevOps

**Файлы изменяются:**
- `ARCHITECTURE.md` (полная ревизия: schema v10, новые orchestrator/learning/memory модули, M6 Hermes)
- `.planning/STATE.md` (правка loop.py цифр)
- `desktop/main.js` (semver.gt check)
- `.github/workflows/release.yml` (GitHub Release publishing fix если нужно)
- Document процесса покупки EV cert (`docs/EV-CERT-PROCESS.md`)

**Acceptance:**
- ARCHITECTURE.md покрывает все 14k+ строк backend
- semver.gt блокирует downgrade
- EV cert process документирован для запуска

**Estimate:** 2 дня.

### M-K0.8 — Coverage push

**Действия:**
- Прогнать `pytest --cov=app --cov-report=html` (не subset)
- Идентифицировать модули с < 60%
- Добавить тесты на critical paths: routes/admin, routes/connections, attachments,  
  log_cards, search

**Acceptance:**
- Total coverage ≥ 60% (от текущего 26.58%)
- Critical paths ≥ 80%
- CI gate `--cov-fail-under=60`

**Estimate:** 3 дня.

### M-K0.9 — Security re-audit

**Действия:**
- Запустить `security-reviewer` агент на полный backend + desktop
- Проверить что 0 CRITICAL, ≤ 2 HIGH
- Если найдены новые — фиксить или явно отложить с обоснованием

**Acceptance:**
- Security report saved в `.planning/knowledge-layer-2026-05-24/phases/M-K0-stabilization/security-re-audit-2026-XX-XX.md`
- 0 CRITICAL, ≤ 2 HIGH

**Estimate:** 1 день.

### M-K0.10 — SUMMARY + handoff

**Файлы создаются:**
- `phases/M-K0-stabilization/SUMMARY.md`
- `phases/M-K0-stabilization/HANDOFF-to-M-K1.md`
- Обновление `STATE.md` (active = M-K1)
- Обновление `CHANGELOG.md` (раздел M-K0)
- Git tag `m-k0-complete`

**Acceptance:**
- Все DoD из общего списка выше — отмечены
- M-K1 готов к старту

**Estimate:** 1 день.

---

## Метрики успеха M-K0

| Метрика | Baseline | Target |
|---------|----------|--------|
| Backend test coverage (real, full) | 26.58% | ≥ 60% |
| Security re-audit CRITICAL | 1 (SEC-1) | 0 |
| Security re-audit HIGH | 6 | ≤ 2 |
| End-to-end latency (10-tool chain) | 25-30 сек | ≤ 15 сек |
| Concurrent writes deadlock rate | unknown (single conn) | 0 |
| WCAG 2.3.1 A pass | fail (12 components) | pass |
| Tool selection accuracy (golden dataset) | unknown | ≥ 80% |
| pytest -n 4 (parallel) | unknown | green |
| ARCHITECTURE.md актуальность | устарел на 2 milestone | актуален |

---

## Риски M-K0 и mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| ARCH-2 contextvars сломает что-то существующее | HIGH | Feature-flag rollout, A/B test через env var, rollback план |
| Decompose не делаем — но Knowledge Layer integration требует чистоты | MEDIUM | M-K3.0 preparatory phase для ARCH-1 (decompose perед M-K3) |
| EV cert процесс долгий (1-3 недели) | MEDIUM | Запустить в M-K0.7 параллельно с другими wave, ждать пока пройдут другие milestones |
| Coverage push выявит больше тех. долга | LOW | Допускаем: добавляем в backlog, в текущем M-K0 — только CRITICAL paths |
| Security re-audit найдёт новый CRITICAL | MEDIUM | Бюджет 2-3 дня в M-K0.9 на закрытие нового |
| Параллельная работа waves конфликтует | LOW | Каждая wave — свой sub-branch, merge в M-K0 branch по готовности |

---

## Что НЕ делаем в M-K0 (явно — backlog)

Из 99 общих findings — закрываем 28, остальные 71 откладываем:

- **MEDIUM/LOW backend** (BE-7..12) — параллельно с M-K1..M-K6, по 1 в неделю
- **MEDIUM/LOW perf** (PERF-4..12) — после Knowledge Layer когда видна real bottleneck
- **MEDIUM/LOW prompts** (PROMPT-4..15) — после Knowledge Layer integration
- **Frontend MEDIUM/LOW** (FE-5..11) — параллельно с UX задачами M-K3
- **All Testing audit (QA-1..6)** — параллельно, не блокеры
- **All DevOps (DEVOPS-2..8)** — после EV cert (M-K0.7)
- **All Product/GTM (PROD-1..6, GTM-1..5)** — закрываем перед commerce launch M-K3
- **All Compliance (COMP-1..3)** — closer to enterprise (M-K6)
- **MEDIUM/LOW security** (SEC-8..11, SEC-13) — параллельно, по приоритету

Все они в Excel `План_развития_1С_Аналитик_2026-05-24.xlsx` — оставлены  
с пустой колонкой «Комментарий пользователя» для приоритезации.

---

## Параллельность с другими треками

Во время M-K0 НЕ начинаем:
- ❌ M-K1 Knowledge Layer Foundation
- ❌ Новые feature requests из основного roadmap
- ❌ UI redesign / brand changes

ОК делать параллельно:
- ✅ Закрытие LOW findings из общего аудита (если не блокируют M-K0)
- ✅ Документация (помимо ARCHITECTURE.md в M-K0.7)
- ✅ Onboarding flow polish
- ✅ Telemetry/Sentry setup (DEVOPS-4) если есть свободное время

---

## После M-K0 — что в M-K1

См. `../M-K1/M-K1-PLAN.md`. Краткое напоминание:
- ADR-001/002/003 (vector DB, graph DB, embeddings)
- OPEN-VS-CLOSED.md
- `backend/app/knowledge/` skeleton
- Storage Layout
- Configuration Fingerprint
- Metadata Cache filler
- Object Dossier API + UC «расскажи про объект»

M-K0 → M-K1 transition должен быть **clean handoff** — после M-K0 фундамент  
стабильный, можно строить Knowledge Layer не оглядываясь на технический долг.

---

## История изменений M-K0-PLAN

- **2026-05-25**: Создан после решения «закрыть дыры первично перед Knowledge  
  Layer». Основа — 28 critical+high findings из общего аудита.
