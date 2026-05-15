# Phase 4: Demo & Refine — Plan Set Overview

**Phase:** 04-demo-refine
**Mode:** mvp (vertical slices)
**Granularity:** coarse
**Plans:** 4
**Waves:** 3
**Total tasks:** 8
**Planning date:** 2026-05-15

## Цель фазы

Закрыть пользовательский MVP-цикл: добавить anonymization end-to-end (toggle + visual highlight + Раскрыть), расширить inline cards с 3 до 6 типов (Metric / References / Code), включить productivity quick-wins (Quick prompts / Slash / @-mentions / Cmd-K), подготовить артефакты для live demo с реальным аналитиком (script + observer checklist + feedback template + seed script + post-MVP backlog).

После Phase 4 продукт готов к first real demo на проекте РТ или УСО.

---

## Phase Goal (MVP user story)

**As an** аналитик 1С на проекте клиента,
**I want to** прогнать 15-минутный сценарий по реальной 1С с anonymization + 6 типами cards + productivity-фичами,
**so that** я могу дать конкретный фидбек по «брал бы я этот инструмент в свою работу» — и команда продукта получает структурированный backlog для post-MVP.

---

## Wave Structure

| Wave | Plans | Параллельность | Обоснование |
|------|-------|----------------|-------------|
| 1 | 04-01 (Anonymization) | — | Plan 4.1 устанавливает migration v4 (ALTER card_states ADD anon_tokens) И расширяет contract Payload-моделей `card_id?: string` для всех 6 типов карточек. Plans 4.2/4.3 строят поверх этого расширения (4.2 добавляет 3 новых payload type с card_id; 4.3 ставит migration v5). Без Plan 4.1 Plan 4.2 не знает где брать card_id, Plan 4.3 не знает текущую CURRENT_VERSION для увеличения. |
| 2 | 04-02 (Advanced Cards), 04-03 (Productivity) | Параллельно с осторожностью | Оба depends_on=[04-01]. Между собой: 04-02 правит `backend/app/orchestrator/cards.py` + `frontend/components/cards/CardRenderer.tsx`. 04-03 правит `backend/app/routes/search.py` (новый), `backend/app/routes/connections.py` (добавляет metadata-suggest endpoint), `backend/app/storage/migrations.py` (CURRENT_VERSION=5), `frontend/components/chat/Input.tsx`. **Файловое пересечение:** только `backend/app/storage/migrations.py` (04-01 устанавливает v4, 04-03 добавляет v5 секцию) + `backend/app/models.py` (оба добавляют новые pydantic-модели). 04-02 НЕ трогает migrations.py. **Рекомендация для execute-phase**: запускать sequential (04-02 → 04-03 в одной длинной сессии или разные сессии) либо два разных worker'а с merge-coordination на migrations.py. Karpathy: пишу как «параллельно с осторожностью» — фактически безопаснее sequential. |
| 3 | 04-04 (Demo Artifacts) | — | Зависит от 04-01..04-03 ради корректного DEMO-SCRIPT (упоминает все features). seed-demo-data.py создаёт sessions с 6 типами cards + anon токены, что требует обоих 04-01 (card_states.anon_tokens) и 04-02 (новые payload types). |

### Файловые пересечения

