# Чек-лист «От v1.2.17 к коммерческой v1.3.0»

> Создан 2026-05-22 после глубокого ревью 9 направлений (architecture/backend/frontend/security/tests/UX/perf/completeness/devops). Базовый отчёт: ответ ассистента в сессии «глубокое ревью приложения».
>
> Принципы:
> - Каждый пункт = 1 атомарный коммит (или ≤3 если pure mechanical).
> - Файлы и строки указаны конкретно — никаких «дорабатываем интеграцию».
> - У каждого пункта есть приёмочный критерий и тест-проверка.
> - Брутальная честность: не помечать ✓ без реального прогона тестов / smoke.
> - GSD-style: фаза → wave → ticket.

---

## Метрика прогресса

```
Wave 1 (CRITICAL, до пилота)     [ 0/9  ]   0%
Wave 2 (HIGH, до коммерции)      [ 0/14 ]   0%
Wave 3 (MEDIUM, polish)          [ 0/15 ]   0%
Wave 4 (Release v1.3.0)          [ 0/5  ]   0%
                                  ─────────
Total                              0/43    0%
```

---

## Phase 0 — Подготовка

### 0.1 Зафиксировать незакоммиченные изменения
**Где:** working tree `main` ветка
**Текущее состояние:** 18 модифицированных файлов + новые `.planning/UI-REVIEW-2026-05-21.md`, `.planning/ui-reviews/`, `frontend/lib/llm-providers.ts`, `desktop/resources/` etc.
**Действия:**
1. Прогнать `git diff` по каждому файлу, понять смысл изменений
2. Либо закоммитить ОДНИМ атомарным коммитом «WIP: design-tokens + light-theme audit fixups» (если это незавершённая работа от прошлой сессии)
3. Либо откатить через `git restore` (если случайно)
**Приёмка:** `git status --short` → пусто (кроме новых отчётов в `.planning/`)
**Тест:** `git status` чист
**Оценка:** 30 мин

### 0.2 Создать feature ветку v1.3.0
**Действия:** `git checkout -b feature/v1.3.0-commerce`
**Приёмка:** `git branch --show-current` → `feature/v1.3.0-commerce`
**Оценка:** 2 мин

### 0.3 Записать baseline метрики
**Действия:**
- pytest count + coverage (целевое: 11→60% на критичных)
- vitest count
- E2E spec count (3/5 skipped)
- ruff warnings
- TypeScript strict errors
**Артефакт:** `.planning/BASELINE-2026-05-22.md`
**Оценка:** 20 мин

---

## Wave 1 — CRITICAL (8–12 часов) — БЛОКЕРЫ ПИЛОТА

### 1.1 Убрать API ключ MiMo из installer (.env в dist)
**Где:**
- `desktop/resources/.env` (в `.gitignore` ✓, но попадает в installer)
- `desktop/electron-builder.yml` — секция `extraResources` или `files`
- `desktop/main.js:84-85` — `cwd: resourcesDir` для backend.exe
- `backend/app/config.py` — fallback на env

**Проблема:** Если пилотный installer раздают N аналитикам, все они получают один ключ MiMo. Квота уходит при компрометации.

**Действия:**
1. Прочитать `desktop/resources/.env` — что там реально (тип ключей)
2. Если есть `DEFAULT_LLM_API_KEY_*` — удалить
3. Сделать onboarding обязательным: при первом запуске аналитик вводит свой ключ
4. Альтернатива (если бизнес-модель «ключ выдаём мы»): proxy-сервис на нашей стороне, аналитик получает короткоживущий токен, выданный по логину
5. Обновить `НАЧНИ ЗДЕСЬ.txt` — убрать инструкцию о работе «из коробки»

**Приёмка:**
- `find desktop -name ".env" -exec strings {} \;` не показывает реальный ключ в installer
- Onboarding wizard блокирует переход без введённого ключа
- Если есть .env — он пустой шаблон

**Тест:** установить v1.3.0 на чистую машину → onboarding требует ключ → введён → чат работает

**Оценка:** 2 часа

### 1.2 Keyword-scanner на execute_query
**Где:**
- `backend/app/orchestrator/safety.py` — найти `scan_for_dangerous` или эквивалент
- `backend/app/orchestrator/loop.py` — там где dispatch tool_call (искать `tool_name == "execute_code"`)

