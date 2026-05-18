# Phase 10 — LEARN Engine: DEFERRED

**Status:** DEFERRED to separate milestone M6 (after v1.2.0 release)
**Reason:** Polynomial scope (3 plans, ~5 hours engineering + careful testing) + high regression risk

---

## Что Phase 10 требует

### Backend (rough)

1. **sqlite-vec dependency** install + `enable_load_extension(True)` + `load_extension(sqlite_vec.loadable_path())`
2. **Migration v6** — `CREATE VIRTUAL TABLE message_embeddings USING vec0(message_id INTEGER PRIMARY KEY, embedding FLOAT[1536])`
3. **EmbeddingsService** — OpenAI-compatible HTTP client (`POST /embeddings` with `Authorization: Bearer ...`)
4. **Background indexer** — asyncio task, 60s interval, batch-encode new messages
5. **RAG retrieve endpoint** — `POST /learn/retrieve { query: str, k: int }` → top-k semantic matches
6. **Orchestrator integration** — добавить `learn_lookup` стадию между `thinking` и `tool_call` в SSE
7. **Settings storage** — `learn_settings` table (api_key, endpoint, model, dim, enabled flag)

### Frontend (rough)

1. **Settings → Обучение** section — конфиг embeddings provider (endpoint, model, API key in sessionStorage)
2. **«Test» button** — verify endpoint reachable, returns valid vector
3. **UI badge** в AssistantMessage — «🔍 Использовано N прошлых ответов» when `learn` stage был активен
4. **Privacy toggle** — read/write `analyst.learn_enabled` localStorage (уже частично через Onboarding step 3)

### Tests (rough)

- 15+ pytest specs для embeddings + RAG endpoints
- 10+ vitest specs для Settings UI
- E2E Playwright: full RAG round-trip (отправить вопрос → проверить badge → reset → задать снова без обучения)

---

## Что НЕ позволяет сделать сейчас

### 1. Risk PyInstaller bundle breakage

`sqlite-vec` C extension загружается через `enable_load_extension` + `load_extension(path)`. PyInstaller `--onefile` распаковывает dependencies в `%TEMP%\_MEI*` при каждом запуске. Динамическая загрузка `.dll` extension из `_MEI` НЕ работает по умолчанию — нужен `--add-binary` workaround + testing на чистой VM. Регрессия для v1.1.0 desktop installer возможна.

**Mitigation:** Phase 10 должна включать smoke test на чистой VM с проверкой что `vec_version()` запрос работает в installed app, не только в dev mode.

### 2. Risk: orchestrator integration breaking SSE contract

Текущий SSE контракт (Phase 2): `status → delta → tool_call → tool_result → card → done`. Phase 10 добавляет `learn` stage между `status="thinking"` и `tool_call`. Это меняет порядок событий — могут сломаться existing tests `useChatStream.test.tsx` (mock SSE replay), `chat_route_test.py` (asserts on event order).

**Mitigation:** Phase 10 должна обновлять все эти тесты, не только добавлять новые.

### 3. Risk: API key management для embeddings

LLM API key хранится в sessionStorage (security requirement from MSG #10 — «никогда в backend storage»). Embeddings API key — отдельный (может быть отдельный провайдер, например OpenAI для embeddings + Yandex для chat). Это новый pattern — отдельный key in sessionStorage + отдельный header `X-Embeddings-API-Key` в backend.

**Mitigation:** Phase 10 должна расширить existing `migrateLegacyApiKey()` и добавить новый ключ хранения.

### 4. Polynomial scope vs. linear progress

Phase 10 это 3 plans (10-01 vector store + indexer, 10-02 retrieve API, 10-03 privacy controls + Settings UI). Каждый из них L (3-5 часов). Total: 9-15 часов engineering + ~5 часов testing + bug fixes. Это отдельная sprint.

---

## Что Phase 10 разблокирует (когда сделана)

- **MSG #10 requirement «LEARN» закрыт** — система может ссылаться на прошлые ответы
- **v1.3.0 release** — major feature release с обучением на сессиях
- **Phase 11.4 cards refactor** опционально использует learn badge на cards

---

## Phase 11.3 Onboarding step 3 связь

Onboarding wizard **уже спрашивает** про обучение в Phase 11.3 (step 3 Learn opt-in). Сохраняет флаг в `localStorage['analyst.learn_enabled']`.

В Phase 10 implementation должна:
- При старте app читать этот флаг
- Если `learn_enabled === false` — НЕ запускать background indexer
- В Settings → Обучение показать текущее значение + позволить переключить
- При выключении (`enabled → false`) — опция «удалить все embeddings» (drop table content)

Это privacy-first contract: пользователь дал согласие → начинаем индексацию. Отозвал согласие → удаляем индекс.

---

## Acceptance criteria (для будущей реализации)

- [ ] sqlite-vec работает в installed Electron app (smoke на чистой Windows VM)
- [ ] Embeddings settings — endpoint + model + API key + dim + enabled toggle
- [ ] Background indexer — 60s interval, gracefully degrades если provider down
- [ ] RAG retrieve API — top-k семантический поиск с pagination
- [ ] Orchestrator уважает `learn_enabled` флаг
- [ ] UI badge на AssistantMessage когда learn stage был активен
- [ ] Privacy: `enabled → false` → опция «удалить все embeddings»
- [ ] 15+ pytest specs PASS
- [ ] 10+ vitest specs PASS
- [ ] E2E full round-trip PASS

**Estimated effort:** 9-15 часов engineering + 5 часов testing = ~2-3 dedicated dev sessions

---

## Next planning

После v1.2.0 release (manual smoke + tag), запланировать M6 «LEARN Engine» как отдельный milestone с явным scope + risks + dependencies в `ROADMAP.md`.

Альтернатива — оставить Phase 10 как long-running backlog (low priority), фокус на:
- v1.2.0 manual smoke + tag
- Phase 11.4 cards refactor (6 cards через CardHeader)
- Phase 11.5 Playwright design-v2.spec.ts
- Performance / memory optimizations
- User feedback round (после первого распространения v1.2.0)