| Файл | Plans | Кто что трогает | Wave-order |
|------|-------|----------------|-----------|
| `backend/app/storage/migrations.py` | 04-01, 04-03 | 04-01: CURRENT_VERSION=4 + ALTER card_states ADD COLUMN anon_tokens. 04-03: CURRENT_VERSION=5 + FTS5 virtual table + 3 triggers + metadata_cache table + backfill. Append-only к MIGRATIONS_V4/V5 спискам. | 04-01 → 04-03 |
| `backend/app/orchestrator/cards.py` | 04-01, 04-02 | 04-01: добавляет card_id ко всем 3 существующим payload schemas (TableCardPayload, ObjectCardPayload, LogCardPayload) + `_extract_anon_tokens_from_payload` helper. 04-02: добавляет 3 новых payload schemas (Metric/References/Code) + `_dispatch_query_card` + 3 builders + расширяет `_CARD_BUILDERS` dict до 6 ключей. | 04-01 → 04-02 |
| `backend/app/orchestrator/loop.py` | 04-01, (04-02) | 04-01: пробрасывает X-Anon-Enabled header в MCPClient + сохраняет anon_tokens в save_card_state для всех card types. 04-02 (минимально): убеждается что save_card_state работает для metric/references/code (просто новые case в условии). | 04-01 → 04-02 |
| `backend/app/orchestrator/persistence.py` | 04-01 | 04-01: расширяет save_card_state опциональным anon_tokens; добавляет get_card_anon_tokens. | — |
| `backend/app/routes/log_cards.py` | 04-01 | 04-01: добавляет POST /sessions/{sid}/messages/{mid}/cards/{cid}/deanonymize. | — |
| `backend/app/routes/connections.py` | 04-03 | 04-03: добавляет GET /channels/{id}/metadata-suggest. | — |
| `backend/app/routes/search.py` | 04-03 | 04-03: НОВЫЙ файл — GET /search FTS5. | — |
| `backend/app/routes/chat.py` | 04-01 | 04-01: добавляет Header X-Anon-Enabled + проброс в run_chat_loop. | — |
| `backend/app/models.py` | 04-01, 04-03 | 04-01: DeanonymizeRequest/Response. 04-03: SearchResponse/Item + MetadataSuggestResponse/Item. Append-only. | 04-01 → 04-03 |
| `frontend/components/cards/CardRenderer.tsx` | 04-01, 04-02 | 04-01: пробрасывает onDeanonymize в TableCard/ObjectCard/LogCard. 04-02: расширяет switch на 3 новых case (metric/references/code). | 04-01 → 04-02 |
| `frontend/components/cards/TableCard.tsx` | 04-01 | 04-01: визуальная подсветка anon-токенов в cells + Раскрыть button + сделать совместимым с onDeanonymize prop. | — |
| `frontend/components/cards/ObjectCard.tsx` | 04-01 | 04-01: highlightAnonTokens + Раскрыть. | — |
| `frontend/components/cards/LogCard.tsx` | 04-01 | 04-01: highlightAnonTokens + Раскрыть. | — |
| `frontend/components/cards/MetricCard.tsx` | 04-02 | 04-02: НОВЫЙ. Сразу с поддержкой anon-tokens consistent с pattern Plan 4.1. | — |
| `frontend/components/cards/ReferencesCard.tsx` | 04-02 | 04-02: НОВЫЙ. | — |
| `frontend/components/cards/CodeCard.tsx` | 04-02 | 04-02: НОВЫЙ + prismjs integration. | — |
| `frontend/components/cards/Sparkline.tsx` | 04-02 | 04-02: НОВЫЙ inline SVG. | — |
| `frontend/components/chat/Markdown.tsx` | 04-01, 04-02 | 04-01: модификация text renderers (`p/td/li/code(inline)`) для highlightAnonTokens. 04-02: модификация `code` renderer для fenced ```bsl/sql/json → CodeCard. Append-only. | 04-01 → 04-02 |
| `frontend/components/chat/useChatStream.ts` | 04-01 | 04-01: добавляет header X-Anon-Enabled. | — |
| `frontend/components/chat/Input.tsx` | 04-03 | 04-03: QuickPrompts + SlashPopover + MentionPopover wire-up. | — |
| `frontend/components/shell/Header.tsx` | 04-01 | 04-01: вставка AnonymizationToggle. | — |
| `frontend/lib/types.ts` | 04-01, 04-02, 04-03 | 04-01: DeanonymizeRequest/Response + card_id поля. 04-02: SparklinePoint, MetricCardPayload, ReferenceItem/Group, ReferencesCardPayload, CodeCardPayload + расширение CardEnvelope. 04-03: SearchResult* + MetadataSuggest*. Append-only. | 04-01 → 04-02 → 04-03 |
| `frontend/lib/api.ts` | 04-01, 04-02 (минимально), 04-03 | 04-01: deanonymizeCard. 04-03: searchMessages + metadataSuggest. Append-only. | 04-01 → 04-03 |
| `frontend/lib/storage.ts` | 04-01 | 04-01: getAnonEnabled/setAnonEnabled. | — |
| `frontend/package.json` | 04-02, 04-03 | 04-02: prismjs + @types/prismjs. 04-03: cmdk + @radix-ui/react-popover. Не конфликтуют. | Параллельно безопасно |

Все пересечения управляемые через wave ordering. Реальных строковых конфликтов нет — все правки append-only либо в разных функциях.

---

## Plans

### Plan 4.1: Anonymization (Wave 1)

**REQ:** ANON-01, ANON-02, ANON-03
**Tasks:** 2
- T-04-01-1: Backend — X-Anon-Enabled forwarding в MCPClient + POST /sessions/{sid}/messages/{mid}/cards/{cid}/deanonymize + migration v4 (ALTER card_states ADD anon_tokens) + расширение card_id для всех 3 существующих card schemas + extract_anon_tokens helper
- T-04-01-2: Frontend — AnonymizationToggle в Header + анон-tokens утилита (regex + highlightAnonTokens + extractAnonTokens) + Markdown подсветка в text renderers + Раскрыть button в TableCard/ObjectCard/LogCard + clipboard-неперсистентность реальных значений

**Зависимости:** Wave 1, нет.
**Доставляет:** end-to-end anonymization с visual highlight + раскрытие через MCP submit_for_deanonymization.

### Plan 4.2: Advanced Cards (Wave 2)

**REQ:** CARD-04, CARD-05, CARD-06
**Tasks:** 2
- T-04-02-1: Backend — _dispatch_query_card (1 row numeric → MetricCard / timeline → MetricCard со sparkline / иначе → TableCard) + _build_references_card group by usage_kind + _build_code_card + 3 новых Pydantic payload schemas + расширение _CARD_BUILDERS до 6 ключей
- T-04-02-2: Frontend — MetricCard + Sparkline (~50 SVG) + ReferencesCard (grouped) + CodeCard + prismjs + bsl-grammar.ts (~50 строк) + Markdown.tsx fenced ```bsl/sql/json → CodeCard + CardRenderer 3 новых case + интеграция с анон-tokens из 4.1