**Проблема:** execute_code защищён, execute_query — нет. LLM может выполнить `УДАЛИТЬ` или `ОЧИСТИТЬ` запрос в 1С.

**Действия:**
1. Прочитать `safety.py`: какие ключевые слова детектятся
2. Расширить scanner на execute_query с теми же словами: УДАЛИТЬ, ОЧИСТИТЬ, DROP, DELETE, TRUNCATE, INSERT, UPDATE
3. Для execute_query — даже SELECT с UPDATE/DELETE-семантикой через хитрые JOIN-ы должен триггерить confirm
4. Добавить unit-тест в `backend/tests/test_orchestrator_safety.py`

**Приёмка:**
- `safety.scan_query(text)` возвращает `dangerous=True` для текстов с УДАЛИТЬ/DROP
- При вызове LLM `execute_query("УДАЛИТЬ ИЗ ...")` — `confirm_required` SSE event

**Тест:** `pytest backend/tests/test_orchestrator_safety.py -k execute_query -v`

**Оценка:** 1.5 часа

### 1.3 Лимит MAX_TOOL_CALLS_PER_TURN
**Где:**
- `backend/app/orchestrator/iteration_budget.py` (уже есть LLM iteration budget)
- `backend/app/orchestrator/loop.py` — место подсчёта tool_call внутри одного turn

**Проблема:** LLM теоретически может вызвать 50 execute_query за один turn — DoS базы 1С + $$ за токены.

**Действия:**
1. Добавить в `iteration_budget.py`: `tool_calls_per_turn: int = 0`, max = 8 (конфиг)
2. В `loop.py` инкрементировать после каждого MCP call
3. При превышении — `error_stop` SSE event с понятным сообщением «Слишком много обращений к 1С за один запрос. Переформулируйте.»
4. Конфиг через `Settings` (`config.py`): `MAX_TOOL_CALLS_PER_TURN = 8`

**Приёмка:**
- Тест: 10 forced tool calls → останов на 9-м с error
- Метрика `tool_call_count` пишется в trajectory log

**Тест:** новый pytest `test_orchestrator_loop_tool_budget.py`

**Оценка:** 1.5 часа

### 1.4 Rate-limit /chat endpoint
**Где:**
- `backend/app/routes/chat.py`
- `backend/pyproject.toml` — добавить `slowapi>=0.1.9`

**Проблема:** UI-баг или DoS могут спамить /chat → backend перегружен.

**Действия:**
1. `pip add slowapi` в `pyproject.toml`
2. В `main.py`: `limiter = Limiter(key_func=get_remote_address)`, `app.state.limiter = limiter`
3. `chat.py`: декоратор `@limiter.limit("10/minute")`
4. При превышении: SSE event `rate_limit_exceeded` или HTTP 429

**Приёмка:**
- 11-й запрос за минуту → 429
- Тест нормальной работы (1 запрос/несколько секунд)

**Тест:** новый pytest `test_chat_rate_limit.py`

**Оценка:** 1 час

### 1.5 Утечка LLMClient при GeneratorExit
**Где:** `backend/app/orchestrator/loop.py:1029-1033` — `finally` блок

**Проблема:** `await mcp.aclose()` есть, но LLMClient (httpx) при обрыве SSE может не закрыться → утечка connection pool.

**Действия:**
1. Прочитать `clients/llm.py` — как LLMClient управляет lifecycle
2. Если LLMClient инстанцируется в `loop.py` — обернуть в try/finally с `await llm.aclose()` в finally
3. Если LLMClient managed externally — проверить shutdown event handler

**Приёмка:**
- 100 обрывов SSE → нет утечки httpx connections (lsof / netstat baseline)

**Тест:** stress-test через скрипт `scripts/stress-sse-disconnect.py`

**Оценка:** 1.5 часа

### 1.6 XSS защита Prism в CodeCard
**Где:**
- `frontend/lib/highlight.ts:44` — `Prism.highlight(code, grammar, language)`
- `frontend/components/cards/CodeCard.tsx:140` — `dangerouslySetInnerHTML`

