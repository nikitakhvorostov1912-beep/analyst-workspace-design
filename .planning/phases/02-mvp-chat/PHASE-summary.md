# Phase 2: MVP Chat — Plan Set Overview

**Phase:** 02-mvp-chat
**Mode:** mvp (vertical slices)
**Granularity:** coarse
**Plans:** 5
**Waves:** 3
**Total tasks:** 14 (4 + 3 + 3 + 3 + 2... уточнить ниже)
**Planning date:** 2026-05-14

## Цель фазы

End-to-end чат работает с реальной 1С: вопрос на NL → backend оркеструет
tool-calling loop (LLM ↔ MCP) → ответ с inline-карточкой (Table / Object / Log)
+ trace. Sessions сохраняются и группируются в sidebar. Channel selector
переключает базы. Trace под каждым ответом раскрывается до args/result tool calls.

---

## Wave Structure

| Wave | Plans | Параллельность | Обоснование |
|------|-------|----------------|-------------|
| 1 | 02-01 (Orchestrator + SSE) | — | Foundation: фиксирует SSE-контракт + DB schema + run_chat_loop. Без него остальные планы не имеют адресатов для consumer-кода. |
| 2 | 02-02 (Cards), 02-03 (Sessions+UI), 02-04 (Channel Selector) | Параллельно | Все три зависят от 02-01. Между собой: 02-02 и 02-03 пересекаются в `components/chat/Thread.tsx` и `Message.tsx` — 02-02 расширяет ChatMessage type и AssistantMessage компонент; 02-03 потребляет AssistantMessage. **Порядок при параллельной работе:** 02-02 завершается первым (добавляет AssistantMessage + типы), 02-03 стартует после type/component готовности — но запускаются в одной wave, потому что 02-03 разработчик может ждать первых 2 task'ов 02-02. 02-04 полностью независим от 02-02/02-03 (трогает Header + ChannelSelector, не Thread). |
| 3 | 02-05 (Trace Panel) | — | Зависит от 02-01 (tool_calls persistence) + 02-02 (AssistantMessage composite) + 02-03 (GET /sessions/{id}/messages для восстановления trace после refresh). Идёт строго после Wave 2. |

### Файловые пересечения внутри Wave 2

| Файл | Plans | Кто что трогает |
|------|-------|----------------|
| `frontend/components/chat/Thread.tsx` | 02-02, 02-03 | 02-02 фильтрует role="tool"; 02-03 добавляет auto-scroll. **Merge order**: 02-02 → 02-03. |
| `frontend/components/chat/Message.tsx` | 02-02 | Только 02-02 (диспетчер user/assistant). 02-03 не трогает. |
| `frontend/lib/types.ts` | 02-01, 02-02, 02-03, 02-04 | 02-01 расширяет SSEEvent; 02-02 — ChatMessage с cards/tool_calls/duration_ms; 02-03 — SessionListItem/MessageRow; 02-04 — MCPConnection last_seen_at. Каждый план добавляет тип, никто не удаляет — конфликтов нет. |
| `frontend/lib/api.ts` | 02-01, 02-03, 02-04 | 02-01 ничего не меняет в существующих функциях; 02-03 добавляет fetchSessions/etc; 02-04 добавляет fetchConnections/etc. Нет конфликтов (append-only). |
| `frontend/components/shell/Header.tsx` | 02-04 | Только 02-04. |
| `frontend/components/shell/ChannelSelector.tsx` | 02-04 | Только 02-04. |
| `frontend/app/page.tsx` | 02-03, 02-04 | 02-03 переписывает целиком (sessions integration); 02-04 добавляет onChannelChange. **Merge order**: 02-03 → 02-04. |
| `frontend/app/sessions/[id]/page.tsx` | 02-03 (создание), 02-04 (extends) | 02-03 создаёт; 02-04 расширяет. **Merge order**: 02-03 → 02-04. |
| `backend/app/routes/sessions.py` | 02-01 (создание stub), 02-03 (расширение до полного CRUD) | 02-01 создаёт минимальный POST; 02-03 расширяет. Wave order соблюдается. |
| `backend/app/orchestrator/persistence.py` | 02-01 (создание), 02-03 (расширение list_sessions_grouped/get_session_messages/delete_session/update_session_title) | Append-only. |
| `backend/app/orchestrator/cards.py` | 02-01 (минимум), 02-02 (полная версия) | 02-02 переписывает _build_* функции, расширяет покрытие tools. |

Все пересечения управляемые через wave ordering. Никаких реальных конфликтов
строк нет.

---

## Plans

### Plan 2.1: Orchestrator + SSE (Wave 1)

