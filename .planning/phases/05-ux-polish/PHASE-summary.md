---
phase: 05-ux-polish
status: planned
created: 2026-05-15
mode: mvp
granularity: coarse
plans: 5
waves: 3
requirements: [UX-01, UX-02, UX-03, UX-04, UX-05]
---

# Phase 5: Полировка UX до готового продукта — Plan Overview

## Phase Goal (User Story)

**As a** developer (Никита), **I want to** клонировать репозиторий, запустить `docker compose up`, открыть `http://localhost:3010` и за <90 секунд пройти onboarding → задать первый вопрос **so that** MVP становится готовым продуктом, которым можно пользоваться без чтения USER.md и ручного CRUD через curl.

## Phase Boundary

Phase 5 **закрывает** UX-затыки, обнаруженные при manual smoke после Phase 4:
- `/settings` был stub с надписью «Phase 2 stub» (4 фазы спустя)
- `getMCPConnections()` читал localStorage, `/connections` API в backend — два источника истины
- Empty state без пошагового onboarding
- `pnpm dev` падал на CSP headers (inline fix перед Phase 5, закрепляется тестом)

Phase 5 **не делает** v2 фичи (multi-profile LLM, smart discovery, presets, API key recovery).

---

## Plan Set

| Plan | Goal | Requirements | Tasks | Wave | Depends on |
|------|------|--------------|-------|------|------------|
| **05-01** | Backend LLM CRUD endpoints (`/llm-config` GET/POST/PATCH/DELETE/test) + frontend API client | UX-04 | 3 | 1 | — |
| **05-02** | Settings UI CRUD: реальный CRUD для MCP + LLM (компоненты MCPConnectionForm, MCPConnectionList, LLMConfigForm); zod валидация; sessionStorage для api_key | UX-02, UX-03 | 3 | 2 | 05-01 |
| **05-03** | First-Run Onboarding wizard (3 шага через модалку) — переиспользует формы Plan 5.2 | UX-01 | 3 | 2 | 05-01, 05-02 |
| **05-04** | page.tsx + ChannelSelector + AssistantMessage + Input + ModelBadge: backend как source-of-truth; @deprecated маркеры в storage.ts; legacy api_key migration | UX-04 | 3 | 3 | 05-01, 05-02, 05-03 |
| **05-05** | E2E Playwright (onboarding + settings-crud), README/USER обновление, final verification, git tag v1.0 | UX-05 | 3 | 3 | 05-01..04 |

**Total:** 5 plans, 15 tasks, 3 waves.

---

## Wave Structure (parallelism map)

```
Wave 1 (start)
└── 05-01 (Backend LLM CRUD)        — изолирован, новый router

Wave 2 (after 05-01)
├── 05-02 (Settings UI CRUD)        — реализует формы для UI
└── 05-03 (Onboarding wizard)       — переиспользует формы 05-02
                                       SEQUENTIAL: 05-02 завершить ДО 05-03
                                       (05-03 импортирует MCPConnectionForm/LLMConfigForm)

Wave 3 (after 05-01..03)
├── 05-04 (Source-of-truth migration) — обновляет 7 файлов; меняет API fetchChat
└── 05-05 (Verification + Release)  — финальный gate; зависит от 05-04
                                       SEQUENTIAL: 05-04 → 05-05
```

**Critical path:** 05-01 → 05-02 → 05-03 → 05-04 → 05-05 (sequential due to dependency chain).

**Parallelism opportunity:** внутри 05-02 task 1 (zod + shadcn install) можно делать пока 05-01 еще тестируется. Но для clarity и соблюдения wave-фрейминга — выполнять wave-by-wave.

---

## Requirements Coverage (UX-01..05)

