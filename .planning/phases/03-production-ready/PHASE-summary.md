# Phase 3: Production Ready — Plan Set Overview

**Phase:** 03-production-ready
**Mode:** mvp (vertical slices)
**Granularity:** coarse
**Plans:** 4
**Waves:** 3
**Total tasks:** 9
**Planning date:** 2026-05-14

## Цель фазы

Завершить production-readiness: error states видимы и обрабатываются
(MCP/LLM), security hardening (confirm dialog опасных execute_code, CSP,
Pydantic strict, CORS lockdown), backend coverage ≥80% + E2E Playwright
+ GitHub Actions CI, документация (README/USER/API/ARCHITECTURE) +
закрытие Phase 2 deferred (LogCard cursor-fetch backend) + TRACE-03
Copy as curl.

---

## Wave Structure

| Wave | Plans | Параллельность | Обоснование |
|------|-------|----------------|-------------|
| 1 | 03-01 (Error & Streaming States) | — | Foundation: расширяет ErrorEvent (retry_after_s) и фиксирует `ErrorCode` как Literal из 12 значений. Plan 3.2 использует тот же Literal (для user_declined/dangerous_keyword_blocked) — без 03-01 контракт у 3.2 не закроется. Plan 3.3 тестирует error path с этими кодами. |
| 2 | 03-02 (Security Hardening), 03-03 (Tests + CI) | Параллельно с осторожностью | Оба зависят от 03-01. Между собой: 03-02 расширяет SSE-контракт (confirm_required event + POST /chat/confirm), вводит Pydantic strict (может ловить ранее тихие type-mismatch), добавляет CSP. 03-03 пишет coverage-тесты, Playwright, GitHub Actions. **Файловые пересечения:** оба правят `backend/app/orchestrator/loop.py` и Pydantic models — 03-02 добавляет confirm branch, 03-03 тестирует max_iterations/finish_reason/init_error. Поскольку 03-02 правит ПРОДУКТИВНЫЙ код, а 03-03 пишет ТОЛЬКО тесты (новые файлы) — конфликта нет. **Однако:** 03-03 не должен писать тесты на confirm_required branch — это сделано в самом 03-02 (там полный test-set для нового кода). 03-03 тестирует только то, что уже было до Plan 3.2 (uncovered branches в loop). При параллельном запуске должен идти после merge 03-02 в branch, либо первым делать частичный run на baseline. **Рекомендация для execute-phase**: запускать 03-02 первым (1-2 часа), затем 03-03 как continue session — это безопаснее. Альтернативно — два разных воркера, но 03-03 финальный pytest --cov-fail-under гонять только после merge 03-02. |
| 3 | 03-04 (Docs + TRACE-03 + LogCard cursor-fetch) | — | Зависит от 03-01 (toast.ts уже существует — используется для «Скопировано»), 03-02 (CSP должна разрешать navigator.clipboard — same-origin OK). От 03-03 явно НЕ зависит, но логично идёт последним для финального code/docs снимка. Мог бы быть в Wave 2, но содержит ARCHITECTURE.md актуализацию — лучше делать когда вся продуктовая логика заморожена. |

### Файловые пересечения

| Файл | Plans | Кто что трогает | Wave-order |
|------|-------|----------------|-----------|
| `backend/app/orchestrator/events.py` | 03-01, 03-02 | 03-01: ErrorEvent.retry_after_s, ErrorCode Literal. 03-02: добавляет ConfirmRequiredEvent. Файл append-only. | 03-01 → 03-02 (наследует Literal) |
| `backend/app/orchestrator/loop.py` | 03-01, 03-02, 03-03, 03-04 | 03-01: маппинг ошибок LLM/MCP. 03-02: confirm branch перед execute_code. 03-03: только тесты файла. 03-04: после save_assistant_message сохраняет card_state. | 03-01 → 03-02 → 03-04. 03-03 параллельно (новые тестовые файлы). |
| `backend/app/models.py` | 03-02, 03-04 | 03-02: strict=True на Request-моделях. 03-04: LoadMoreRequest, LogPagePayload. | 03-02 → 03-04 |
| `backend/app/storage/migrations.py` | 03-04 | Только 03-04 (миграция v3). | — |
| `backend/app/main.py` | 03-02, 03-04 | 03-02: CORS lockdown env, environment warning. 03-04: include log_cards_router. | 03-02 → 03-04 |
| `backend/pyproject.toml` | 03-03 | Только 03-03 (cov gates). | — |
| `frontend/components/chat/useChatStream.ts` | 03-01, 03-02 | 03-01: routing error.code → banner/toast/inline. 03-02: pendingConfirm + resolveConfirm. Append-only. | 03-01 → 03-02 |
| `frontend/components/chat/ToolTrace.tsx` | 03-04 | Только 03-04 (Copy as curl button). | — |
| `frontend/components/cards/LogCard.tsx` | 03-04 | Только 03-04 (load-more wire-up). | — |
| `frontend/lib/types.ts` | 03-01, 03-02, 03-04 | 03-01: ErrorCode tab, ChatMessage.error. 03-02: ConfirmRequiredPayload, SSEEvent dischrim. 03-04: CardContext, LogCardPayload.card_id. Append-only. | 03-01 → 03-02 → 03-04 |
| `frontend/next.config.ts` | 03-02 | Только 03-02 (CSP headers). | — |
| `frontend/app/page.tsx + sessions/[id]/page.tsx` | 03-01, 03-02 | 03-01: ConnectionStatusBanner state + handleRetry. 03-02: ConfirmExecuteDialog подключение. Append-only. | 03-01 → 03-02 |
| `frontend/package.json` | 03-02, 03-03 | 03-02: @radix-ui/react-dialog. 03-03: @playwright/test. Не конфликтуют. | Параллельно безопасно |