**REQ:** CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CONN-03 (частично)
**Tasks:** 4
- T-02-01-1: Pydantic SSE-events + schema_version=2 + ChatRequest расширение
- T-02-01-2: Persistence слой (ensure_session, save_user_message, save_assistant_message, touch_session, lookup_mcp_endpoint) + POST /sessions stub + MCPClient.aclose alias
- T-02-01-3: run_chat_loop (главный tool-calling алгоритм) + build_card_from_tool_result (мини) + ≥13 unit-тестов
- T-02-01-4: POST /chat orchestrator интеграция + 3 «золотых» e2e теста + frontend types/sse расширение

**Зависимости:** ничего (Wave 1).
**Доставляет:** работающий backend с реальным NL → MCP loop, contracts SSE+cards.

### Plan 2.2: Inline Cards (Wave 2)

**REQ:** CARD-01, CARD-02, CARD-03, CHAT-05
**Tasks:** 3
- T-02-02-1: Финальный build_card_from_tool_result в backend (≥12 кейсов)
- T-02-02-2: react-markdown + shadcn table/badge + 3 card-компонента + CSV-утилита
- T-02-02-3: AssistantMessage композит + ChatMessage type расширение + vitest

**Зависимости:** 02-01 (контракт card payload).
**Доставляет:** UI для 3 типов карточек, готовый visualiser MCP-результатов.

### Plan 2.3: Sessions + History UI (Wave 2)

**REQ:** HIST-01, HIST-02, HIST-03, HIST-04, CHAT-01, CHAT-03 (UI wire-up)
**Tasks:** 3
- T-02-03-1: Backend sessions CRUD + grouping + auto-title (heuristic + LLM)
- T-02-03-2: Frontend API + sessions store + SessionList + useChatStream hook
- T-02-03-3: URL routing /sessions/[id] + page.tsx integration + manual smoke checklist

**Зависимости:** 02-01 (persistence слой + SSE контракт + POST /sessions stub).
**Доставляет:** реальный pipe от UI до DB; история выживает refresh; sidebar grouping.

### Plan 2.4: Channel Selector (Wave 2)

**REQ:** CONN-03, CONN-04
**Tasks:** 3
- T-02-04-1: Backend connections CRUD + last_seen_at update at ping
- T-02-04-2: shadcn DropdownMenu + новый ChannelSelector с параллельным ping
- T-02-04-3: Header wire-up + onChannelChange в page.tsx + интеграция

**Зависимости:** 02-01 (channel_id уже в ChatRequest, lookup в mcp_connections).
**Доставляет:** multi-tenant переключение между базами 1С с ping-индикатором.

### Plan 2.5: Trace Panel (Wave 3)

**REQ:** TRACE-01, TRACE-02
**Tasks:** 2
- T-02-05-1: JsonTree компонент + format-duration utility + vitest
- T-02-05-2: ToolTrace компонент + интеграция в AssistantMessage + vitest

**Зависимости:** 02-01 (tool_calls сохраняются в БД) + 02-02 (AssistantMessage exists) + 02-03 (GET /sessions/{id}/messages восстанавливает tool_calls).
**Доставляет:** аналитик видит args/result каждого MCP-вызова под ответом ассистента.

---

## Сумма задач

| Plan | Tasks | Wave |
|------|-------|------|
| 02-01 | 4 | 1 |
| 02-02 | 3 | 2 |
| 02-03 | 3 | 2 |
| 02-04 | 3 | 2 |
| 02-05 | 2 | 3 |
| **Total** | **15** | — |

---

## REQ Coverage Matrix

