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
| **Current Phase** | Phase 2 — MVP Chat (planned, готов к execute) |
| **Previous Phase** | Phase 1 — Foundation ✓ PASS |
| **Mode** | YOLO + coarse granularity + parallel execution |
| **Last Update** | 2026-05-14 |

## Phase Progress

| # | Phase | Status | Plans | Progress |
|---|-------|--------|-------|----------|
| 1 | Foundation | ✓ Complete | 2/2 executed | 100% |
| 2 | MVP Chat | ◆ Planned | 0/5 executed (5 planned) | 0% |
| 3 | Production Ready | ○ Pending | 0/4 | 0% |
| 4 | Demo & Refine | ○ Pending | 0/4 | 0% |

**Overall:** Progress: ███░░░░░░░ 13% (Phase 1 закрыта; 0/13 планов M2-M4)

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
6. **Now:** `/gsd:execute-phase 2` — выполнить Wave 1 (02-01 orchestrator) → Wave 2 (02-02 cards, 02-03 sessions, 02-04 channel selector — с ordering: cards T1+T2 до sessions T2) → Wave 3 (02-05 trace)
7. **Pending (можно начинать параллельно с Phase 2 dev):** настройка LLM endpoint (Xiaomi MiMo) + MCP Toolkit (порт 6010) у разработчика
8. **Pending визуальный smoke в браузере** (когда удобно): открыть `http://localhost:3010` глазами — AppShell, IBM Plex, бейдж backend, Ctrl+Enter

## Warnings from plan-checker (для execute-phase)
- W-1/W-2: Wave 2 запускать не чисто параллельно — сначала 02-02 T1+T2 (types.ts + Card компоненты), затем 02-03 T2 (Thread.tsx с card rendering); 02-04 T3 — после 02-03 T3
- W-3: 02-01 (18 файлов, тяжёлый T-02-01-3 центральный loop) — запускать на свежем context window
- W-4 (разрешено): CARD-03 LogCard cursor-fetch делаем рабочим (соответствует REQ CARD-03 в REQUIREMENTS), не disabled placeholder

---

*State initialized: 2026-05-13 manual GSD init (skipped interactive questioning — context pre-loaded from artifacts)*