| Requirement | Plan | Verification |
|-------------|------|--------------|
| **UX-01** First-run onboarding wizard | 05-03 | E2E `onboarding.spec.ts` (Plan 05-05); 9 unit-тестов OnboardingDialog |
| **UX-02** Settings → MCP CRUD UI | 05-02 | E2E `settings-crud.spec.ts`; unit-тесты MCPConnectionForm/List |
| **UX-03** Settings → LLM CRUD UI | 05-02 | E2E `settings-crud.spec.ts`; unit-тесты LLMConfigForm |
| **UX-04** Backend = source-of-truth | 05-01 + 05-04 | Manual smoke (curl POST → refresh → empty state пропадает); 13 backend тестов test_llm_config_route.py |
| **UX-05** Dev mode launch без ошибок | 05-05 | E2E covers full flow; `pnpm build` + `pnpm dev` smoke в verification gate |

**Coverage: 5/5.** Каждый UX-id маппится минимум в один плана `requirements` frontmatter и закрывается verification в Plan 05-05.

---

## Multi-Source Coverage Audit

### Source: GOAL (ROADMAP.md Phase 5)
| Item | Status | Plan |
|------|--------|------|
| `pnpm dev` запускается без ошибок dev mode | COVERED | 05-05 (gate 8) |
| First-run experience за 3 клика | COVERED | 05-03 |
| `/settings` — полноценный CRUD UI | COVERED | 05-02 |
| Source of truth = backend `/connections` API | COVERED | 05-01 + 05-04 |
| Empty state с понятным CTA «Шаг 1...3» | COVERED | 05-03 (внутри onboarding); 05-04 (для legacy empty state) |

### Source: REQ (REQUIREMENTS.md UX-01..05)
| Item | Status | Plan |
|------|--------|------|
| UX-01..05 | COVERED | См. таблицу выше |

### Source: RESEARCH (RESEARCH.md)
Phase 5 не имеет отдельного RESEARCH.md — Phase 5 директива через CONTEXT.md без research-этапа (direct extraction yolo per CONTEXT.md строка 5).

### Source: CONTEXT (CONTEXT.md decisions)
| D-ID | Decision | Covered by |
|------|----------|------------|
| Plan 5.1 — Backend LLM CRUD endpoints | COVERED | 05-01 |
| Plan 5.1 — api_key в frontend memory, NOT backend | COVERED | 05-01 (нет api_key в LLMConfigResponse) + 05-02 (sessionStorage) |
| Plan 5.1 — Migration v6 не нужна | COVERED | 05-01 (UPSERT по id=1) |
| Plan 5.2 — controlled inputs + zod (без react-hook-form) | COVERED | 05-02 task 2 |
| Plan 5.2 — sessionStorage api_key | COVERED | 05-02 lib/api-keys.ts |
| Plan 5.2 — shadcn Slider + AlertDialog | COVERED | 05-02 task 1 |
| Plan 5.3 — Detection: empty backend + флаг !== "true" | COVERED | 05-03 (page.tsx useEffect) |
| Plan 5.3 — 3 шага с прогресс-индикатором | COVERED | 05-03 StepIndicator |
| Plan 5.3 — Кнопка «Пропустить» на любом шаге | COVERED | 05-03 task 2 |
| Plan 5.3 — Test обязателен (gate Далее) | COVERED | 05-03 ping/test passed gate |
| Plan 5.4 — getMCPConnections/getLLMConfig @deprecated | COVERED | 05-04 task 1 |
| Plan 5.4 — hasConfig из backend | COVERED | 05-04 task 2 |
| Plan 5.4 — fetchChat использует getLLMApiKey | COVERED | 05-04 task 1 |
| Plan 5.5 — E2E Playwright onboarding + CRUD | COVERED | 05-05 task 1 |
| Plan 5.5 — README/USER update | COVERED | 05-05 task 2 |
| Plan 5.5 — git tag v1.0 | COVERED | 05-05 task 3 |
| Out-of-scope: Multi-profile LLM | EXCLUDED (deferred) | — |
| Out-of-scope: Smart discovery | EXCLUDED (deferred) | — |
| Out-of-scope: Provider presets | EXCLUDED (deferred) | — |
| Out-of-scope: API key recovery | EXCLUDED (deferred) | — |
| Out-of-scope: Settings history/undo | EXCLUDED (deferred) | — |
| Discretion: onboarding modal layout (Dialog без отдельной страницы) | COVERED | 05-03 (shadcn Dialog) |
| Discretion: default endpoints в placeholders | COVERED | 05-02 LLMConfigForm + 05-03 OnboardingDialog |
| Discretion: api_key в sessionStorage vs React state | COVERED (sessionStorage) | 05-02 |
| Discretion: localStorage backward compat — legacy migration | COVERED | 05-04 task 1 (migrateLegacyApiKey) |