| Requirement | Plan(s) | Notes |
|-------------|---------|-------|
| CONN-03 (Channel selector multi-tenant) | 02-01 (channel_id в ChatRequest), 02-04 (UI dropdown) | Полное закрытие |
| CONN-04 (POST /mcp/{id}/ping) | 02-04 (refactor + полный CRUD /connections) | Backward compat с Phase 1 сохранена |
| CHAT-01 (NL → ответ ≤30 сек) | 02-01 (orchestrator), 02-03 (UI wire-up) | Полное закрытие, время = функция LLM/MCP latency |
| CHAT-02 (LLM autonomous tool calling) | 02-01 (tools параметр в LLMClient уже из Phase 1, теперь используется) | Полное закрытие |
| CHAT-03 (SSE streaming, ≤500 мс первый chunk) | 02-01 (status=thinking первый event), 02-03 (useChatStream consumer) | Полное закрытие; visualization stages — Phase 3 |
| CHAT-04 (множественные tool calls) | 02-01 (MAX_TOOL_ITERATIONS=10, accumulator) | Полное закрытие |
| CHAT-05 (TL;DR + cards + trace) | 02-02 (Markdown + CardRenderer), 02-05 (ToolTrace) | Полное закрытие |
| CARD-01 (TableCard pagination + sort + CSV) | 02-02 (T-02-02-2) | Полное закрытие |
| CARD-02 (ObjectCard 4 секции) | 02-02 (T-02-02-2) | Полное закрытие |
| CARD-03 (LogCard timeline + levels) | 02-02 (T-02-02-2) | Закрытие частично — load-more cursor является UI-кнопка без фактического fetch (Phase 3) |
| HIST-01 (Sidebar group by date) | 02-03 (T-02-03-2, SessionList) | Полное закрытие |
| HIST-02 (Auto-title) | 02-03 (T-02-03-1, title.py: cheap LLM + heuristic fallback) | Полное закрытие |
| HIST-03 (Persistence через refresh) | 02-01 (save_*), 02-03 (GET /sessions/{id}/messages) | Полное закрытие |
| HIST-04 («+ Новый чат») | 02-03 (T-02-03-3) | Полное закрытие |
| TRACE-01 (Collapsed trace строка) | 02-05 (T-02-05-2, ToolTrace header) | Полное закрытие |
| TRACE-02 (Expanded trace details) | 02-05 (T-02-05-2 + T-02-05-1 JsonTree) | Полное закрытие |
| ~~TRACE-03 (Copy as curl)~~ | НЕ в Phase 2 (явно отложено на Phase 3 в CONTEXT.md) | — |

**Всего REQ в Phase 2:** 16 (по ROADMAP) → закрыто 16 ✓ (TRACE-03 явное OOS).

---

## Out-of-Scope Phase 2 (явно НЕ делаем)

| Feature | Reason | Phase |
|---------|--------|-------|
| STATE-02 (MCP disconnected банер) | Error states deferred | Phase 3 |
| STATE-03 (LLM rate limit handling) | Error states deferred | Phase 3 |
| TRACE-03 (Copy as curl) | Productivity, не критично для MVP | Phase 3 |
| Анонимизация ANON-* | Безопасность v2 | Phase 3/4 |
| SEC-01 (confirm dialog execute_code) | Security hardening | Phase 3 |
| SEC-02 (CSP headers) | Security hardening | Phase 3 |
| SEC-03 (Pydantic strict) | Security hardening | Phase 3 |
| SEC-04 (CORS lockdown) | Security hardening | Phase 3 |
| DEVX-02 (E2E Playwright) | Testing, не для feature dev | Phase 3 |
| DEVX-03 (GitHub Actions) | CI, не для feature dev | Phase 3 |
| 80% test coverage | Cel из Phase 3; Phase 2 цель ≥60% backend | Phase 3 |
| PROD-01..05 (quick prompts, slash, @-mentions, Cmd-K, экспорт) | v2 productivity | Phase 4 |
| CARD-04..06 (Metric, References, Code cards) | v2 cards | Phase 4 |
| Background polling ping в ChannelSelector | Избыточно для MVP | Phase 3 если потребуется |
| Settings → Connections реальный CRUD UI | Backend есть (Plan 2.4), UI Settings остаётся read-only | Phase 3 / Out-of-Scope |
| Pagination cursor для LogCard load-more | Endpoint требует Phase 3 | Phase 3 |
| Streaming stages visualisation в UI | Не в acceptance criteria CHAT-03 (достаточно факта streaming) | Phase 3 |

---

## Verification Gate (для всей фазы)

Phase 2 закрывается когда выполнены **все** успешные критерии каждого PLAN +
3 acceptance criteria из ROADMAP Phase 2:

1. ✅ Тестовый prompt «Расскажи про базу» → корректный ответ с TableCard или ObjectCard
2. ✅ Тестовый prompt «Покажи документы ОПП за вчера» → TableCard с реальными строками
3. ✅ Тестовый prompt «Что в журнале сегодня» → LogCard с записями
4. ✅ История сессий сохраняется; после refresh видна в sidebar (HIST-03)
5. ✅ Channel selector работает: переключение базы → новые tools, новый чат (CONN-03)

Автоматическая verification (pytest + vitest):
- backend: pytest backend/ -v + ruff check → ≥40 кейсов зелёных, coverage app/orchestrator ≥60%
- frontend: pnpm type-check + pnpm lint + pnpm build + pnpm test --run → ≥20 кейсов

Manual smoke (выполняет execute-phase агент в конце Wave 3):
- 3 «золотых» промпта через UI с реальной (или замоканной) 1С → видны 3 типа карточек
- Создать 5 сессий с разными датами → видны 4 sidebar группы
- Refresh страницы /sessions/{id} → сообщение, card, trace восстановлены
- Switch канала → /sessions/[id] редиректит на `/`
- Click на trace → expanded list args/result для каждого tool call