**Проблема:** Prism не санирует HTML на входе. Untrusted code из LLM ответов может содержать `</span><script>`.

**Действия:**
1. В `highlight.ts:44`: ввести `escapeHtml(code)` перед `Prism.highlight()`
2. Функция escapeHtml: заменить `&<>"'` на HTML-entities
3. Альтернатива (безопаснее): подключить DOMPurify и санировать output Prism

**Приёмка:**
- Тест: input `'</code></pre><img src=x onerror=alert(1)>'` → не выполняется JS
- Visual regression: подсветка BSL/SQL продолжает работать

**Тест:** новый vitest `__tests__/highlight.test.ts` с XSS payload

**Оценка:** 1 час

### 1.7 AbortController в useChatStream
**Где:** `frontend/components/chat/useChatStream.ts:105`

**Проблема:** При навигации со страницы `/sessions/[id]` async generator продолжает setState на размонтированный компонент.

**Действия:**
1. Завести `const abortRef = useRef<AbortController | null>(null)`
2. В `send()`: `abortRef.current = new AbortController()`, передать `signal` в `fetchChat`
3. В `useEffect` cleanup: `abortRef.current?.abort()`
4. Обработать `AbortError` в try/catch (не показывать как ошибку)

**Приёмка:**
- Тест: открыть чат → отправить → быстро уйти на /settings → нет ошибок в console, нет setMessages после unmount

**Тест:** новый vitest `useChatStream.test.tsx` с rerender + cleanup

**Оценка:** 1 час

### 1.8 Sprint 3 Hermes Learning — wire-up в runtime
**Где:**
- `backend/app/orchestrator/loop.py:468` — `# Sprint 3 (Hermes A8/A9/D3): skill store + usage telemetry per канал.`
- `loop.py:489-491` — TODO `todo_add/todo_complete/todo_list`
- `loop.py:524` — `# + skills block (Sprint 3)`
- `loop.py:531` — `# Sprint 3 (A9): инкрементим usage`
- `backend/app/learning/background_review.py` — раскомментировать `asyncio.create_task`
- `backend/app/learning/skill_store.py` — `inject_into_prompt`
- `backend/app/orchestrator/auxiliary.py:5,10` — Sprint 5 auxiliary LLM

**Проблема:** STATE.md заявляет «M6 Sprint 3 Self-Learning COMPLETE, 6 фич, +75 pytests». Файлы написаны. Но в runtime НЕ вызываются. USP «самообучение» не работает.

**Действия:**
1. Прочитать каждый модуль `learning/`
2. В `build_system_prompt`: вызвать `skill_store.inject_skills(channel_id, max=5)` — топ-5 skills per channel
3. После successful turn (`await persistence.save_turn(...)`): `asyncio.create_task(background_review_fork(channel_id, turn_id, ...))`
4. В `background_review.py`: должен сравнить trajectory с skills, обновить usage, возможно curate
5. Включить опциональный `clarify_question` internal tool (Sprint 4 Hermes D1) если LLM явно запросит
6. Включить `todo_add/todo_complete/todo_list` internal tools (Sprint 4)

**Приёмка:**
- Smoke: 5 turns подряд с похожими вопросами → во 2-м turn skills видны в system prompt (через trace)
- `skill_usage_count` инкрементируется в `skill_store`
- background_review создаёт записи в `usage_log` через 5-10 сек

**Тест:**
- `pytest backend/tests/test_learning_integration.py` — новый интеграционный
- E2E playwright: проверить что `data-skill-injected` атрибут есть в trace

**Оценка:** 6 часов

### 1.9 Обновить STATE.md и удалить ложные заявления о M6 COMPLETE
**Где:** `.planning/STATE.md`

**Проблема:** STATE.md заявляет «M6 Hermes Integration ✓ COMPLETE» и «30/30 фич». Из 30 фич ~6 (Sprint 3 + clarify + todo) не были wired в runtime.

**Действия:**
1. Изменить статус Sprint 3 на «code-only complete, runtime wired in v1.3.0»
2. Добавить раздел «Honesty gap closed in v1.3.0» с детальным списком
3. Обновить «Last commit» и progress метрику

