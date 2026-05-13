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
| **Current Phase** | Phase 1 — Foundation (planned, ready to execute) |
| **Mode** | YOLO + coarse granularity + parallel execution |
| **Last Update** | 2026-05-13 |

## Phase Progress

| # | Phase | Status | Plans | Progress |
|---|-------|--------|-------|----------|
| 1 | Foundation | ◆ Planned | 0/2 executed (2 planned) | 0% |
| 2 | MVP Chat | ○ Pending | 0/5 | 0% |
| 3 | Production Ready | ○ Pending | 0/4 | 0% |
| 4 | Demo & Refine | ○ Pending | 0/4 | 0% |

**Overall:** Progress: ░░░░░░░░░░ 0%

## Artifacts Status

- [x] [PROJECT.md](./PROJECT.md) — vision (post-pivot v1)
- [x] [REQUIREMENTS.md](./REQUIREMENTS.md) — 22 v1 requirements (REQ-IDs)
- [x] [ROADMAP.md](./ROADMAP.md) — 4 coarse phases
- [x] [config.json](./config.json) — workflow preferences
- [x] [intel/](./intel/) — pre-loaded technology + integration intel
- [x] Phase 1 plan — 2 plans + summary in `.planning/phases/01-foundation/` (verified by plan-checker: PASS_WITH_NOTES)
- [ ] Phase 1 execution (run `/gsd-execute-phase 1`)

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

1. ~~**Now:** Git init + GitHub репозиторий + push~~ ✓ done
2. ~~**Next:** `/gsd-plan-phase 1` (запуск plan для Foundation)~~ ✓ done — 2 plans + summary committed
3. **Now:** `/gsd-execute-phase 1` — параллельное выполнение PLAN-01-backend и PLAN-02-frontend (yolo)
4. Параллельно: настройка LLM/MCP environment у разработчика

---

*State initialized: 2026-05-13 manual GSD init (skipped interactive questioning — context pre-loaded from artifacts)*