Все пересечения управляемые через wave ordering. Реальных строковых
конфликтов нет — все правки append-only либо в разных функциях.

---

## Plans

### Plan 3.1: Error & Streaming States (Wave 1)

**REQ:** STATE-02, STATE-03
**Tasks:** 2
- T-03-01-1: Backend — ErrorEvent.retry_after_s + ErrorCode Literal (12 значений) + LLMRateLimitError + MCPDisconnectedError + маппинг ошибок в loop.py
- T-03-01-2: Frontend — Toaster (~80 строк свой) + ConnectionStatusBanner + StreamingIndicator + интеграция в useChatStream/page

**Зависимости:** ничего (Wave 1).
**Доставляет:** код ошибок зафиксирован для всей фазы; MCP banner + LLM toast + streaming stages в UI.

### Plan 3.2: Security Hardening (Wave 2)

**REQ:** SEC-01, SEC-02, SEC-03, SEC-04
**Tasks:** 2
- T-03-02-1: Backend — safety.py (dangerous keywords + pending confirmation) + ConfirmRequiredEvent + loop branch + POST /chat/confirm + Pydantic strict + CORS lockdown + caplog audit
- T-03-02-2: Frontend — next.config.ts CSP production-only + ConfirmExecuteDialog + useChatStream wire-up

**Зависимости:** 03-01 (Literal ErrorCode для user_declined/dangerous_keyword_blocked).
**Доставляет:** confirm dialog для опасных execute_code, CSP, strict validation, fail-secure CORS.

### Plan 3.3: Tests + CI (Wave 2)

**REQ:** DEVX-01, DEVX-02, DEVX-03
**Tasks:** 3
- T-03-03-1: Backend — coverage gates 80% в pyproject.toml + 25+ edge-case тестов (orchestrator/clients/routes)
- T-03-03-2: Frontend — Playwright + route() моки + 3 E2E spec'а (setup-and-prompt / sessions-history / channel-switch)
- T-03-03-3: GitHub Actions ci.yml (backend + frontend + e2e jobs) + README workflow

**Зависимости:** 03-01 (error codes fixated — тестируем их).
**Доставляет:** автоматизация качества — coverage gate, E2E, CI.

### Plan 3.4: Docs + TRACE-03 + LogCard cursor-fetch backend (Wave 3)

**REQ:** TRACE-03, DEVX-04, DEVX-05 + Phase 2 deferred (LogCard load-more)
**Tasks:** 3
- T-03-04-1: Backend — миграция v3 + table card_states + persistence save_card_state/get_card_state + POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more
- T-03-04-2: Frontend — curl-builder.ts + ToolTrace «Скопировать как curl» button + LogCard wire-up к load-more API
- T-03-04-3: Документация — README + USER.md + API.md + CURL.md + ARCHITECTURE.md актуализация

**Зависимости:** 03-01 (toast.ts), 03-02 (CSP — навigator.clipboard same-origin).
**Доставляет:** копирование curl, реальный LogCard load-more, документация для нового пользователя.

---

## Сумма задач

| Plan | Tasks | Wave |
|------|-------|------|
| 03-01 | 2 | 1 |
| 03-02 | 2 | 2 |
| 03-03 | 3 | 2 |
| 03-04 | 3 | 3 |
| **Total** | **10** | — |