**Приёмка:** STATE.md отражает реальное состояние

**Оценка:** 30 мин

---

## Wave 1 Итог
**Время:** 16 часов (с буфером) — реалистично 2 рабочих дня
**Эффект:** пилот можно проводить безопасно. Critical уязвимости устранены. Sprint 3 заработал в runtime.
**Commit gate:** все 9 тикетов выполнены + green CI + smoke

---

## Wave 2 — HIGH (40–60 часов) — БЛОКЕРЫ КОММЕРЦИИ

### 2.1 Декомпозиция loop.py (1157 строк → 4 функции по 200-300)
**Где:** `backend/app/orchestrator/loop.py:372-1158` — `run_chat_loop()`

**Проблема:** God-функция, 12 ответственностей. M7 без рефакторинга невозможен.

**Действия (хирургические, не архитектурные):**
1. Выделить `_initialize_loop_context()` из строк 394-510 → новый файл `orchestrator/loop_init.py`
2. Выделить `_build_system_prompt_with_context()` из 525-557
3. Выделить `_handle_tool_call()` из 813-1019 → `orchestrator/loop_tool_handler.py`
4. Выделить `_finalize_turn()` из 1034-1131 → `orchestrator/loop_finalize.py`
5. `run_chat_loop` оставить только координацию + `while True` с ≤80 строками тела
6. Перенести `INTERRUPTS`, `_pending`, `CLARIFY` глобальные структуры в `LoopContext` dataclass (передаётся через параметры)

**Приёмка:**
- `wc -l backend/app/orchestrator/loop.py` < 400
- Все 652 backend pytests зелёные
- E2E ручной: 5 разных prompts проходят без изменений в SSE-выходе

**Тест:** существующая тестовая база + snapshot SSE-выходов

**Оценка:** 10 часов

### 2.2 Multi-tenant изоляция глобальных структур
**Где:**
- `backend/app/orchestrator/interrupt.py` — `INTERRUPTS` глобальный dict
- `backend/app/orchestrator/safety.py:70` — `_pending` глобальный dict
- `backend/app/orchestrator/clarify.py` — `CLARIFY` глобальный

**Проблема:** multi-tenant изоляция per-session, не per-channel. Гонки при concurrent retry на одну сессию.

**Действия:**
1. Завести `LoopContext(session_id, channel_id)` dataclass
2. Переместить per-session state в context
3. Глобальные структуры → `ContextRegistry` с TTL-eviction
4. Добавить тест: 100 concurrent /chat в один channel → нет cross-contamination

**Приёмка:** stress-test с 100 concurrent passes без cross-session data leaks

**Оценка:** 4 часа

### 2.3 Code signing installer
**Где:** `desktop/electron-builder.yml`

**Проблема:** SmartScreen блокирует corporate install. README документирует «выполнить в любом случае» — несерьёзно для продажи.

**Действия:**
1. Купить EV Code Signing certificate (DigiCert или Sectigo, ~$300/год)
   - **Альтернатива дёшево:** OV (~$80/год), но SmartScreen warning сохраняется первые 3-6 месяцев пока не накопится reputation
2. В `electron-builder.yml`:
   ```yaml
   win:
     certificateFile: ${CSC_LINK}
     certificatePassword: ${CSC_KEY_PASSWORD}
     publisherName: "Khvorostov Nikita" (или ИП/ООО)
   ```
3. CI variables: CSC_LINK + CSC_KEY_PASSWORD
4. Build smoke: устанавливаем на чистый Windows → нет SmartScreen warning ИЛИ есть «известный издатель»

**Приёмка:** установка на чистый Win10/11 без предупреждений

**Оценка:** 4 часа (без учёта оформления сертификата — 1-3 дня административно)

### 2.4 Auto-update через electron-updater
**Где:**
- `desktop/package.json` — добавить `electron-updater`
- `desktop/main.js` — после `whenReady`
- `desktop/electron-builder.yml` — секция `publish`
- GitHub Releases workflow

**Проблема:** Аналитик не будет вручную скачивать v1.3.1 → застрянет на v1.3.0.

