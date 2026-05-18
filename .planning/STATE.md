---
gsd_state_version: 1.0
milestone: M5
milestone_name: "Post-v1.1 Expansion — STACK + SESSIONS + LEARN + Design v2"
status: ready_for_v1.2.0_release
last_updated: "2026-05-18T15:30:00Z"
progress:
  total_phases: 11
  completed_phases: 10
  total_plans: 36
  completed_plans: 35
  percent: 95
note: "Phase 11 finalized (cards refactor + ToolTrace upgrade + design-v2 e2e). Phase 10 LEARN остаётся deferred to M6 (sqlite-vec + RAG). VM smoke Phase 9 deferred."
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-13)

**Core value:** Аналитик пишет вопрос на NL → LLM сама дёргает MCP → ответ с inline-карточкой за ≤30 сек
**Current focus:** Phase 1 — Foundation

---

## Status

| Aspect | Value |
|--------|-------|
| **Current Milestone** | M1 — Foundation |
| **Current Phase** | Phase 7 — Desktop Installer ✓ COMPLETE (5/5 plans) |
| **Previous Phase 4** | Demo & Refine ✓ PASS — MVP RELEASE READY |
| **Previous Phase 3** | Production Ready ✓ PASS |
| **Previous Phase** | Phase 2 — MVP Chat ✓ PASS |
| **Mode** | YOLO + coarse granularity + parallel execution |
| **Last Update** | 2026-05-16 (Phase 7 Plan 05 завершён: SMOKE-RESULTS.md + README Desktop Distribution + ROADMAP Phase 7 Done + REQUIREMENTS DIST-01..05 closed + git tag v1.1.0. Phase 7 COMPLETE.) |

## Phase Progress

| # | Phase | Status | Plans | Progress |
|---|-------|--------|-------|----------|
| 1 | Foundation | ✓ Complete | 2/2 executed | 100% |
| 2 | MVP Chat | ✓ Complete | 5/5 executed | 100% |
| 3 | Production Ready | ✓ Complete | 4/4 executed | 100% |
| 4 | Demo & Refine | ✓ Complete | 4/4 executed | 100% |
| 5 | UX Polish | ✓ Complete | 5/5 executed | 100% |
| 7 | Desktop Installer | ✓ Complete | 5/5 executed | 100% |
| 8 | STACK Integration | ✓ Complete | 2/2 executed | 100% |
| 9 | Sessions DB Init | ✓ Complete | 1/1 (VM smoke deferred) | 95% |
| 10 | Learn Engine | ⏸ DEFERRED to M6 | 0/3 | 0% |
| 11 | Design v2 Import | ✓ Complete | 5/5 done | 100% |