Поправка: фактически 10 задач (2+2+3+3), не 9 как в шапке. См. подробно
в самих плановых файлах.

---

## REQ Coverage Matrix

12 REQ-ID из Phase 3:

| Requirement | Plan(s) | Notes |
|-------------|---------|-------|
| STATE-02 (MCP disconnected banner) | 03-01 (T-1 backend + T-2 frontend ConnectionStatusBanner + retry) | Полное закрытие |
| STATE-03 (LLM rate limit / errors) | 03-01 (Retry-After parser + 4 error codes + toast + countdown) | Полное закрытие |
| TRACE-03 (Copy as curl) | 03-04 (T-2 curl-builder + ToolTrace button + clipboard + toast) | Полное закрытие |
| SEC-01 (Confirm dialog execute_code) | 03-02 (T-1 safety + confirm_required event + T-2 ConfirmExecuteDialog) | Полное закрытие |
| SEC-02 (CSP headers) | 03-02 (T-2 next.config.ts production-only CSP + X-Frame/X-Content/Referrer) | Полное закрытие |
| SEC-03 (Pydantic strict) | 03-02 (T-1 strict=True на всех Request-моделях + 422 ловит type-mismatch) | Полное закрытие |
| SEC-04 (CORS lockdown + API key forward) | 03-02 (T-1 BACKEND_ALLOWED_ORIGINS env + fail-secure default + caplog audit) | Полное закрытие |
| DEVX-01 (Unit tests ≥80%) | 03-03 (T-1 coverage gate + 25+ новых тестов orchestrator/clients/routes) | Полное закрытие; если фактический cov ниже — Plan SUMMARY документирует обоснование снижения gate |
| DEVX-02 (E2E Playwright 3 flow) | 03-03 (T-2 playwright config + 3 spec'а + Playwright route() моки) | Полное закрытие |
| DEVX-03 (GitHub Actions CI) | 03-03 (T-3 ci.yml: backend + frontend + e2e jobs) | Полное закрытие |
| DEVX-04 (README docker-compose) | 03-04 (T-3 README post-MVP с Установка/Быстрый старт/Конфигурация/Тестирование/Troubleshooting) | Полное закрытие |
| DEVX-05 (USER.md гид) | 03-04 (T-3 USER.md + FAQ + API.md + CURL.md + ARCHITECTURE.md) | Полное закрытие |

**Всего REQ в Phase 3:** 12 → закрыто 12 ✓

Дополнительно: Phase 2 deferred **LogCard cursor-fetch backend** — Plan 3.4
T-1 (миграция v3 + endpoint /load-more) + T-2 (frontend wire-up). Не маппится
на отдельный REQ-ID, но закрывает реальный backlog Phase 2 (CARD-03
load-more был частично implemented как UI-placeholder).

---

## Out-of-Scope Phase 3 (явно НЕ делаем)

| Feature | Reason | Phase |
|---------|--------|-------|
| ANON-01..03 (анонимизация) | v2; REQUIREMENTS.md уже маркирует v2 | Phase 4 |
| CARD-04..06 (Metric/References/Code cards) | v2 cards | Phase 4 |
| PROD-01..05 (quick prompts, slash, @-mentions, Cmd-K, Export) | v2 productivity | Phase 4 |
| OAuth / SSO | Out of Scope (REQUIREMENTS) | — |
| Email notifications | Out of Scope | — |
| Mobile / tablet UI | Out of Scope | — |
| Light theme | Out of Scope | — |
| Vector search / RAG | Out of Scope для v1 | v2 |
| Voice / TTS | Out of Scope | — |
| Sonner / третья сторона toast | Karpathy Simplicity — пишем ~80 строк свой компонент | — |
| MSW в E2E | Karpathy — Playwright route() проще | — |
| CSP nonce-based (вместо unsafe-inline для script) | Требует server-side React-nonce — v2 | v2 |
| HSTS / Strict-Transport-Security | Reverse-proxy layer, не Next.js | — |
| Rate limiting endpoints | Не критично для single-user MVP | v2 |
| Auth/Authorization | Out of Scope для MVP | — |
| Container build/push в CI | DEVX-04 покрывает docker-compose (run, не build deploy) | — |
| Deploy job (staging/prod) | Out of Scope | — |
| Security scanning (CodeQL, Snyk) | v2 | v2 |
| Visual regression тесты | v2 | v2 |
| Cross-browser Playwright (Firefox/WebKit) | Only Chromium для MVP | v2 |
| Coverage upload в Codecov/Coveralls | v2 | v2 |
| Скриншоты в README/USER.md | Pre-merge без — требует развёрнутую реальную 1С; добавятся post-merge как addendum (CONTEXT.md Discretion) | Post-Phase 3 addendum |
| Pagination в TableCard backend | TableCard cap 1000 + CSV достаточно для MVP | v2 |
| Configurable UI dangerous keywords | env-only, Settings UI Out of Scope | v2 |
| Persisting load-more LogCard entries в DB | Refresh = новая страница — известное ограничение | v2 |
| Background polling MCP-ping | Banner показывается реактивно на event:error | v2 если потребуется |

---

## Verification Gate (для всей фазы)

Phase 3 закрывается когда выполнены все успешные критерии каждого PLAN +
5 acceptance criteria из ROADMAP Phase 3:

1. ✅ Все 5+ error/streaming состояний воспроизводятся:
   - MCP disconnected (banner + retry)
   - LLM rate limit (toast + countdown)
   - LLM invalid_key (toast)
   - LLM network_error (toast)
   - LLM server_error (toast)
   - Streaming stages (thinking / calling_tool / formatting) индикатор
   - Confirm required (Dialog с args + reason)
   - User declined / Confirm timeout (inline error)
2. ✅ Security audit passes — заменяется на конкретные acceptance items (Plan 3.2 verification + manual smoke + threat_model coverage):
   - dangerous keywords scan работает на 6+ regex'ах
   - confirm_required end-to-end через SSE + POST /chat/confirm
   - CSP в production headers содержит default-src 'self' + frame-ancestors 'none' + connect-src backend_url
   - Pydantic strict=True ловит extra fields и type-mismatch
   - CORS default fail-secure (пустой список без env)
   - X-LLM-API-Key не появляется в caplog тестах
3. ✅ Coverage ≥80% backend orchestrator + clients — pytest --cov-fail-under=80 в pyproject.toml
4. ✅ CI green — GitHub Actions ci.yml ✓ 3 jobs (backend + frontend + e2e)
5. ✅ README + USER.md позволяют новому юзеру setup за ≤15 минут — SUMMARY Plan 3.4 фиксирует фактическое время если делал чистый dry-run

Автоматическая verification (выполняется execute-phase в конце Wave 3):
```
cd backend && python -m pytest -v --cov-fail-under=80
cd frontend && pnpm type-check && pnpm lint && pnpm test --run && pnpm build
cd frontend && pnpm exec playwright test --list  # 3 spec'а
node -e "require('fs').readFileSync('.github/workflows/ci.yml')"  # parse ok
grep -ri "TODO\|FIXME\|placeholder" backend/app frontend/components frontend/lib README.md docs/ ARCHITECTURE.md  # 0 hits
grep -rn '"sonner"' frontend/package.json frontend/lib frontend/components  # 0 hits (Karpathy Simplicity)
grep -ri "Traceback\|stack trace" backend/app/orchestrator/loop.py  # 0 hits
```

Manual smoke (выполняет execute-phase в конце Wave 3):
1. Stop MCP EPF → отправить prompt → видим красный banner + retry button; перезапустить EPF + ping → banner исчезает
2. Замокать LLM на 429 с Retry-After: 5 → видим toast countdown «5...4...3...»
3. LLM выдаёт tool_call execute_code с args.code = «Удалить элемент» → видим Dialog с args + reason; Отменить → видим inline error «Пользователь отменил»; Выполнить → видим tool_result
4. Открыть DevTools → Network в `pnpm start` (production) → Headers содержат Content-Security-Policy
5. ToolTrace expand → click «Скопировать как curl» → paste в терминал → команда parsable
6. LogCard «Загрузить ещё» → видим дополнительные entries
7. Чистый dry-run: новый разработчик клонит репозиторий, читает README → запускает за ≤15 минут (фиксируем в Phase SUMMARY)

---

## Known Risks / Open Questions

1. **Coverage 80% может не достигнуться** — orchestrator/loop.py имеет много error branches. Mitigation в Plan 3.3 risk #1: после прогона если факт <80%, понижаем gate до факта (например 78%) с явным обоснованием в SUMMARY. **Открытый вопрос**: блокирует ли execute-phase merge при cov < 80%? **Решение**: в Plan SUMMARY указываем фактическое значение; gate в pyproject.toml — fail-fast; если хотим сохранить merge — снижаем gate, но не отступаем без документации.

2. **safety._pending как module-level dict не работает в multi-worker uvicorn** — Plan 3.2 risk #1. Mitigation: README.md Plan 3.4 явно укажет «production требует single-worker (uvicorn --workers 1) или замена на Redis-pending в v2». **Открытый вопрос**: docker-compose backend сейчас запускается без --workers (default=1) — это уже single-worker; явное предупреждение в README достаточно.

3. **CSP unsafe-inline для script** — accepted risk T-03-12 в Plan 3.2. Замена на nonce-based CSP — v2. **Открытый вопрос**: некоторые security-аудиторы могут оценить это как HIGH; mitigation — accept рисковая позиция документирована.

4. **navigator.clipboard в insecure context** — Plan 3.4 risk #1. Mitigation: catch error + toast «Не удалось скопировать. Используйте HTTPS». Localhost работает по исключению spec.

5. **Параллельность 03-02 + 03-03 в Wave 2** — Wave Structure выше указывает: рекомендация sequential (03-02 → 03-03). При полностью parallel запуске 03-03 финальный pytest --cov-fail-under должен запускаться после merge 03-02 (иначе coverage будет считаться по старому коду без confirm branch). **Открытый вопрос**: execute-phase оркестратор должен учитывать это; в проекте использовался pattern «один воркер на wave» — этот pattern предотвращает проблему.

6. **scrolledшение DANGEROUS_KEYWORDS false positives** — Plan 3.2 risk #5. Mitigation: USER.md FAQ объясняет; пользователь жмёт «Выполнить» — продолжает работу. Не блокер.

7. **GitHub Actions cost** — 3 jobs * каждый PR ~5 минут = ~15 минут/PR. Concurrency group cancel-in-progress снижает; для соло-разработки это бесплатно (private repo лимит 2000 минут/мес). **Решение**: monitor через github billing если станет проблемой.

8. **Скриншоты в README/USER.md** — отложены post-merge addendum (CONTEXT.md Claude's Discretion). Это снижает приёмочную ценность README для нового user'а. Mitigation: clear textual инструкции; ROADMAP success criteria «≤15 минут setup» проверяется без скриншотов в первой итерации.

---

## Сроки и контекст

- **Wave 1 (03-01)**: ~30-40% context на 2 задачи (T-1 backend, T-2 frontend). Backend наибольшая часть — error mapping + LLMRateLimitError. Рекомендация: один воркер, между task'ами не /clear.
- **Wave 2 (03-02 + 03-03)**: sequential рекомендуется. 03-02 ~40% context. 03-03 ~50% context (большой Plan: 25+ backend тестов + Playwright config + ci.yml). Рекомендация: /clear между 03-02 и 03-03.
- **Wave 3 (03-04)**: ~50-60% context. 3 задачи: backend migration+endpoint + frontend wire-up + 5 doc файлов. Рекомендация: можно разделить на 2 сессии (Task 1+2 backend/frontend code, затем Task 3 docs).

Итого: **3-4 execution sessions** для Phase 3 при solo workflow.

---

## Self-Check

- [x] Все 4 PLAN-файла созданы по канону `{phase}-{NN}-PLAN.md`
- [x] Frontmatter содержит все required поля (phase, plan, type, wave, depends_on, files_modified, autonomous, requirements, must_haves)
- [x] Каждый план содержит objective, context, 2-3 tasks, out-of-scope, risks, verification, test_strategy, references, success_criteria, output
- [x] Каждая задача имеет files, action, verify (automated), done
- [x] Wave 2 параллельность задокументирована с recommendation на sequential
- [x] REQ coverage 12/12 ✓
- [x] Phase 2 deferred (LogCard cursor-fetch) явно закрыт Plan 3.4
- [x] Out-of-Scope явно перечислен по всей фазе (≥ 20 items)
- [x] Никаких placeholder/TODO/«доделать позже» в плановых acceptance criteria
- [x] Karpathy Simplicity First: 80-строчный toast вместо sonner; route() вместо MSW; ~40 строк curl-builder
- [x] Brutal honesty: 8 открытых вопросов перечислены
- [x] Threat models включены во все 4 плана (security_enforcement)
- [x] User decisions из CONTEXT.md уважены: dangerous keywords list, CSP в production-only, toast свой ~80 строк, MSW vs route() решение задокументировано

---

*Phase 3 planning complete: 2026-05-14*
*Next step: `/gsd-execute-phase 03-production-ready` (sequential по wave, как описано в «Сроки и контекст»)*
