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
| **Current Phase** | Phase 1 — Foundation (PARTIAL: код + автотесты ✓, runtime smoke ожидает ручной проверки) |
| **Mode** | YOLO + coarse granularity + parallel execution |
| **Last Update** | 2026-05-14 |

## Phase Progress

| # | Phase | Status | Plans | Progress |
|---|-------|--------|-------|----------|
| 1 | Foundation | ◆ Verified (PARTIAL) | 2/2 executed | 95% (runtime smoke pending) |
| 2 | MVP Chat | ○ Pending | 0/5 | 0% |
| 3 | Production Ready | ○ Pending | 0/4 | 0% |
| 4 | Demo & Refine | ○ Pending | 0/4 | 0% |

**Overall:** Progress: ██░░░░░░░░ 13% (2/2 Phase 1 plans + 0/15 remaining)

## Artifacts Status

- [x] [PROJECT.md](./PROJECT.md) — vision (post-pivot v1)
- [x] [REQUIREMENTS.md](./REQUIREMENTS.md) — 22 v1 requirements (REQ-IDs)
- [x] [ROADMAP.md](./ROADMAP.md) — 4 coarse phases
- [x] [config.json](./config.json) — workflow preferences
- [x] [intel/](./intel/) — pre-loaded technology + integration intel
- [x] Phase 1 plan — 2 plans + summary in `.planning/phases/01-foundation/` (verified by plan-checker: PASS_WITH_NOTES)
- [x] Phase 1 Plan 01 execution — backend skeleton (2026-05-14, 20 tests green, ruff clean)
- [x] Phase 1 Plan 02 execution — frontend Next.js 15 scaffold (2026-05-14, type-check + lint + build зелёные)
- [x] Phase 1 VERIFICATION — 17/18 must-haves verified, 1 PARTIAL (Docker недоступен в sandbox). См. `phases/01-foundation/VERIFICATION.md`

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
3. ~~`/gsd-execute-phase 1`~~ ✓ done — 2 plans executed, 8 commits, verification PARTIAL
4. **Human runtime smoke** (5 пунктов, ~10 мин):
   - `docker compose up -d backend` → `curl http://localhost:8010/health` → ожидаем `{"status":"ok","version":"0.1.0","db":"ok"}`
   - Cold start ≤ 2 сек (`time docker compose restart backend`)
   - `cd frontend && pnpm dev` → открыть `http://localhost:3010` → AppShell, тёмная тема, IBM Plex, русский, empty state с CTA «Настроить»
   - Бейдж «Backend: ok 0.1.0» при работающем backend
   - Ctrl+Enter в textarea срабатывает
5. Если smoke зелёный → `/gsd:plan-phase 2` (MVP Chat: orchestrator + cards + sessions + settings + trace)
6. Параллельно: настройка LLM endpoint (Xiaomi MiMo) + MCP Toolkit (порт 6010) у разработчика

---

*State initialized: 2026-05-13 manual GSD init (skipped interactive questioning — context pre-loaded from artifacts)*