**Зависимости:** 04-01 (card_id support в payload).
**Доставляет:** 6 типов inline cards вместо 3.

### Plan 4.3: Productivity (Wave 2)

**REQ:** PROD-01, PROD-02, PROD-03, PROD-04 (PROD-05 partial)
**Tasks:** 2
- T-04-03-1: Backend — migration v5 (FTS5 virtual table messages_fts + 3 trigger INSERT/UPDATE/DELETE + metadata_cache table + index + backfill) + GET /search FTS5 endpoint + GET /channels/{id}/metadata-suggest endpoint с TTL-cache (default 3600s) + MCP refresh-on-miss + stale fallback
- T-04-03-2: Frontend — QuickPrompts (5 chip над Input) + SlashPopover (5 commands: sql/journal/find/audit/clear) + MentionPopover (debounced fetch с stale badge) + CommandPalette (cmdk + Cmd-K hotkey + scroll-to-message) + Input.tsx wire-up + cmdk + radix-popover

**Зависимости:** 04-01 (migrations v4 → v5).
**Доставляет:** quick prompts, slash, @-mentions, Cmd-K search.

**PROD-05 explicit**: CSV export уже есть с Phase 2 (TableCard); PDF deferred к post-MVP, documented в SUMMARY этого плана.

### Plan 4.4: Live Demo Session (Wave 3)

**REQ:** — (процессный план, не маппится на функциональные REQ-ID)
**Tasks:** 2
- T-04-04-1: docs/DEMO-SCRIPT.md (7 разделов, 15 минут) + DEMO-OBSERVER-CHECKLIST.md (5 категорий) + DEMO-FEEDBACK-TEMPLATE.md (6 секций, structured choices)
- T-04-04-2: scripts/seed-demo-data.py + тесты + .planning/BACKLOG-POST-MVP.md (6 категорий + Pipeline ритуал) + README.md секция «Демо для аналитика»

**Зависимости:** 04-01..04-03 (seed-demo-data использует все 6 типов cards + anon токены).
**Доставляет:** артефакты для проведения 15-минутного demo. Сам прогон — human activity после merge.

---

## Сумма задач

| Plan | Tasks | Wave |
|------|-------|------|
| 04-01 | 2 | 1 |
| 04-02 | 2 | 2 |
| 04-03 | 2 | 2 |
| 04-04 | 2 | 3 |
| **Total** | **8** | — |

---

## REQ Coverage Matrix

11 REQ-ID из Phase 4 + 1 bonus partial:

| Requirement | Plan(s) | Notes |
|-------------|---------|-------|
| ANON-01 (Toggle анонимизации в header) | 04-01 (T-2 AnonymizationToggle + useChatStream X-Anon-Enabled) | Полное закрытие |
| ANON-02 (Visual highlight токенов) | 04-01 (T-2 anon-tokens.ts + Markdown.tsx text renderers + cards integration) | Полное закрытие |
| ANON-03 (Раскрытие через submit_for_deanonymization) | 04-01 (T-1 endpoint /deanonymize + T-2 Раскрыть button + client-side replacement без persist) | Полное закрытие |
| CARD-04 (MetricCard + sparkline) | 04-02 (T-1 _dispatch_query_card heuristics + T-2 MetricCard + Sparkline) | Полное закрытие |
| CARD-05 (ReferencesCard) | 04-02 (T-1 _build_references_card group by usage_kind + T-2 ReferencesCard с filter + clickable) | Полное закрытие |
| CARD-06 (CodeCard) | 04-02 (T-1 _build_code_card + language detection + T-2 CodeCard + prismjs + bsl-grammar) | Полное закрытие |
| PROD-01 (Quick prompts chips) | 04-03 (T-2 QuickPrompts.tsx + 5 default constants) | Полное закрытие |
| PROD-02 (Slash commands) | 04-03 (T-2 SlashPopover + slash-commands.ts expand fn) | Полное закрытие |
| PROD-03 (@-mentions) | 04-03 (T-1 metadata_cache + endpoint + T-2 MentionPopover) | Полное закрытие |
| PROD-04 (Cmd-K search) | 04-03 (T-1 FTS5 migration + /search + T-2 CommandPalette + cross-platform hotkey) | Полное закрытие |
| PROD-05 (Export) | **PARTIAL** — CSV: ✓ Phase 2 TableCard; PDF: deferred post-MVP | Документировано в 04-03 SUMMARY + BACKLOG-POST-MVP.md |

**Всего REQ в Phase 4:** 11 → закрыто 11 (10 полностью + 1 partial с явным обоснованием) ✓

---

## Out-of-Scope Phase 4 (явно НЕ делаем)

| Feature | Reason | Phase |
|---------|--------|-------|
| PROD-05 PDF export | Нужен `pdfkit` или server-side render — отдельная итерация | Post-MVP |
| Vector search / RAG over metadata | Не lexical — отдельный engine | v2 |
| Mobile / tablet UI | Out of Scope (REQUIREMENTS) | — |
| Light theme | Out of Scope | — |
| Voice / TTS / OAuth | Out of Scope | — |
| Real-time collaboration / Multi-user | Out of Scope | — |
| Direct 1С editing помимо confirmed execute_code | Out of Scope (Phase 3 SEC-01) | — |
| Per-session anon override | MVP: global toggle | v2 |
| Анонимизация в Trace panel | Security: реальные значения не показываем в trace | — (intentional) |
| Cross-card anon раскрытие | Per-card раскрытие | v2 |
| HTTP cache real values | Cache-Control: no-store обязателен | — (mitigation) |
| Drill-down в MetricCard | click value → query «details» | v2 |
| Edit / Run code в CodeCard | read-only | — |
| Полный BSL grammar | ~30 keywords + ~30 builtins | Расширение по feedback |
| Recharts / chart.js | Sparkline вручную ~50 SVG | — (Karpathy) |
| Shiki vs prismjs | prismjs (10kb vs WASM) | — |
| Sonner toast | Свой ~80 строк (Phase 3) | — |
| Persistence pinned quick prompts | Constants only | v2 |
| Custom slash commands | Hardcoded 5 | v2 |
| Recall истории команд (`/<TAB>`) | v2 | v2 |
| Mention по реквизитам | Top-level objects only | v2 |
| Voice trigger Cmd+Shift+K | v2 | v2 |
| Markdown rendering в snippet | Plain text + `<mark>` | — |
| Pagination /search | Top 20-50 | v2 |
| Bookmark / star results | v2 | v2 |
| Cross-channel /search | Single channel filter | v2 |
| Авто-rotation seed data | On demand | — |
| Playwright тест demo прогона | Human session | — |
| Видео-запись demo | Фасилитатор | — |
| NLP анализ feedback | Manual | — |

---

## Verification Gate (для всей фазы)

Phase 4 закрывается когда выполнены success criteria каждого PLAN + 4 acceptance criteria из ROADMAP Phase 4:

1. ✅ Демо проходит за 15 минут — DEMO-SCRIPT.md содержит timing для каждого раздела (2+3+4+2+2+2 = 15 мин); поверяется на dry-run одной командой (фасилитатор сам)
2. ✅ Anonymization работает: ON → токены подсвечены → «Раскрыть» → реальные значения
3. ✅ 6 типов inline cards рендерятся (TableCard, ObjectCard, LogCard + MetricCard, ReferencesCard, CodeCard)
4. ✅ Quick prompts / slash / @-mentions / Cmd-K работают (manual smoke по DEMO-SCRIPT.md)