---

## Known Risks / Open Questions

1. **Performance for large tool result (>50 KB)** — Plan 2.1 ограничивает payload в messages до 50000 символов с маркером ...truncated. Card payload идёт без обрезки — если result огромный (50К строк), TableCard cap = 1000 строк на client + CSV экспорт полный. **Если возникнут проблемы** — Phase 3 ввести stream-rendering или server-side pagination.

2. **Auto-title через cheap LLM call** — добавляет дополнительный LLM round-trip. Плюс: красивые названия. Минус: если у пользователя дорогая модель и нет дешёвой fallback — каждое создание сессии стоит. **Митигация в Plan 2.3**: фоновый task (не блокирует main loop); fallback на heuristic если LLM падает. **Дополнительная опция (отложено в Plan 2.3 SUMMARY)**: env var `AUTO_TITLE_ENABLED=false` чтобы отключать LLM-генерацию совсем.

3. **Switching канала в `/sessions/[id]` редиректит на `/`** — UX-решение спорное (пользователь теряет контекст). Альтернатива: оставаться на текущей сессии, новый канал применяется только к новым чатам. **Default = редирект**, потому что иначе ChannelSelector показывает channel ≠ session.channel_id (confusing). **Pre-empt в SUMMARY**: можно перейти на «остаёмся, но с warning» если usability теста покажет фрустрацию.

4. **Backend CRUD /connections vs Settings UI** — backend полностью реализован в Plan 2.4, но Settings → Connections в UI остаётся read-only (Phase 1 stub). Это разрыв ожидания: пользователь не сможет добавлять подключения через UI после Phase 2 — только через curl/Postman. **Compensating**: ChannelSelector сам показывает «Подключения не настроены» + ссылку на Settings. **Open**: дополнить UI Settings в Plan 2.4 или явно Phase 3? **Решение для Phase 2**: оставить как есть (явный OOS); если execute-phase агент посчитает критичным — поднимать на gap-closure.

5. **MCP tool schema → OpenAI function format conversion** — Plan 2.1 task T-02-01-3 описывает простую обёртку. Открытый риск: если MCP вернёт схему с неподдерживаемыми JSON Schema конструкциями (например `oneOf`/`anyOf`), OpenAI может не принять. **Митигация**: documented в Plan 2.1 risk #6, в крайнем случае фильтровать сложные конструкции на этапе конверсии. Не блокирует, потому что 1С MCP Toolkit известен (docs/00b-mcp-capability-map.md) — 10 простых tools со стандартными schema.

6. **Vitest setup для frontend tests** — может потребовать ad-hoc настройку jsdom/test environment. Plan 2.2 task T-02-02-3 явно описывает добавление `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`. **Если в sandbox install fails** — Plan 2.2 может частично не пройти test-gate; fallback: ручная inspection компонентов + type-check. Это документируется в SUMMARY с явной меткой «vitest not installed».

---

## Сроки и контекст

- Wave 1 (02-01): ~50% context на main task (T-02-01-3) — большой план, требует свежий context. **Рекомендация**: execute-phase запускает один воркер на Wave 1, после завершения /clear перед Wave 2.
- Wave 2 (02-02, 02-03, 02-04): параллельно 3 воркера, каждый ~30-40% context. Между ними нет блокировок (после Wave 1 контракты заморожены). **Рекомендация**: 3 parallel agents.
- Wave 3 (02-05): один воркер, ~20% context. Самый маленький план.

---

## Self-Check

- [x] Все 5 PLAN-файлов созданы по канону `{phase}-{NN}-PLAN.md`
- [x] Frontmatter содержит все required поля (phase, plan, type, wave, depends_on, files_modified, autonomous, requirements, must_haves)
- [x] Каждый план содержит objective, context, 2-4 tasks, out-of-scope, risks, verification, test_strategy, references, success_criteria, output
- [x] Каждая задача имеет files, action, verify (automated), done
- [x] Wave 2 параллельность подтверждена анализом пересечений файлов
- [x] REQ coverage 16/16 (включая explicit OOS для TRACE-03)
- [x] Out-of-Scope явно перечислен по всей фазе
- [x] Никаких placeholder/TODO/«доделать позже» в плановых acceptance criteria
- [x] Karpathy Simplicity First: каждый план — минимум tasks для real value
- [x] Brutal honesty: открытые вопросы 1-6 явно перечислены

---

*Phase 2 planning complete: 2026-05-14*
*Next step: `/gsd-execute-phase 02-mvp-chat` (либо параллельные agents по wave)*