**Действия:**
1. `npm i electron-updater` в desktop/
2. `main.js`: после `mainWindow.show()` → `autoUpdater.checkForUpdatesAndNotify()`
3. `electron-builder.yml`:
   ```yaml
   publish:
     provider: github
     owner: nikitakhvorostov1912-beep
     repo: analyst-workspace-design
   ```
4. GitHub Action `.github/workflows/release.yml`: triggered on tag `v*`, билдит + публикует через `softprops/action-gh-release`
5. UI: при наличии обновления — non-blocking toast «Доступна v1.3.1, обновить?»

**Приёмка:**
- Релиз v1.3.0-test → клиент с v1.2.17 → получает уведомление об обновлении
- Скачивание + перезапуск работает

**Тест:** manual smoke на двух Win машинах

**Оценка:** 6 часов

### 2.5 E2E coverage критичного пути
**Где:** `frontend/e2e/`

**Проблема:** 3 spec'а заскипано (`setup-and-prompt`, `sessions-history`, `channel-switch`). Главный happy-path не покрыт.

**Действия:**
1. Переписать `setup-and-prompt.spec.ts` под `setupOnboardingMocks` паттерн (как `onboarding.spec.ts`)
2. Сценарии:
   - Send message → receive SSE → see TableCard
   - Send query that triggers confirm → confirm → tool call → result
   - Tool error → retry → success
   - Interrupt → cancel mid-stream
3. Переписать `sessions-history.spec.ts`:
   - Create 3 sessions → switch → history loads correctly
   - Delete session → confirm dialog → removed
4. Переписать `channel-switch.spec.ts`:
   - 2 channels in config → switch → MCP tools change → cards from different channel

**Приёмка:** 5/5 E2E spec'ов зелёные, не skipped

**Оценка:** 6 часов

### 2.6 Test coverage критичных модулей до 60%
**Где:** `backend/tests/`

**Целевые модули:**
- `loop.py` 11% → 60%
- `persistence.py` 13% → 60%
- `mcp_pool.py` 15% → 70%
- `cards.py` 28% → 60%
- `compressor.py` 22% → 50%

**Действия:**
1. `test_mcp_pool.py` — новый файл: initialize_all, list_all_tools (dedup), client_for routing
2. `test_orchestrator_loop_extended.py`: multi-tool chain (3+ tools), iteration budget exhaustion, interrupt mid-execution, compressor trigger, prompt_caching activation
3. `test_orchestrator_persistence_extended.py`: параметризованные load_history с разными role mix
4. `test_orchestrator_cards_extended.py`: type detection для всех 6 типов карточек
5. `test_compressor_integration.py`: long history → compressed → continued

**Приёмка:** `pytest --cov=app --cov-report=term-missing` показывает ≥60% на критичных

**Оценка:** 8 часов

### 2.7 Robust prompt-injection (заменить regex на llm-guard или аналог)
**Где:** `backend/app/memory/injection_scan.py`

**Проблема:** 40/100 эффективность против реальных атак (base64, Unicode homoglyphs, многострочные `\n\n`, JSON-encoded).