Автоматическая verification (выполняется execute-phase в конце Wave 3):
```
cd backend && python -m pytest -v --cov-fail-under=80
cd frontend && pnpm type-check && pnpm lint && pnpm test --run && pnpm build
sqlite3 backend/data.db "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"   # 5
sqlite3 backend/data.db "SELECT name FROM sqlite_master WHERE type IN ('table','trigger','index') AND (name LIKE '%fts%' OR name = 'metadata_cache' OR name LIKE 'messages_a%' OR name = 'card_states')"   # ≥ 6 имён
grep -rn "TODO\|FIXME\|placeholder" backend/app frontend/components frontend/lib README.md docs/ ARCHITECTURE.md scripts/ | grep -v '^#' | wc -l   # 0
grep -rn "recharts\|chart.js\|shiki\|sonner" frontend/package.json frontend/lib frontend/components   # 0 hits
test -f docs/DEMO-SCRIPT.md && test -f docs/DEMO-OBSERVER-CHECKLIST.md && test -f docs/DEMO-FEEDBACK-TEMPLATE.md && test -f scripts/seed-demo-data.py && test -f .planning/BACKLOG-POST-MVP.md
python scripts/seed-demo-data.py --db /tmp/phase4-verify.db --clean && sqlite3 /tmp/phase4-verify.db "SELECT COUNT(*) FROM sessions"   # ≥ 5
sqlite3 /tmp/phase4-verify.db "SELECT COUNT(DISTINCT json_extract(value,'$.type')) FROM messages, json_each(messages.cards) WHERE messages.cards IS NOT NULL"   # ≥ 5 (5+ типов в seed)
```