**Audit result: ALL items COVERED or explicitly EXCLUDED as v2/deferred.** No silent gaps.

---

## Files Modified (Aggregated)

### Backend (Plan 05-01)
- `backend/app/models.py` (5 новых моделей)
- `backend/app/routes/llm_config.py` (новый router)
- `backend/app/main.py` (include_router)
- `backend/tests/test_llm_config_route.py` (новый файл)

### Frontend lib (Plans 05-01, 05-02, 05-03, 05-04)
- `frontend/lib/api.ts` (5 новых функций; fetchChat signature change)
- `frontend/lib/types.ts` (LLM config types)
- `frontend/lib/form-schemas.ts` (новый)
- `frontend/lib/api-keys.ts` (новый, sessionStorage)
- `frontend/lib/onboarding-flag.ts` (новый)
- `frontend/lib/storage.ts` (@deprecated маркеры)

### Frontend components (Plans 05-02, 05-03, 05-04)
- `frontend/components/settings/MCPConnectionForm.tsx` (новый)
- `frontend/components/settings/MCPConnectionList.tsx` (новый)
- `frontend/components/settings/LLMConfigForm.tsx` (новый)
- `frontend/components/onboarding/OnboardingDialog.tsx` (новый)
- `frontend/components/onboarding/StepIndicator.tsx` (новый)
- `frontend/components/ui/slider.tsx` (shadcn add)
- `frontend/components/ui/alert-dialog.tsx` (shadcn add)
- `frontend/components/ui/dialog.tsx` (shadcn add, если отсутствует)
- `frontend/components/chat/Input.tsx` (sessionStorage check)
- `frontend/components/chat/AssistantMessage.tsx` (legacy comment)
- `frontend/components/shell/ModelBadge.tsx` (async fetchLLMConfig)
- `frontend/components/shell/ChannelSelector.tsx` (legacy fallback comment)

### Frontend pages (Plans 05-02, 05-03, 05-04)
- `frontend/app/settings/page.tsx` (полная переписка)
- `frontend/app/page.tsx` (backend-driven hasConfig + onboarding)
- `frontend/app/sessions/[id]/page.tsx` (fetchConnections async)

### Tests (Plans 05-01, 05-02, 05-03, 05-04, 05-05)
- `backend/tests/test_llm_config_route.py` (13 тестов)
- `frontend/components/settings/__tests__/*` (3 файла, ≥10 тестов)
- `frontend/components/onboarding/__tests__/OnboardingDialog.test.tsx` (≥9 тестов)
- `frontend/components/chat/__tests__/useChatStream.test.tsx` (адаптация)
- `frontend/components/cards/__tests__/ChannelSelector.test.tsx` (адаптация)
- `frontend/e2e/onboarding.spec.ts` (новый, 4 теста)
- `frontend/e2e/settings-crud.spec.ts` (новый, ≥6 тестов)
- `frontend/e2e/mocks/onboarding-handlers.ts` (новый)

### Docs (Plan 05-05)
- `README.md` (quick start update)
- `USER.md` (FAQ update)