**Действия:**
1. Исследовать `llm-guard`, `rebuff`, `prompt-shield` (web research)
2. Выбрать (вероятно llm-guard — open source, поддерживает asyncio)
3. Заменить scan() в `injection_scan.py` на вызов llm-guard
4. Сохранить fallback regex для случаев когда llm-guard недоступен
5. Добавить расширенные паттерны для русского ("проигнорируй", "не учитывай", "перезапустись")
6. Тестировать на 20 реальных attack payloads (можно с https://gandalf.lakera.ai/ или OWASP LLM-AI list)

**Приёмка:**
- ≥85% detection rate на тестовом наборе атак
- false positive rate ≤5% на нормальных запросах

**Оценка:** 6 часов

### 2.8 Backend Dockerfile multi-stage + non-root user
**Где:** `backend/Dockerfile`

**Действия:**
1. Multi-stage build:
   ```dockerfile
   FROM python:3.12-slim AS builder
   COPY pyproject.toml .
   RUN pip install --no-cache-dir --target=/deps .
   
   FROM python:3.12-slim
   RUN useradd --create-home --shell /bin/bash appuser
   USER appuser
   COPY --from=builder /deps /usr/local/lib/python3.12/site-packages
   COPY app /app
   WORKDIR /app
   CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
   ```
2. Кеширование: `COPY pyproject.toml` отдельным слоем от `COPY app`

**Приёмка:**
- Размер образа уменьшен на ≥30%
- `docker run --user=root` → permission denied на write в `/app`

**Тест:** `docker build backend/ -t analyst-backend:test && docker run analyst-backend:test`

**Оценка:** 1 час

### 2.9 docker-compose.yml для prod
**Где:** `docker-compose.yml`

**Действия:**
1. Добавить `healthcheck` на backend:
   ```yaml
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:8010/health"]
     interval: 30s
     timeout: 10s
     retries: 3
   ```
2. NEXT_PUBLIC_BACKEND_URL — через ARG/ENV
3. Зафиксировать версии образов (`:1.3.0` не `:latest`)
4. Разделить `docker-compose.dev.yml` и `docker-compose.prod.yml`

**Приёмка:** `docker compose up` стартует с healthcheck, на prod-проф фронт получает правильный backend URL

**Оценка:** 1 час

### 2.10 CI: docker build job
**Где:** `.github/workflows/ci.yml`

**Действия:** добавить job:
```yaml
docker-build:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Build backend
      run: docker build backend/ -t analyst-backend:ci
    - name: Build frontend
      run: docker build frontend/ -t analyst-frontend:ci
```

**Приёмка:** PR с broken Dockerfile → red CI

**Оценка:** 30 мин

### 2.11 Cross-card deanonymization
**Где:**
- `backend/app/routes/log_cards.py:117` — `submit_for_deanonymization`
- `backend/app/orchestrator/persistence.py` — добавить таблицу `anon_tokens(session_id, card_id, token, real_value)`

**Действия:**
1. Создать миграцию v9: `anon_tokens` таблица
2. При создании карточки с anon — сохранять токены в registry per session
3. При раскрытии — искать в session-wide registry (не только в card)
4. UI: показать «уже раскрыто в карточке X» если токен уже разрешён

**Приёмка:**
- Test: 2 карточки с одним токеном → раскрыть в одной → во второй автоматически раскрыто
- Audit log создаётся (опционально, Wave 3)

**Оценка:** 4 часа

### 2.12 README — актуальная ссылка на Release
**Где:** `README.md`

**Действия:**
1. Заменить ссылку с v1.0.0 на actual latest release (на момент: v1.2.17, после релиза — v1.3.0)
2. Убрать фразу «получите у разработчика через USB»
3. Добавить раздел «Install» с link на GitHub Releases
4. Добавить badges (build status, version, license)

**Оценка:** 30 мин

### 2.13 Audit log раскрытия anon-токенов
**Где:** новая таблица + route

**Действия:**
1. Миграция v10: `deanonymization_audit(timestamp, session_id, card_id, token, user_action)`
2. При каждом раскрытии — запись
3. Route `/admin/audit/deanonymization` (admin only)
4. UI: список в `/insights` или `/status`

**Приёмка:** все раскрытия видны в audit log

**Оценка:** 2 часа

### 2.14 Slash-команды (минимум /sql и /journal)
**Где:** `frontend/components/chat/CommandPalette.tsx`

**Действия:**
1. Расширить `commands` array:
   - `/sql <text>` → шаблон system message: «Выполни SQL-запрос: <text>»
   - `/journal <фильтр>` → шаблон для get_event_log
   - `/find <термин>` → search_metadata
   - `/audit <раздел>` → проверка прав
2. При выборе команды — подставить шаблон в input, фокус на input для дозаполнения

**Приёмка:** все 4 команды работают, при `/sql ВЫБРАТЬ *` подставляется правильный шаблон

**Оценка:** 2 часа

---

## Wave 2 Итог
**Время:** 55 часов (с буфером) — реалистично 1 рабочая неделя
**Эффект:** коммерческая версия. Code signing + auto-update + Sprint 3 wired + test coverage — все блокеры закрыты.

---

## Wave 3 — MEDIUM polish (20–30 часов)

### 3.1 UI: hardcoded цвета → токены (6 файлов)
**Где:**
- `frontend/components/cards/MetricCard.tsx:67,97`
- `ObjectCard.tsx:231`
- `TableCard.tsx:257`
- `LogCard.tsx:166`
- `CodeCard.tsx:118`
- `MentionPopover.tsx:94`
- `settings/page.tsx:87` — `border-red-800`

**Действия:** замена `text-emerald-400`/`text-rose-400`/`text-amber-400` → `var(--success/error/warning)`

**Оценка:** 30 мин

### 3.2 StreamingStages — маппинг tool names
**Где:** `frontend/components/chat/StreamingStages.tsx:129`

**Действия:** добавить mapping snake_case → русские человеческие фразы
```ts
const TOOL_LABELS = {
  execute_query: "Выполняю запрос",
  execute_code: "Выполняю код",
  get_metadata: "Читаю структуру",
  get_object_by_link: "Читаю объект",
  get_event_log: "Читаю журнал",
  find_references_to_object: "Ищу ссылки",
  get_access_rights: "Проверяю права",
  get_bsl_syntax_help: "Справка BSL",
  submit_for_deanonymization: "Раскрываю данные",
  get_link_of_object: "Получаю ссылку",
};
```

**Приёмка:** аналитик не видит `execute_query` в UI

**Оценка:** 30 мин

### 3.3 SQLite PRAGMA tuning
**Где:** `backend/app/storage/db.py:23` (после WAL)

**Действия:**
```python
await db.execute("PRAGMA synchronous=NORMAL")
await db.execute("PRAGMA cache_size=-64000")  # 64MB
await db.execute("PRAGMA temp_store=MEMORY")
await db.execute("PRAGMA foreign_keys=ON")
```

**Приёмка:** smoke pass, бенчмарк `pytest backend/tests/test_persistence_bench.py` показывает +15-30% writes

**Оценка:** 30 мин

### 3.4 httpx.AsyncClient reuse в AuxiliaryClient
**Где:** `backend/app/orchestrator/auxiliary.py:87`, `routes/llm_config.py:207`

**Действия:** вынести AsyncClient в `__init__` как `self._http`, `aclose()` в shutdown

**Оценка:** 1 час

### 3.5 Frontend lazy load (Recharts, Markdown, Prism)
**Где:** `frontend/components/cards/ChartCard.tsx`, `Markdown.tsx`, `CodeCard.tsx`

**Действия:** `next/dynamic({ ssr: false })` для тяжёлых импортов

**Приёмка:** initial bundle ↓ на ≥100KB

**Оценка:** 1 час

### 3.6 React.memo на Message/Card
**Где:** `frontend/components/chat/Message.tsx`, всё в `cards/`

**Действия:** обернуть Message в `React.memo` с custom `arePropsEqual`

**Приёмка:** профайлер показывает что Message не re-render на каждый delta event

**Оценка:** 1 час

### 3.7 React keys fix (key={i})
**Где:** `TableCard.tsx:162,187,190`, `ObjectCard.tsx:59,69,71`

**Действия:** key={col.name} для колонок, key={JSON.stringify(row)} для строк

**Оценка:** 30 мин

### 3.8 a11y: aria-live на StreamingStages
**Где:** `frontend/components/chat/StreamingStages.tsx`

**Действия:** `<div role="status" aria-live="polite">` обёртка над стадиями

**Оценка:** 20 мин

### 3.9 a11y: aria-sort на TableCard headers
**Где:** `frontend/components/cards/TableCard.tsx:159`

**Действия:** `scope="col"`, `aria-sort={sortDir}`

**Оценка:** 30 мин

### 3.10 Button focus ring → 2px
**Где:** `frontend/components/ui/button.tsx:7`

**Действия:** `focus-visible:ring-1` → `focus-visible:ring-2 focus-visible:ring-offset-2`

**Оценка:** 20 мин

### 3.11 Estimated tokens через tiktoken (вместо 0)
**Где:** `backend/app/orchestrator/insights.py:62,203`

**Действия:** `tiktoken.get_encoding("cl100k_base")` + проксирование на `count_tokens(text)`

**Приёмка:** insights показывают реальные числа

**Оценка:** 1 час

### 3.12 ARCHITECTURE.md обновление
**Где:** `ARCHITECTURE.md`

**Действия:** добавить 8 новых routers + Hermes-слои + schema v8

**Оценка:** 1 час

### 3.13 CHANGELOG.md
**Где:** новый `CHANGELOG.md`

**Действия:** Keep a Changelog format, v0.1.0 → v1.3.0

**Оценка:** 1.5 часа

### 3.14 ENV vars документация
**Где:** новый `docs/ENV-VARS.md`

**Действия:** все env переменные с типами, дефолтами, обязательность

**Оценка:** 1 час

### 3.15 CORS allow_methods сужение
**Где:** `backend/app/main.py:67-69`

**Действия:** `allow_methods=["GET", "POST", "DELETE", "OPTIONS"]`, `allow_credentials=False` (если не используются cookies)

**Оценка:** 20 мин

---

## Wave 3 Итог
**Время:** 12 часов (с буфером)
**Эффект:** UX/perf polish. После Wave 3 — продукт «причёсан».

---

## Wave 4 — Release v1.3.0

### 4.1 Smoke test полный
**Действия:**
1. Чистая VM Windows 10/11
2. Установить v1.3.0 installer
3. Запустить onboarding
4. Подключить MCP Toolkit
5. Ввести LLM ключ
6. Отправить 5 разных prompts: метаданные, запрос, журнал, объект, навыки (skill injection check)
7. Проверить multi-channel switch
8. Проверить sessions history
9. Проверить anonymization
10. Trigger auto-update mock

**Приёмка:** `.planning/SMOKE-v1.3.0.md` все 10 пунктов ✓

**Оценка:** 2 часа

### 4.2 Quality gate
**Действия:** запустить `/awd-quality-gate` skill (он есть в проекте)
- pytest зелёный
- vitest зелёный
- pnpm build clean
- playwright 5/5 зелёные

**Приёмка:** PASS

**Оценка:** 30 мин (если что-то падает — fix)

### 4.3 Build v1.3.0
**Действия:**
1. `npm run build` в frontend (standalone)
2. `pyinstaller build.spec` в backend
3. `electron-builder --win --x64` в desktop
4. Подписать installer (Code signing)
5. Артефакт: `1C-Analyst-v1.3.0/analyst-setup-v1.3.0.exe`

**Приёмка:** installer запускается на чистой Win10, нет SmartScreen warning

**Оценка:** 1 час

### 4.4 Release notes
**Где:** `1C-Analyst-v1.3.0/RELEASE-NOTES.md` + GitHub Release body

**Действия:** аналогично `1C-Analyst-v1.2.17/НАЧНИ ЗДЕСЬ.txt`, плюс «Что нового в v1.3.0»

**Оценка:** 1 час

### 4.5 GitHub Release + tag
**Действия:**
1. `git tag v1.3.0 && git push --tags`
2. GitHub Release с installer + release notes
3. Обновить ссылку в README

**Приёмка:** Release виден публично, installer доступен

**Оценка:** 30 мин

---

## Итоги

| Wave | Часов | Что закрывает |
|---|---:|---|
| 0 | 1 | Подготовка ветки + baseline |
| 1 | 16 | Critical уязвимости + Sprint 3 wire-up |
| 2 | 55 | Code signing, auto-update, test coverage, decompose loop.py |
| 3 | 12 | UX polish, perf tuning, docs |
| 4 | 5 | Release v1.3.0 |
| **Total** | **89 часов** | Готовая коммерческая версия |

**Реалистичный график:**
- 1 человек full-time: **2.5 рабочих недели**
- 1 человек part-time (4ч/день): **5 недель**

**Критический путь:** 1.1 → 1.2 → 1.3 → 1.4 → 1.8 → 2.1 → 2.3 → 2.4 → 4.1 → 4.3 → 4.5

**Параллелизуемое:** UI polish (Wave 3) можно делать в любом порядке, не блокирует.

---

## Договорённости

- Каждый ticket = 1 атомарный коммит (если можно)
- После каждого коммита: pytest + vitest + tsc должны быть зелёные
- При FAIL: stop, разобрать, исправить, не двигаться дальше
- Правило 3 итераций (Матаков): если ticket требует >3 итераций — переформулировать spec
- При завершении waves обновлять `.planning/STATE.md`