Manual smoke (выполняет execute-phase в конце Wave 3):
1. Header Anonymization toggle ON → отправить prompt → ответ с токенами → Раскрыть → реальные значения inline; reload → токены снова видны (не persisted)
2. Mock MCP возвращает execute_query 1 row 1 numeric col → MetricCard; timeline 12 rows → MetricCard со sparkline; find_references → ReferencesCard grouped; execute_code → CodeCard с BSL highlight; markdown ```bsl блок в TL;DR → inline CodeCard
3. Пустая textarea показывает 5 quick prompts; click → заполняет
4. Typing «/» → SlashPopover; ArrowDown + Enter `/journal` → expand prompt
5. Typing «@Док» → MentionPopover; Enter → вставка `@Документ.Имя`
6. Cmd+K (Mac) / Ctrl+K (Win) → CommandPalette; typing «опп» → results; click → /sessions/{id}#message-{mid} scroll
7. Прогнать DEMO-SCRIPT.md dry-run с seed-data: 15 минут от начала до wrap-up без застреваний

---

## Known Risks / Open Questions

1. **MCP submit_for_deanonymization shape** — capability-map описывает имя tool, реальная форма response не верифицирована. Mitigation Plan 4.1: тесты mock; SUMMARY фиксирует фактический формат после первого E2E теста на live 1С. **Открытый вопрос**: если MCP вернёт другой формат → fix patch в `routes/log_cards.py:deanonymize_card` (несколько fallback парсеров: mapping / map / replacements).

2. **Параллельность 04-02 + 04-03 в Wave 2** — оба depends_on=[04-01]. Между собой нет hard-конфликтов файлов (см. таблицу), но при параллельной работе models.py и migrations.py могут получить merge conflicts. **Рекомендация для execute-phase**: sequential (04-02 первым, затем 04-03 — оба умеренного размера ~50% context каждый) ИЛИ два worker'а с явным merge-point после Wave 2.

3. **FTS5 в SQLite build** — Python 3.11-slim image содержит. Если кто-то деплоит на alpine — нужен `apk add sqlite-fts5`. Документировать в README.

4. **prismjs CSP** — production CSP установлен в Plan 3.2. prismjs использует class names + DangerouslySetInnerHTML — must verify в production build что нет inline-style violations.

5. **BSL grammar coverage** — ~30 keywords + 30 builtins. Реальные BSL программы могут содержать редкие конструкции (DECLARE / Перем). Mitigation: документировано в Plan 4.2 risk; расширение по post-MVP feedback.

6. **MetricCard heuristic false positives** — single row + numeric ID column → может попасть в metric. Mitigation: ID-like columns (regex `^(id|ссылка|reference)$`) исключаются.

7. **Demo артефакты протухают** — если merge → demo через >14 дней, имена tools/cards могут измениться. Mitigation Plan 4.4: SUMMARY указывает дату валидности; ревизия DEMO-SCRIPT перед каждым demo.

8. **Demo может пойти не по plan** — реальный аналитик задаёт «крестики-нолики» вместо запланированного prompt. Mitigation: резервные сценарии в DEMO-SCRIPT.md.

9. **AssistantMessage id="message-{mid}"** — CommandPalette scroll to anchor требует. Verify в Plan 4.3 что компонент имеет этот id (если нет — добавить в Plan 4.3 T-2 как минимальная правка существующего AssistantMessage.tsx).

10. **PROD-05 PDF** — partial CSV есть, PDF deferred. Не блокер для Phase 4 success criteria. Зафиксировано в BACKLOG-POST-MVP.md.

11. **Migration v5 backfill для существующих messages** — `INSERT INTO messages_fts SELECT ...` выполняется один раз. Если в БД 10000 messages — ~100ms. На больших БД (если случится) — ≤5s. Приемлемо.

12. **localStorage anon toggle в SSR** — Next.js SSR на /page.tsx может пытаться читать localStorage до hydration. Mitigation Plan 4.1: useState(false) initial + useEffect для чтения on mount (стандартный pattern из Phase 1).

---

## Сроки и контекст

- **Wave 1 (04-01)**: ~40% context на 2 задачи (T-1 backend, T-2 frontend). Backend часть: deanonymize endpoint + migration v4 + extract_anon_tokens helper. Frontend: 9 файлов + 3 теста-набора (anon-tokens, AnonymizationToggle, TableCard.anon). Рекомендация: один воркер, между task'ами не /clear.
- **Wave 2 (04-02 + 04-03)**: sequential рекомендуется. 04-02 ~45% context (cards.py builders + prismjs + 4 React компонента + bsl-grammar). 04-03 ~50% context (FTS5 migration + 2 endpoints + 4 React popover/palette компонента). Рекомендация: /clear между 04-02 и 04-03; либо два разных worker session.
- **Wave 3 (04-04)**: ~25% context. Только doc файлы + один Python script + README update. Можно делать в одной короткой сессии.

Итого: **3-4 execution sessions** для Phase 4 при solo workflow.

---

## Self-Check

- [x] Все 4 PLAN-файла созданы по канону `{phase}-{NN}-PLAN.md`
- [x] Frontmatter содержит все required поля (phase, plan, type, wave, depends_on, files_modified, autonomous, requirements, must_haves)
- [x] Каждый план содержит objective, context, 2 tasks, out-of-scope, risks, verification, test_strategy, references, success_criteria, output
- [x] Каждая задача имеет files, action, verify (automated), done
- [x] Wave 2 параллельность задокументирована с recommendation на sequential
- [x] REQ coverage 11/11 ✓ (10 полностью + 1 partial с явным обоснованием)
- [x] PROD-05 partial задокументирован в 04-03 + BACKLOG-POST-MVP.md
- [x] Out-of-Scope явно перечислен (≥ 25 items)
- [x] Никаких placeholder/TODO/«доделать позже» в плановых acceptance criteria
- [x] Karpathy Simplicity First: prismjs vs shiki, ~50 SVG Sparkline вместо recharts, ~80 строк toast (уже Phase 3), regex highlight ~20 строк
- [x] Brutal honesty: 12 открытых вопросов / рисков перечислены
- [x] Threat models включены во все 4 плана
- [x] User decisions из 04-CONTEXT.md уважены:
  - Anon токены regex: `\[(ORG|INN|PER|PHONE|EMAIL|ACCT|AGREE|FIO|DOC|ADDR)-\d+\]`
  - prismjs (не shiki)
  - Sparkline руками (не recharts)
  - Metadata cache TTL 1 час (env-configurable METADATA_CACHE_TTL_S)
  - Cross-platform Cmd-K detection через navigator.platform
  - PROD-05 partial: CSV есть, PDF deferred — в BACKLOG-POST-MVP.md
  - Demo артефакты как процессный план (Plan 4.4 NOT код продукта)

---

*Phase 4 planning complete: 2026-05-15*
*Next step: `/gsd-execute-phase 04-demo-refine` (sequential по wave, как описано в «Сроки и контекст»)*