### Planning (Plan 05-05)
- `.planning/phases/05-ux-polish/05-VERIFICATION.md` (новый)
- `.planning/STATE.md` (Phase 5 Completed)
- `.planning/REQUIREMENTS.md` (UX-01..05 Done)

**Total files affected: ~30.** Преимущественно frontend (Phase 5 — UX-фаза).

---

## Verification Gate (Phase 5 acceptance)

5 truths из ROADMAP Phase 5 Success Criteria:

| # | Truth | How verified |
|---|-------|--------------|
| 1 | `pnpm dev` запускается без ошибок dev mode | Plan 05-05 gate 8: `pnpm dev` + curl HTTP 200 + `<title>` присутствует |
| 2 | First-run за <90 сек: пустая БД → onboarding → 3 шага → готов | Plan 05-05 E2E `onboarding.spec.ts` measures elapsed time |
| 3 | `/settings` — полноценный CRUD UI | Plan 05-05 E2E `settings-crud.spec.ts` |
| 4 | localStorage НЕ source-of-truth для MCP/LLM | Plan 05-04 + manual smoke: curl POST /connections → refresh → empty state пропадает |
| 5 | Git tag `v1.0` создан | Plan 05-05 task 3 + `git tag --list \| grep v1.0` |

**All 5 truths must PASS for Phase 5 acceptance.**

---

## Known Risks

| Risk | Mitigation Plan |
|------|-----------------|
| **R1:** fetchChat signature change (05-04) ломает useChatStream тесты | Plan 05-04 task 3 итеративно адаптирует тесты до зелёного |
| **R2:** Pre-existing 11 failed useChatStream тестов с Phase 4 | Phase 5 не пытается их чинить; baseline 181/192 passed сохраняется |
| **R3:** shadcn `pnpm dlx` интерактивность | Plan 05-02/05-03 fallback — копировать components вручную из docs |
| **R4:** Playwright `getByLabel` mismatches с label-ами форм | Plan 05-05 task 1 итеративно правит locators |
| **R5:** `git tag v1.0` локальный — push требует подтверждения пользователя | Plan 05-05 не пушит автоматически (per CLAUDE.md rule) |
| **R6:** Backend LLMClient API может отличаться | Plan 05-01 R3 — fallback на прямой httpx.AsyncClient.post если интерфейс не совпадает |
| **R7:** `app/sessions/[id]/page.tsx` точные строки не прочитаны при планировании | Plan 05-04 task 2 R4 — обязательно Read перед изменением |
| **R8:** «Далее» gate в OnboardingDialog шаг 2 опирается на Save, не на Test | Plan 05-03 R1 — hover-подсказка «Рекомендуется нажать Тест перед Сохранить»; альтернатива (onTested callback) расширяет API формы |

---

## Out-of-Scope (deferred to v2)

- Multi-profile LLM (несколько конфигов одновременно)
- Smart connection discovery (auto-scan localhost :6010 / :6003)
- LLM provider presets (OpenAI / Anthropic / Xiaomi MiMo)
- API key recovery / encrypted persistent storage
- Settings history / undo
- Migration v6 (не нужна — `llm_settings` уже создана в Phase 1)
- react-hook-form (overkill для 2 форм)

Все out-of-scope items документированы в `BACKLOG-POST-MVP.md` (Phase 4 артефакт).

---

## Release readiness

После прохождения 5/5 verification gates Phase 5:
- Git tag `v1.0` создан локально
- README + USER updated
- E2E coverage ≥ Phase 4 (расширен onboarding + settings-crud spec)
- Документированы все decisions из CONTEXT.md

**Next steps after Phase 5:**
1. Push tag в remote (требует подтверждения пользователя)
2. v2 planning — multi-profile LLM, smart discovery (как отдельная фаза)
3. Demo Day с реальным аналитиком (Phase 4 артефакт DEMO-SCRIPT.md уже готов)

---

*Plan overview created: 2026-05-15*
*Phase 5 planning: yolo mode, MVP vertical slices, coarse granularity*