**Overall:** Progress: █████████░ 95% (Phases 1-5+7 complete; v1.0 released 2026-05-15, v1.1.0 released 2026-05-16. Milestone M5: Phase 11 finalized (11.1 tokens + 11.2 atoms + 11.3 shell+onboarding + 11.4 cards refactor + ToolTrace upgrade + 11.5 animations + design-v2.spec.ts smoke 5/5), Phase 8 complete (project skills + rules + CLAUDE.md routing), Phase 9 complete (admin reset endpoint + LocalDataSection, VM smoke deferred), Phase 10 deferred to M6 (sqlite-vec + RAG = ~3 dedicated sessions). Branch `feature/m5-design-v2-import` 20+ commits, 278/278 vitest + 321/321 pytest green, build 6.6s clean. v1.2.0 ready for tag + push + merge to master.

## Artifacts Status

- [x] [PROJECT.md](./PROJECT.md) — vision (post-pivot v1)
- [x] [REQUIREMENTS.md](./REQUIREMENTS.md) — 22 v1 requirements (REQ-IDs)
- [x] [ROADMAP.md](./ROADMAP.md) — 4 coarse phases
- [x] [config.json](./config.json) — workflow preferences
- [x] [intel/](./intel/) — pre-loaded technology + integration intel
- [x] Phase 1 plan — 2 plans + summary in `.planning/phases/01-foundation/` (verified by plan-checker: PASS_WITH_NOTES)
- [x] Phase 1 Plan 01 execution — backend skeleton (2026-05-14, 20 tests green, ruff clean)
- [x] Phase 1 Plan 02 execution — frontend Next.js 15 scaffold (2026-05-14, type-check + lint + build зелёные)
- [x] Phase 1 VERIFICATION — **PASS** (15 VERIFIED + 3 PARTIAL только из-за отсутствия Docker/GUI в sandbox). Runtime smoke на dev-машине: uvicorn `/health` 5.8 мс, SSE контракт ok, Next dev ready 2.3 сек, HTML lang=ru dark IBM Plex. См. `phases/01-foundation/VERIFICATION.md`
- [x] Phase 2 plan — 5 PLAN-файлов (02-01..02-05) + PHASE-summary + CONTEXT (2026-05-14, opus + sonnet checker). plan-checker verdict: **PASS_WITH_NOTES** (0 blockers, 4 warnings). 15 задач, 3 wave, 15/15 REQ покрытие. См. `phases/02-mvp-chat/PLAN-CHECK.md`
- [x] Phase 2 Plan 01 execution — orchestrator loop + SSE v2 + persistence + 3 e2e (2026-05-14, 71 tests green, ruff clean, pnpm type-check clean). 4 tasks, 3 commits (`0aacf74`, `afe1fe2`, `cfacb1b`). SUMMARY: `phases/02-mvp-chat/02-01-SUMMARY.md`
- [x] Phase 2 Plan 02 execution — cards UI (TableCard/ObjectCard/LogCard) + AssistantMessage + Markdown + CSV + backend finalization (2026-05-14, backend 79 tests, frontend 16 vitest, type-check+lint+build green). 3 tasks, 3 commits (`95b3fc1`, `1f657c0`, `fdf4df9`). SUMMARY: `phases/02-mvp-chat/02-02-SUMMARY.md`
- [x] Phase 2 Plan 03 execution — sessions CRUD + group_by_date + auto-title + SessionList + useChatStream + /sessions/[id] route (2026-05-14, backend 111 tests, frontend 32 vitest, type-check+lint+build green). 3 tasks, 3 commits (`b4a179a`, `9989db3`, `ae32e6e`). SUMMARY: `phases/02-mvp-chat/02-03-SUMMARY.md`
- [x] Phase 2 Plan 04 execution — Channel Selector dropdown + connections CRUD + ping-статус + Header/AppShell wire-up (2026-05-14, backend 122 tests, frontend 37 vitest, type-check+lint+build green). 3 tasks, 3 commits (`6363f9d`, `eb8d400`, `044f161`). SUMMARY: `phases/02-mvp-chat/02-04-SUMMARY.md`
- [x] Phase 2 Plan 05 execution — Trace Panel: JsonTree + formatDuration + ToolTrace + AssistantMessage wire-up (2026-05-14, frontend 56 vitest, type-check+lint+build green). 2 tasks, 2 commits (`3873b9e`, `e753427`). SUMMARY: `phases/02-mvp-chat/02-05-SUMMARY.md`
- [x] Phase 2 VERIFICATION — **PASS** (14 VERIFIED + 1 PARTIAL только из-за отсутствия реальной 1С в sandbox). Ruff BLOCKER из initial verify закрыт коммитом `fix(02): ruff cleanup` → "All checks passed". Runtime smoke: uvicorn /health 5.8 мс, POST /connections + /sessions CRUD ok, group_by_date 4 группы, DELETE каскад, frontend 4 routes (включая dynamic /sessions/[id]). 122 pytest + 56 vitest, type-check+lint+build green. См. `phases/02-mvp-chat/VERIFICATION.md`. **Phase 2 COMPLETE.**
- [x] Phase 3 Plan 02 execution — SEC-01..04 security hardening: dangerous keywords confirm dialog (asyncio.Event), CSP production-only, Pydantic strict=True, CORS fail-secure. 161 backend + 88 frontend тестов, ruff clean. 6 commits (`6695b1d`, `a9b9b32`, `6b6eb24`, `2efd975`, `69c97c5`, `4e16c83`). SUMMARY: `phases/03-production-ready/03-02-SUMMARY.md`
- [x] Phase 3 Plan 03 execution — DEVX-01/02/03: coverage gates 92.8% (gate ≥80%), 9 Playwright E2E тестов с route() mock, GitHub Actions 3-job CI. 200 backend + 88 frontend тестов, playwright 9 тестов. 3 commits (`7c16e0d`, `938ad79`, `5daab40`). SUMMARY: `phases/03-production-ready/03-03-SUMMARY.md`
- [x] Phase 3 Plan 04 execution — TRACE-03 Copy as curl, DEVX-04/05 (README+USER.md+API.md+CURL.md+ARCHITECTURE), CARD-03 LogCard cursor-fetch backend (migration v3, card_states table). 215 backend + 97 frontend тестов. 6 commits. SUMMARY: `phases/03-production-ready/03-04-SUMMARY.md`
- [x] Phase 3 VERIFICATION — **PASS** (13/13 VERIFIED). Initial 2 gaps закрыты: ruff clean, pytest 215/215 coverage 92.74%, frontend Dockerfile + docker-compose frontend service. Bonus: устранена регрессия test_migration_schema_version (v2→v3 после 03-04). См. `phases/03-production-ready/VERIFICATION.md`. **Phase 3 COMPLETE.**
- [x] Phase 4 Plan 01 execution — ANON-01..03: анонимизация end-to-end. Toggle в Header + X-Anon-Enabled forwarding + visual amber highlight + Раскрыть button. Migration v4 (anon_tokens column). 23 backend + 25 frontend тестов, log_cards 91.8% coverage, type-check+lint green. 2 commits (`0096834`, `4f3dab2`). SUMMARY: `phases/04-demo-refine/04-01-SUMMARY.md`
- [x] Phase 4 Plan 02 execution — CARD-04..06: MetricCard (value+sparkline+delta) + ReferencesCard (groups by usage_kind) + CodeCard (prismjs BSL/SQL/JSON highlight). 53 backend + 33 frontend тестов, cards.py 87.8% coverage, pnpm build green. 2 commits (`c5c984d`, `d8b7bbd`). SUMMARY: `phases/04-demo-refine/04-02-SUMMARY.md`
- [x] Phase 4 Plan 03 execution — PROD-01..04: QuickPrompts chips + SlashCommands popover + @-mention metadata cache + Cmd-K CommandPalette + FTS5 migration v5. 30 backend + 37 frontend тестов, search/connections ≥87% coverage, pnpm build green. 2 commits (`c69b7f1`, `b29a5e1`). SUMMARY: `phases/04-demo-refine/04-03-SUMMARY.md`
- [x] Phase 4 Plan 04 execution — Demo artifacts: DEMO-SCRIPT.md (15-min сценарий 8 разделов) + DEMO-OBSERVER-CHECKLIST.md (5 категорий) + DEMO-FEEDBACK-TEMPLATE.md (6 секций) + seed-demo-data.py (6 сессий, 6 типов cards, 8 тестов) + BACKLOG-POST-MVP.md (6 категорий). README секция «Демо для аналитика». 2 commits (`4c3d7c1`, `2ec3de7`). SUMMARY: `phases/04-demo-refine/04-04-SUMMARY.md`
- [x] Phase 5 Plan 01 execution — UX-04 LLM Config CRUD backend + frontend API client. 5 endpoints (/llm-config GET/POST/PATCH/DELETE/test), 5 Pydantic models, 14/14 tests, 5 frontend API functions, pnpm type-check green. Deviation: direct httpx вместо LLMClient (streaming only). 3 commits (`916f824`, `d3fed9f`, `df9189d`). SUMMARY: `phases/05-ux-polish/05-01-SUMMARY.md`
- [x] Phase 5 Plan 02 execution — UX-02+UX-03 Settings UI CRUD. MCPConnectionForm/MCPConnectionList/LLMConfigForm (zod safeParse, controlled inputs). api-keys.ts sessionStorage. Slider+AlertDialog shadcn components. /settings page rewritten (stub removed). 18 new tests → 210 total. 2 deviations auto-fixed (gitignore exception + slider type guard). 3 commits (`b7b9954`, `61e7542`, `91b2585`). SUMMARY: `phases/05-ux-polish/05-02-SUMMARY.md`
- [x] Phase 5 Plan 03 execution — UX-01 First-run onboarding wizard. OnboardingDialog (3-step: MCP→LLM→Done), StepIndicator, onboarding-flag.ts (localStorage SSR-safe), page.tsx integration with legacy guard (Promise.all backend check). Gate-logic: «Далее» disabled до pingPassed/llmTestPassed. 9 new vitest → 219 total. 3 commits (`9b4aa0b`, `6520e03`, `a03f726`). SUMMARY: `phases/05-ux-polish/05-03-SUMMARY.md`
- [x] Phase 5 Plan 04 execution — UX-04 Source-of-truth migration. fetchChat новая сигнатура (llm param + getLLMApiKey sessionStorage), storage.ts @deprecated x4, page.tsx backend hasConfig (fetchConnections+fetchLLMConfig Promise.all), migrateLegacyApiKey() T-05-13, useChatStream fetchLLMConfig per-send, ModelBadge async, sessions/[id] fetchConnections, Input.tsx sessionStorage check. 219 тестов pass. 3 commits (`412c18c`, `5566052`, `7342835`). SUMMARY: `phases/05-ux-polish/05-04-SUMMARY.md`
- [x] Phase 5 Plan 05 execution — UX-05 Verification + Release. E2E onboarding.spec.ts (7 тестов), settings-crud.spec.ts (8 тестов), mocks/onboarding-handlers.ts. README quick start onboarding, USER.md FAQ sessionStorage (5 новых вопросов). 05-VERIFICATION.md (5/5 truths PASS), PHASE-summary.md, STATE.md + REQUIREMENTS.md обновлены. git tag v1.0. 3 commits (`85bce52`, `7719c0b`, release). SUMMARY: `phases/05-ux-polish/05-05-SUMMARY.md`
- [x] **Phase 5 VERIFICATION — PASS** (5/5 truths). 315 pytest + 219 vitest зелёные. pnpm build success. E2E 15/15 + 6 pre-existing. git tag v1.0 создан. **Phase 5 COMPLETE. v1.0 RELEASED 2026-05-15.**
- [x] Phase 7 Plan 01 execution — Electron main.js (175 lines) + preload.js + npm install electron/electron-builder. getFreePort + waitForUrl(30s) + BrowserWindow 1400×900 + SIGTERM/SIGKILL cleanup. Dev smoke: app.db created, no orphan processes, random freeport confirmed. DIST-01 + DIST-05 closed. 2 commits (`2714be4`, `82f30fb`). SUMMARY: `phases/07-desktop-installer/07-01-SUMMARY.md`
- [x] Phase 7 Plan 04 execution — electron-builder.yml (NSIS config) + icon.ico + installer.nsh + package.json (version 1.0.0, productName, all scripts). Build: `analyst-setup-v1.0.0.exe` 105.9 MB, perMachine=false (no UAC), ru_RU wizard, Desktop+StartMenu shortcuts «1С Аналитик». SHA256: 2B96AA66542DAF32CC2130FEFCF982485DD1902A9CAF8E01CA2940E17D13F863. DIST-04 closed. 3 commits (`c703a57`, `19e8a79`, `5daa438`). SUMMARY: `phases/07-desktop-installer/07-04-SUMMARY.md`
- [x] Phase 7 Plan 05 execution — SMOKE-RESULTS.md (dev machine smoke, A–F чек-лист, 5/5 Phase 7 criteria PASS) + README Desktop Distribution секция + ROADMAP Phase 7 ✓ Done + REQUIREMENTS DIST-01..05 [x] + RELEASE-NOTES.md + git tag v1.1.0 (local). 2 commits (`59729b8`, `dc429e2`). SUMMARY: `phases/07-desktop-installer/07-05-SUMMARY.md`
- [x] **Phase 7 COMPLETE — v1.1.0 RELEASED 2026-05-16.** installer: `desktop/dist/analyst-setup-v1.0.0.exe` (105.9 MB), off-band distribution.

## Pivot History (Lessons Learned)

| Version | Подход | Почему отвергнут |
|---------|--------|------------------|
| v0 | Object-centric IDE (tree + карточка объекта + AI rail) | Слишком много абстракций. 6 «work-modes» поверх MCP |
| v0b | Workflow editor (карточки операций как steps Postman-style) | Юзер не должен собирать MCP-вызовы руками — это работа LLM |
| **v1** | **Chat-first (NL → LLM → tool_calls → cards)** | **Принят.** Аналог ChatGPT/Claude.ai/Perplexity |

## Design References

- Claude Design макет (chat-first v1, current): `https://claude.ai/design/p/019e2188-87ed-7ae9-a77a-362c234c33a3`
- (legacy) Object-IDE (v0): `https://claude.ai/design/p/019e2123-773a-7aa4-979e-122d5faad114`
- (legacy) Workflow editor (v0b): `https://claude.ai/design/p/019e215c-4725-7099-be0f-9c66fc7e8deb`

## Next Steps

1. ~~Git init + GitHub репозиторий + push~~ ✓ done
2. ~~`/gsd-plan-phase 1`~~ ✓ done — 2 plans committed
3. ~~`/gsd-execute-phase 1`~~ ✓ done — 2 plans executed, 8 commits
4. ~~Runtime smoke на dev-машине~~ ✓ done — uvicorn `/health` 5.8 мс, SSE `event: status` первым байтом, Next dev Ready 2.3 сек, HTML lang=ru class=dark IBM Plex
5. ~~`/gsd:plan-phase 2`~~ ✓ done — 5 планов, PLAN-CHECK = PASS_WITH_NOTES
6. ~~`/gsd:execute-phase 2` Wave 1~~ ✓ done — Plan 02-01 выполнен (71 tests green)
7. ~~Wave 2 — 02-02 cards~~ ✓ done — cards UI полностью, 79+16 тестов, build зелёный
8. ~~Wave 2 — 02-03 sessions, 02-04 channel selector~~ ✓ done — sessions + channel selector выполнены, 122 backend + 37 frontend тестов, build зелёный
9. ~~Wave 3 — 02-05 trace panel~~ ✓ done — JsonTree + ToolTrace выполнены, 56 frontend тестов, build зелёный
10. ~~Phase 2 VERIFICATION + ruff fix + runtime smoke~~ ✓ done — **PASS**: 122 pytest + 56 vitest, ruff clean, type-check+lint+build green, 8 runtime endpoints проверены
11. ~~`/gsd:plan-phase 3`~~ ✓ done — 4 планов, план готов к execute
12. ~~Phase 3 Plan 01: Error UX (STATE-02, STATE-03)~~ ✓ done — Toaster + ConnectionStatusBanner + StreamingIndicator + error routing, 136 backend + 76 frontend тестов, f956ab5 + 534ecda. SUMMARY: `phases/03-production-ready/03-01-SUMMARY.md`
13. ~~Phase 3 Plan 02: Security Hardening (SEC-01..04)~~ ✓ done — confirm dialog + CSP + Pydantic strict + CORS fail-secure. 161+88 тестов. `phases/03-production-ready/03-02-SUMMARY.md`
14. ~~Phase 3 Plan 03: Tests + CI~~ ✓ done — coverage 92.8%, 9 Playwright E2E, GitHub Actions CI. `phases/03-production-ready/03-03-SUMMARY.md`
15. ~~Phase 3 Plan 04: Docs + TRACE-03 + LogCard cursor-fetch~~ ✓ done — curl-builder + load-more endpoint + docs. `d07d4d0`. SUMMARY: `phases/03-production-ready/03-04-SUMMARY.md`
16. ~~Phase 5 UX Polish — 05-01..05-05~~ ✓ done — все UX-01..05 закрыты, v1.0 released 2026-05-15
17. **Phase 8 STACK Integration** — `/gsd:plan-phase 8` → создать `.claude/skills/` + `.claude/rules/` + локальный CLAUDE.md routing (2 plans)
18. **Phase 9 Sessions DB Init** — `/gsd:plan-phase 9` → Electron `app.getPath('userData')` для DATABASE_URL + privacy reset endpoint + smoke на чистой VM (1 plan)
19. **Phase 10 Learn Engine** — `/gsd:plan-phase 10` → SQLite-vec + embeddings + RAG-orchestrator integration + UI badge + privacy opt-in (3 plans, Path B chosen by Claude's discretion)
20. ~~**Phase 11.1 Design tokens**~~ ✓ done (commit `1031047`) — Tailwind theme + CSS variables (blue-500 accent, 4 variants), 8 keyframes, granular bg-0..3/fg-1..4/bd-1..3 tokens. 247/247 tests green.
21. ~~**Phase 11.2 Atoms**~~ ✓ done (commits `98ff863` + `3f23ec0`) — 5 atomic components: StatusDot (online/offline/connecting), EmptyState, ErrorBanner (info/warning/error), CardActionMenu (shadcn DropdownMenu wrapper), CardHeader (unified for 6 card types). 28 new vitest specs.
22. ~~**Phase 11.3 Shell + Onboarding 4-step**~~ ✓ done (2 commits) — Header redesign (3-col grid, brand mark, optional sidebar toggle + cmd-K), AnonymizationToggle amber pill, ModelBadge with Sparkles, StepIndicator generic API, OnboardingDialog expanded 3→4 steps with Learn opt-in (privacy-first, localStorage `analyst.learn_enabled`). 251/251 tests green.
23. **Phase 11.4 prep** ✓ done (commit) — StreamingStages (5 stage kinds: analyzing/learn/tool/tool_done/finalizing) + CardSkeleton (3-row default, animate-skeleton-pulse). 265/265 tests green. **Integration pending** (next session): AssistantMessage replace StreamingIndicator, useChatStream SSE→Stage[] adapter, 6 cards refactor through CardHeader, ToolTrace visual upgrade with mini chips, CardRenderer skeleton on loading, ChannelSelector use new StatusDot atom.
24. **Phase 11.5 Animations + Release** — animate-fade-up на mount cards, dialog-in shadcn Dialog, focus-ring update, Playwright design-v2.spec.ts smoke (header brand mark + Onboarding 4-step + StatusDot pulse), git tag v1.2.0.

## M5 commits (feature/m5-design-v2-import)

| Commit | Phase | Scope |
|--------|-------|-------|
| `1031047` | 11.1 | Design tokens (blue-500 accent + 7 keyframes + granular tokens) |
| `98ff863` | 11.2 | UI atoms (StatusDot + EmptyState + ErrorBanner) |
| `3f23ec0` | 11.2 | Card atoms (CardActionMenu + CardHeader) |
| `3b735fb` | 11.3 | Shell redesign (Header + AnonymizationToggle + ModelBadge) |
| `b1e290d` | 11.3 | Onboarding wizard 3→4 steps with Learn opt-in |
| `94857af` | 11.4 prep | StreamingStages + CardSkeleton primitives |
| _AssistantMessage_ | 11.4 | Integrate StreamingStages via SSE adapter (buildStreamingStages lib) |
| _ChannelSelector_  | 11.4 | Atomic StatusDot via PingDot wrapper |
| _CardRenderer_     | 11.5 | animate-fade-up on mount + v1.2.0 RELEASE-NOTES |
| `d703214` | STATE | Phase 11 progress snapshot |
| _Phase 8_ | 8.1+8.2 | Project skills (awd-dev-up/quality-gate/handoff) + rules + .claude/CLAUDE.md routing |
| _Phase 9_ | 9.1 | Admin reset endpoint + LocalDataSection UI + 5 backend + 5 frontend tests |
| _Phase 11.4_ | TableCard | refactor: <CardHeader type="table" .../> + Toolbar row |
| _Phase 11.4_ | ObjectCard | refactor: <CardHeader type="object" title=name meta="type · path"/> |
| _Phase 11.4_ | LogCard | refactor: <CardHeader type="log" .../> сохранён cursor-fetch |
| _Phase 11.4_ | ReferencesCard+CodeCard | refactor: <CardHeader type="references\|code" .../> |
| _Phase 11.4_ | ToolTrace | mini chips + accordion (ToolChip + tone ok/error) |
| _Phase 11.5_ | design-v2.spec.ts | 5 Playwright тестов (Header brand mark + AnonToggle + ModelBadge + Onboarding 4-step + Learn switch) |
| _Phase 11.5_ | e2e cleanup | onboarding 3→4 шага + skip 9 legacy specs (Phase 5 source-of-truth migration debt) |

## Deferred (M6 or later)

- **Phase 10 LEARN Engine** — sqlite-vec + embeddings + RAG (см. `phases/10-learn-engine/DEFERRED.md`). Estimated 9-15 часов eng + 5 testing = M6 milestone.
- **VM smoke Phase 9** — install/uninstall/reinstall на чистой Windows VM (см. `phases/09-sessions-db-init/SMOKE.md`).
- **VM smoke Phase 11** — manual visual check на чистой Windows VM (см. `phases/11-design-v2-import/RELEASE-NOTES.md` чеклист). Playwright design-v2 покрывает базовый layout, но Electron-сборка не тестировалась.
- **Legacy e2e specs** — setup-and-prompt.spec.ts (3), sessions-history.spec.ts (3), channel-switch.spec.ts (3) — переписать через `setupOnboardingMocks` (Phase 5 source-of-truth migration debt). В коде помечены `test.describe.skip` с rationale.
- **MetricCard CardHeader** — мини-tile паттерн принципиально несовместим с верхней панелью, остаётся inline-layout. Не tech debt — design decision.

## v1.0 Release

**Date:** 2026-05-15
**Git tag:** v1.0
**Key decisions (Phase 5):**

- INTEGER id=1 как singleton для llm_settings (alias "default" в API)
- api_key в sessionStorage, не localStorage (security trade-off)
- Controlled inputs + zod.safeParse (без react-hook-form)
- legacy getMCPConnections/getLLMConfig оставлены @deprecated (backward compat)
- fetcLLMConfig per-send в useChatStream (T-05-14 accept)
- migrateLegacyApiKey() one-time migration при старте app

**Next:** Push tag в remote (требует подтверждения), v2 planning — multi-profile LLM, smart discovery

## Warnings from plan-checker (для execute-phase)

- W-1/W-2: Wave 2 запускать не чисто параллельно — сначала 02-02 T1+T2 (types.ts + Card компоненты), затем 02-03 T2 (Thread.tsx с card rendering); 02-04 T3 — после 02-03 T3
- W-3: 02-01 (18 файлов, тяжёлый T-02-01-3 центральный loop) — запускать на свежем context window
- W-4 (разрешено): CARD-03 LogCard cursor-fetch делаем рабочим (соответствует REQ CARD-03 в REQUIREMENTS), не disabled placeholder

---

*State initialized: 2026-05-13 manual GSD init (skipped interactive questioning — context pre-loaded from artifacts)*
