# Стратегический план v1.3.0 — коммерческий релиз

**Дата:** 2026-05-23
**Базируется на:** глубокое ревью 2026-05-22 + IDEAS-FROM-STACK / IDEAS-ADDENDUM от 2026-05-21
**Ветка:** `feature/v1.3.0-commerce` (продолжение)
**Цель:** v1.3.0 готовый к продаже корп-клиентам в РФ
**Бюджет времени:** 58 часов работы (~9 рабочих дней)

---

## Принципы

1. **Brutal scope.** Только то, что критично для первой продажи. Никаких «было бы хорошо».
2. **Каждый тикет = 1 атомарный коммит** с тестами.
3. **Hardrules без откладываний:**
   - 152-ФЗ риск закрыт через РФ-ДЦ LLM по умолчанию
   - XSS на API ключи невозможен (backend-only)
   - Crash на больших данных невозможен (ResultSizeGate)
   - Подписанный installer + auto-update
4. **Брутальная честность в STATE.md** — никаких «100% complete» без runtime verify.

---

## Цели и не-цели

### Целимся в

- v1.3.0 можно установить на чистый Win10/11 без SmartScreen warning
- v1.3.0 безопасен по 152-ФЗ из коробки (Cloud.ru Qwen3 default)
- v1.3.0 не утечёт ключи (backend-only)
- v1.3.0 не упадёт на «дай все заказы за год»
- v1.3.0 «самообучение» реально работает в runtime (Sprint 3 wired)
- v1.3.0 — следующая версия одним кликом (auto-update)

### НЕ целимся в

- ❌ Presidio PII Shield (нужен только если LLM не в РФ — у нас default в РФ)
- ❌ Регистрация в реестре операторов ПД (формальность под первого корп-клиента)
- ❌ Langfuse observability (нужен при 5+ клиентах, не сейчас)
- ❌ Cells + Reactive Graph (invasive, риск 3 недели без гарантии adoption)
- ❌ Telegram bot (distraction)
- ❌ Plan→Execute как default (opt-in toggle в Settings)
- ❌ DeepEval framework (нет стабильных prompts + примеров — гадание)
- ❌ Архитектурный refactor loop.py (только хирургия 4 функции, не reшing)

---

## Phase 1 — Хвост Wave 1/2 (30h)

### P1.1 — W1.8 Sprint 3 Hermes Learning wire-up (6h)

**Проблема:** STATE.md заявляет M6 Sprint 3 «100% complete», реально модули `learning/*` написаны но НЕ вызываются из runtime. USP «самообучение» не работает.

**Файлы:**
- `backend/app/orchestrator/loop.py:468` — комментарий `# Sprint 3 (Hermes A8/A9/D3): skill store + usage telemetry per канал.`
- `backend/app/orchestrator/loop.py:489-491` — TODO `todo_add/todo_complete/todo_list`
- `backend/app/orchestrator/loop.py:524` — `# + skills block (Sprint 3) + todo block`
- `backend/app/orchestrator/loop.py:531` — `# Sprint 3 (A9): инкрементим usage`
- `backend/app/learning/background_review.py` — fire-and-forget aux LLM
- `backend/app/learning/skill_store.py` — `inject_skills(channel_id, max=5)` метод

**Что делаем:**
1. Прочитать каждый файл `learning/*` — понять контракты
2. В `build_system_prompt`: вызвать `skill_store.inject_skills(channel_id, max=5)` — топ-5 skills per channel
3. После successful turn (`save_turn`): `asyncio.create_task(background_review_fork(channel_id, turn_id, trajectory))`
4. В `background_review.py`: сравнить trajectory с skills, обновить usage_count, при необходимости curate
5. Раскомментировать `# Sprint 3 (A9): инкрементим usage` на `loop.py:531`
6. Добавить тест `test_learning_integration.py` — smoke: 2 похожих вопроса → во втором skills видны в prompt

**Приёмка:**
- 2 turn'а с похожими вопросами в одном channel → во втором turn `skills` block есть в system prompt (через trace)
- `skill_usage_count` инкрементируется в БД через `skill_store`
- background_review создаёт записи в `usage_log` через 5-10 секунд
- `pytest backend/tests/test_learning_integration.py -v` зелёный
- Все 689 предыдущих pytest зелёные (без регрессий)

**Риск:** background_review через asyncio.create_task без backpressure — добавить `asyncio.Semaphore(3)` для лимита.

---

### P1.2 — W2.1 Хирургическая декомпозиция loop.py (10h)

**Проблема:** `loop.py:372-1158` — God-функция 786 строк тела с 12 ответственностями. M7+ невозможен без декомпозиции.

**Файлы:**
- Исходник: `backend/app/orchestrator/loop.py` (1157 строк)
- Новые: `backend/app/orchestrator/loop_init.py`, `loop_tool_handler.py`, `loop_finalize.py`

**Что делаем (хирургически, не архитектурно):**
1. Выделить `_initialize_loop_context()` из строк 394-510 → `loop_init.py`
2. Выделить `_build_system_prompt_with_context()` из 525-557 → внутри `loop_init.py`
3. Выделить `_handle_tool_call(tc, context)` из 813-1019 → `loop_tool_handler.py`
4. Выделить `_finalize_turn(context, ...)` из 1034-1131 → `loop_finalize.py`
5. `run_chat_loop` оставить только координацию + `while True` ≤80 строк
6. Перенести `INTERRUPTS`, `_pending`, `CLARIFY` глобальные dict'ы в `LoopContext` dataclass

**Приёмка:**
- `wc -l backend/app/orchestrator/loop.py` < 400 (вместо 1157)
- Все 689+ backend pytest зелёные
- 5 snapshot-тестов SSE-выходов (5 prompts: simple text, single tool, multi-tool chain, error, interrupt) — байт-в-байт совпадают с до-рефакторинга

**Риск:** регрессия в SSE-протоколе. Перед рефакторингом — записать snapshot SSE выходов на main, после — сравнить.

---

### P1.3 — W2.3 Code signing installer (4h + 1-3 дня админ)

**Проблема:** SmartScreen блокирует corporate install. README обещает «v1.3.0 будет с подписью».

**Файлы:**
- `desktop/electron-builder.yml` — секция `win.certificateFile`
- `.github/workflows/build.yml` — CSC_LINK + CSC_KEY_PASSWORD secrets
- `desktop/scripts/sign.ps1` — helper для local sign

**Что делаем:**

**Async (параллельно с другими тикетами):**
1. Оформить EV Code Signing certificate — DigiCert/Sectigo, ~300$/год. 1-3 дня админ
   - Альтернатива: OV (~80$), но SmartScreen warning сохраняется первые 3-6 месяцев

**Sync (после получения сертификата):**
2. Зашифровать сертификат в base64, положить в GitHub Secret `CSC_LINK`
3. Пароль — Secret `CSC_KEY_PASSWORD`
4. В `electron-builder.yml`:
   ```yaml
   win:
     certificateFile: ${env.CSC_LINK}
     certificatePassword: ${env.CSC_KEY_PASSWORD}
     publisherName: "Хворостов Никита" (или ИП/ООО когда оформится)
   ```
5. CI: добавить step «verify signature» — `signtool verify /pa dist/*.exe`

**Приёмка:**
- Установка на чистый Win10/11 без SmartScreen warning
- `signtool verify` проходит на собранном exe
- Сертификат не утекает в логи CI

**Риск:** OV vs EV — если бюджет тонкий, начать с OV (быстрее, дешевле), терпеть 3 мес SmartScreen, потом upgrade на EV. Для пилота OV хватит.

---

### P1.4 — W2.4 Auto-update через electron-updater (6h)

**Проблема:** Аналитик не будет вручную качать новый exe. Без auto-update застрянут на v1.3.0.

**Файлы:**
- `desktop/package.json` — `electron-updater` зависимость
- `desktop/main.js` — после `mainWindow.show()`
- `desktop/electron-builder.yml` — `publish:` секция
- `.github/workflows/release.yml` — новый workflow triggered on tag

**Что делаем:**
1. `npm i electron-updater` в `desktop/`
2. `main.js` — после window ready:
   ```js
   import { autoUpdater } from 'electron-updater';
   autoUpdater.checkForUpdatesAndNotify();
   autoUpdater.on('update-available', () => {
     mainWindow.webContents.send('update-available');
   });
   autoUpdater.on('update-downloaded', () => {
     mainWindow.webContents.send('update-ready');
   });
   ```
3. `electron-builder.yml`:
   ```yaml
   publish:
     provider: github
     owner: nikitakhvorostov1912-beep
     repo: analyst-workspace-design
   ```
4. `.github/workflows/release.yml` — triggered on `v*` tag, builds + publishes через `softprops/action-gh-release`
5. UI: новый компонент `UpdateBanner` в Header — non-blocking toast «Доступна v1.3.1, обновить?»
6. IPC: `ipcMain.handle('install-update', () => autoUpdater.quitAndInstall())`

**Приёмка:**
- Релиз v1.3.0-test на GitHub
- Клиент с v1.2.17 получает уведомление через 10-30 секунд после запуска
- Click «Обновить» → скачивание → перезапуск с v1.3.0-test
- Manual smoke на 2 Win машинах

**Риск:** electron-updater требует подписанный installer (см. P1.3). Параллельный путь: пока сертификат оформляется — настраивать code locally с self-signed для теста.

---

## Phase 1 итог

| Тикет | Часов | Закрывает |
|---|---:|---|
| P1.1 | 6 | M6 honesty gap, USP «самообучение» работает |
| P1.2 | 10 | M7+ разблокирован, поддерживаемость |
| P1.3 | 4 | SmartScreen warning, корп-policy |
| P1.4 | 6 | User retention при патчах |
| **Total** | **26** | Production-ready code, distributable |

После Phase 1 — есть рабочий **v1.3.0-beta** без P0 проблем из IDEAS.

---

## Phase 2 — Critical P0 из IDEAS (15h)

### P2.1 — P0-2 Backend-only API key (6h)

**Проблема:** API ключи MiMo/NVIDIA/OpenAI/OpenRouter сейчас живут в `localStorage` через `getLLMApiKey()`. **XSS уносит ключи всех пользователей.** Это активная уязвимость, не теоретическая.

**Контекст:** сейчас в коде:
- `frontend/lib/storage.ts` — `getLLMApiKey()`, `setLLMApiKey(key)`, читают/пишут в `localStorage.analyst.llm_api_key`
- `frontend/lib/api.ts` — `fetchChat()` передаёт ключ в header `X-LLM-API-Key`
- `backend/app/routes/chat.py` — принимает `X-LLM-API-Key`, fallback на `settings.resolve_default_api_key(endpoint)`
- `backend/app/routes/llm_config.py` — GET возвращает `has_env_api_key` per-endpoint флаг

**Что делаем:**
1. **Новая таблица в БД** — `user_secrets`:
   ```sql
   CREATE TABLE user_secrets (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     provider_id TEXT NOT NULL,  -- xiaomi-mimo, nvidia, openai, openrouter, cloud-ru
     api_key_encrypted BLOB NOT NULL,  -- AES-256 GCM
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   CREATE UNIQUE INDEX idx_user_secrets_provider ON user_secrets(provider_id);
   ```
   Encryption key — `app_secret` в `.env`, генерируется при первом запуске Electron.

2. **Backend routes:**
   - `POST /llm-config/secret` — body `{provider_id, api_key}` → шифрует, кладёт в БД, возвращает `{stored: true}`
   - `DELETE /llm-config/secret/{provider_id}` — удаляет
   - `GET /llm-config/secret-status` — возвращает `{provider_id: bool}` — какие провайдеры имеют сохранённый ключ

3. **chat.py** — изменить flow:
   ```python
   # Раньше: api_key из header X-LLM-API-Key
   # Стало: api_key из БД user_secrets по endpoint, fallback на env-fallback
   provider_id = detect_provider(endpoint)
   stored_key = await get_stored_secret(db, provider_id)
   effective_api_key = stored_key or settings.resolve_default_api_key(llm_endpoint)
   ```

4. **Frontend:**
   - `lib/storage.ts` — удалить `getLLMApiKey()`/`setLLMApiKey()`, оставить только `setSecretViaApi()` который зовёт `POST /llm-config/secret`
   - `LLMConfigForm.tsx` — input для ключа теперь триггерит API call, не localStorage
   - `lib/api.ts` `fetchChat()` — БОЛЬШЕ НЕ передаёт `X-LLM-API-Key` header
   - Migration: при первом запуске v1.3.0 — если `localStorage.analyst.llm_api_key` есть → POST на backend → clear localStorage. Показать toast «Ключи теперь хранятся на сервере для безопасности».

5. **Tests:**
   - `test_user_secrets.py` — CRUD encryption, корректный round-trip
   - `test_chat_uses_stored_secret.py` — chat подхватывает ключ из БД
   - vitest: LLMConfigForm теперь зовёт API, не localStorage

**Приёмка:**
- `grep -r "localStorage.*api_key" frontend` пусто
- XSS-payload (eval `localStorage.analyst.llm_api_key`) возвращает null
- Чат работает с ключом из БД
- Migration старого ключа сработает без потери

**Риск:** breaking change для пользователей v1.2.17. Migration обязательна, нельзя пропустить.

---

### P2.2 — P0-3 ResultSizeGate + virtualization (4h)

**Проблема:** MCP `execute_query` без LIMIT может вернуть 50 MB JSON → frontend виснет, LLM не переваривает 100k+ строк.

**Что делаем:**

**Backend (3h):**
1. `backend/app/orchestrator/result_gate.py` — новый модуль:
   ```python
   MAX_ROWS_FOR_LLM = 500
   MAX_PAYLOAD_BYTES = 200_000  # 200 KB total per turn
   
   async def gate_tool_result(db, result, tool_name, tool_args):
       """Возвращает (truncated_result_for_llm, result_id, full_size)."""
       if tool_name == "execute_query" and isinstance(result, dict):
           rows = result.get("rows", [])
           if len(rows) > MAX_ROWS_FOR_LLM:
               result_id = await store_full_result(db, result)
               sample = {
                   "columns": result["columns"],
                   "rows": rows[:MAX_ROWS_FOR_LLM],
                   "total_rows": len(rows),
                   "truncated": True,
                   "result_id": result_id,
                   "sample_size": MAX_ROWS_FOR_LLM,
               }
               return sample, result_id, calc_size(result)
       return result, None, calc_size(result)
   ```
2. `backend/app/orchestrator/loop.py` — после tool_result, перед добавлением в messages → пропустить через `gate_tool_result`
3. `backend/app/routes/log_cards.py` — новый endpoint `GET /tool-results/{result_id}/page?offset=0&limit=1000` для load-more
4. Миграция v9 для таблицы `tool_results_storage`:
   ```sql
   CREATE TABLE tool_results_storage (
     id TEXT PRIMARY KEY,
     session_id TEXT,
     tool_name TEXT,
     payload_json TEXT,
     created_at TIMESTAMP,
     expires_at TIMESTAMP  -- TTL 7 дней
   );
   ```

**Frontend (1h):**
5. `npm i @tanstack/react-virtual`
6. `TableCard.tsx` — добавить virtualization при `rows.length >= 100`:
   ```tsx
   const rowVirtualizer = useVirtualizer({
     count: rows.length,
     estimateSize: () => 36,
     overscan: 10,
   });
   ```
7. При `truncated=true` в payload — баннер «Показаны первые 500 из 50000. [Загрузить все]» + кнопка → batch load

**Приёмка:**
- Запрос «дай 10000 заказов» → LLM получает sample 500 + `result_id`, не виснет
- UI TableCard для 10000 строк работает плавно (60 FPS scroll)
- «Загрузить все» работает batch-ами

**Риск:** изменение формата tool_result может сломать существующие cards. Делаю обратно совместимо (если нет `truncated` поля — старое поведение).

---

### P2.3 — P0-4 SQL AST validator (5h)

**Проблема:** W1.2 keyword-scanner закрывает простые случаи, но LLM может обойти через encoded payloads. AST-валидация надёжнее.

**Что делаем:**
1. `pip install sqlparse` в `pyproject.toml`
2. `backend/app/orchestrator/sql_validator.py`:
   ```python
   import sqlparse
   
   ALLOWED_VERBS_1C = {"ВЫБРАТЬ", "SELECT"}  # только read-only
   FORBIDDEN_VERBS = {
       "УДАЛИТЬ", "DELETE", "ИЗМЕНИТЬ", "UPDATE",
       "ВСТАВИТЬ", "INSERT", "DROP", "TRUNCATE",
       "ALTER", "GRANT", "REVOKE", "EXEC",
   }
   
   def validate_query(query_text: str) -> ValidationResult:
       """Парсит и валидирует. Возвращает status + reason."""
       parsed = sqlparse.parse(query_text)
       if not parsed:
           return ValidationResult.INVALID("not parseable")
       
       for stmt in parsed:
           first_token = stmt.token_first(skip_cm=True)
           if first_token.normalized.upper() in FORBIDDEN_VERBS:
               return ValidationResult.BLOCKED(f"forbidden verb: {first_token}")
       
       return ValidationResult.OK
   ```
3. В `safety.py` — добавить `validate_sql_ast()` помимо keyword scan
4. Tests — 20+ кейсов на known SQL injection patterns

**Приёмка:**
- `SELECT * FROM users; DROP TABLE accounts;--` — blocked даже если keywords скрыты через комментарии
- Нормальные 1С запросы (СОЕДИНЕНИЕ, ПОМЕСТИТЬ, ВЫБРАТЬ ПЕРВЫЕ N) — пропускают

**Риск:** sqlparse может не понять 1С-специфичный синтаксис. Падать → отказывать в выполнении (fail-safe).

---

## Phase 2 итог

| Тикет | Часов | Закрывает |
|---|---:|---|
| P2.1 | 6 | P0-2 XSS на ключи |
| P2.2 | 4 | P0-3 crash на 100k+ строк |
| P2.3 | 5 | P0-4 SQL inject defense-in-depth |
| **Total** | **15** | Production-ready security |

---

## Phase 3 — Cloud.ru Qwen3-Coder pivot (8h)

### P3.1 — Provider catalog: Cloud.ru первой строкой (2h)

**Файлы:**
- `frontend/lib/llm-providers.ts`
- `backend/app/config.py`

**Что делаем:**
1. В `llm-providers.ts` — добавить новый provider первой строкой:
   ```ts
   {
     id: "cloud-ru-qwen3",
     label: "Cloud.ru Qwen3-Coder-480B",
     endpoint: "https://foundation-models.api.cloud.ru/v1",
     keyHint: "sk-...",
     keyDocsUrl: "cloud.ru/foundation-models",
     embedKeyAvailable: false,  // user вводит свой
     models: [
       { id: "Qwen/Qwen3-Coder-480B-A35B-Instruct", label: "Qwen3-Coder-480B", description: "БЕСПЛАТНО, РФ-ДЦ, лучшее на BSL — рекомендуется по умолчанию" }
     ],
     compliance: { russian_dc: true, fz152: true },  // новый флаг для UI badge
   }
   ```
2. `DEFAULT_PRESET_ID = "Qwen/Qwen3-Coder-480B-A35B-Instruct"` (раньше mimo-v2.5-pro)
3. Backend `config.py`:
   ```python
   default_llm_endpoint: str = Field(
       default="https://foundation-models.api.cloud.ru/v1",
       validation_alias="DEFAULT_LLM_ENDPOINT"
   )
   default_llm_model: str = Field(
       default="Qwen/Qwen3-Coder-480B-A35B-Instruct",
       validation_alias="DEFAULT_LLM_MODEL"
   )
   default_llm_api_key_cloud_ru: str = Field(
       default="", validation_alias="DEFAULT_LLM_API_KEY_CLOUD_RU"
   )
   ```
4. `resolve_default_api_key` — добавить case для `cloud.ru` в endpoint

**Приёмка:**
- В Settings → LLM dropdown первой строкой Cloud.ru
- Default endpoint при первом запуске — Cloud.ru
- Badge «РФ-ДЦ ✓ 152-ФЗ» рядом с провайдером в UI

**Риск:** Cloud.ru может изменить URL endpoint. Документировать source date.

---

### P3.2 — Function calling совместимость (3h)

**Что делаем:**
1. Smoke-тест на Cloud.ru — открыть Aether Lab или просто curl:
   ```bash
   curl https://foundation-models.api.cloud.ru/v1/chat/completions \
     -H "Authorization: Bearer $KEY" \
     -d '{"model": "Qwen/Qwen3-Coder-480B-A35B-Instruct", "messages": [...], "tools": [...]}'
   ```
   Проверить что format function calling работает как у OpenAI
2. Если есть расхождения с MiMo:
   - Адаптация в `backend/app/clients/llm.py` — provider-specific tweaks
   - Тесты с FakeLLM имитирующим Cloud.ru response format
3. Проверить streaming (`stream: true`) — формат chunks

**Приёмка:**
- Реальный диалог с Cloud.ru: 3 prompt'а (текст, tool call, multi-tool) — все работают
- Snapshot tests с реальными chunks от Cloud.ru

**Риск:** Cloud.ru может не поддерживать какие-то фичи (например `reasoning_content`). Документировать compatibility matrix.

---

### P3.3 — UI compliance badges + migration UI (2h)

**Что делаем:**
1. `LLMConfigForm` — badge рядом с провайдером:
   - «РФ-ДЦ ✓» — Cloud.ru, YandexGPT, GigaChat
   - «За рубежом — требует согласие» — MiMo, OpenAI, Claude
2. При выборе зарубежного провайдера — модальный диалог:
   ```
   ⚠ Выбран провайдер вне РФ
   
   По 152-ФЗ передача персональных данных в зарубежные системы
   требует согласия субъектов. Корп-клиенты должны подписать
   соответствующее уведомление.
   
   [Я понимаю риски, продолжить]   [Отмена]
   ```
3. Onboarding wizard: на шаге «LLM» — default selected Cloud.ru. С пояснением «бесплатно + в РФ»

**Приёмка:**
- Аналитик при первой установке видит Cloud.ru рекомендованным
- При выборе MiMo/OpenAI/Claude — confirm с предупреждением

---

### P3.4 — Documentation update (1h)

**Что делаем:**
1. `README.md` — секция «LLM Provider» с таблицей сравнения
2. `docs/USER.md` — обновить инструкцию (Cloud.ru как default)
3. `docs/идеи-для-развития/IDEAS-ADDENDUM-2026-05-21.md` — пометить §3.1 как DONE
4. `CHANGELOG.md` — Cloud.ru pivot в Unreleased секции

**Приёмка:**
- README показывает Cloud.ru первым с описанием «бесплатно, в РФ»
- USER.md инструкция понятна аналитику-не-разработчику

---

## Phase 3 итог

| Тикет | Часов | Закрывает |
|---|---:|---|
| P3.1 | 2 | Provider catalog |
| P3.2 | 3 | Function calling совместимость |
| P3.3 | 2 | UI badges + migration UX |
| P3.4 | 1 | Docs |
| **Total** | **8** | 152-ФЗ риск снят through default |

После Phase 3 — продукт **продаваем корпам в РФ без юр. блокеров**.

---

## Phase 4 — Release v1.3.0 (5h)

### P4.1 — Smoke на чистой VM (2h)

1. Развернуть VM Windows 11 чистая
2. Установить v1.3.0 installer (подписанный из P1.3)
3. Onboarding с 0
4. Подключение MCP (требует EPF Toolkit запущенный на хост-машине)
5. Ввод Cloud.ru ключа
6. 10 различных prompts:
   - Простой текст без tool
   - execute_query 100 строк
   - execute_query 5000 строк (проверка ResultSizeGate)
   - execute_query с DROP в тексте (P2.3 SQL validator должен отказать)
   - get_metadata
   - get_event_log с фильтром
   - Multi-tool chain (3 tools подряд)
   - Long history → compressor должен сработать (если 100+ messages)
   - Anonymization on/off
   - Interrupt mid-stream
7. Проверить auto-update — поставить v1.3.0-test rc1, потом релизнуть rc2, увидеть уведомление в работающем приложении

**Артефакт:** `.planning/SMOKE-v1.3.0.md` с галочками и скриншотами.

---

### P4.2 — Quality gate (30 мин)

`/awd-quality-gate` skill:
- pytest backend — все зелёные
- vitest frontend — все зелёные
- pnpm build — clean
- playwright — 5/5 specs зелёные (или хотя бы 2 active + 3 documented skip с причинами)

**Если что-то падает:** stop, разобрать, исправить, повторить.

---

### P4.3 — Build v1.3.0 final (1h)

1. `cd frontend && pnpm build` — Next.js standalone
2. `cd backend && pyinstaller build.spec` — backend.exe
3. `desktop/scripts/build-bundle.js` — копирует артефакты в `desktop/resources/`
4. `cd desktop && electron-builder --win --x64` — signed installer
5. Smoke: установить на чистый Win → запустить → first sentence response

**Артефакт:** `1C-Analyst-v1.3.0/analyst-setup-v1.3.0.exe` (~110 MB, signed).

---

### P4.4 — Release notes + GitHub Release (1h)

1. `1C-Analyst-v1.3.0/НАЧНИ ЗДЕСЬ.txt` — для аналитика
2. `1C-Analyst-v1.3.0/RELEASE-NOTES.md` — для разработчиков
3. `CHANGELOG.md` — финализировать `## [1.3.0] — 2026-XX-XX` секцию (раньше была Unreleased)
4. `git tag v1.3.0 -m "Commerce Readiness — Cloud.ru pivot + P0 fixes"`
5. `git push --tags`
6. GitHub Release: installer как asset, release notes как body
7. Обновить README ссылку на actual v1.3.0

**Артефакт:** Public GitHub Release v1.3.0 с installer'ом.

---

### P4.5 — STATE.md → milestone M7 closed (30 мин)

1. Обновить `.planning/STATE.md`:
   ```yaml
   milestone: M7
   milestone_name: "Commerce Readiness"
   status: complete
   ```
2. Открыть M8 milestone в `.planning/ROADMAP.md` с следующими целями (опционально):
   - 152-ФЗ регистрация в реестре (под первого корп-клиента)
   - Presidio PII Shield (если зарубежные LLM нужны)
   - Langfuse observability (при 5+ клиентах)

---

## Phase 4 итог

| Тикет | Часов |
|---|---:|
| P4.1 Smoke VM | 2 |
| P4.2 Quality gate | 0.5 |
| P4.3 Build | 1 |
| P4.4 Release | 1 |
| P4.5 STATE.md | 0.5 |
| **Total** | **5** |

---

## Общий итог

| Phase | Часов | Кратко |
|---|---:|---|
| Phase 1 | 26 | Wave 1/2 хвост: Sprint 3 wired, loop.py decompose, code signing, auto-update |
| Phase 2 | 15 | P0 из IDEAS: backend-only API key, ResultSizeGate, SQL AST validator |
| Phase 3 | 8 | Cloud.ru Qwen3 pivot — 152-ФЗ риск через default |
| Phase 4 | 5 | Smoke, quality gate, build, release v1.3.0 |
| **Total** | **54** | **~9 рабочих дней** до коммерческой v1.3.0 |

---

## Параллелизация

Не всё нужно делать sequentially. Что можно параллелить:

**Стартует немедленно (день 1):**
- P1.1 Sprint 3 wire-up (sequential ✓)
- **Async:** оформление EV Code Signing certificate (1-3 дня админ, не блокирует код)

**После P1.1 (день 2-3):**
- P1.2 Decompose loop.py (sequential, изменяет тот же файл что P1.1 трогает)

**После P1.2 (день 4):**
- P2.1 + P2.2 + P2.3 (можно параллельно если делать с разных файлов: P2.1 — chat.py/storage, P2.2 — orchestrator, P2.3 — safety.py)

**День 5-6:**
- P3.1 + P3.2 + P3.3 + P3.4

**День 7 (после получения сертификата):**
- P1.3 Code signing integration
- P1.4 Auto-update

**День 8-9:**
- Phase 4 (Smoke + Build + Release)

---

## Decision log

Зафиксированные решения 2026-05-22 (если перепрочитать через месяц — понять почему так):

| # | Решение | Альтернатива (rejected) | Причина |
|---|---|---|---|
| 1 | Cloud.ru Qwen3 default LLM | Остаться на MiMo | Free + РФ + лучше BSL + 152-ФЗ снят |
| 2 | НЕ делать Presidio в v1.3.0 | Сразу с PII shield | Если LLM в РФ — Presidio опциональный, экономим 15h |
| 3 | НЕ регистрироваться в реестре операторов ПД сейчас | Сразу регистрация | Формальность под первого корп-клиента, экономим время |
| 4 | НЕ делать Langfuse в v1.3.0 | Сразу observability | Нужно при 5+ клиентах, не сейчас |
| 5 | НЕ делать Cells + Reactive Graph | Революционный UX | Invasive 3 недели без гарантии adoption |
| 6 | НЕ делать DeepEval framework | Eval CI с порога | Нет стабильных prompts → гадание |
| 7 | НЕ делать Telegram bot в v1.3.0 | Secondary UI канал | Distraction. Web-only фокус |
| 8 | Plan→Execute как OPT-IN (toggle) | Default mode | Default = friction для опытных. Toggle в Settings |
| 9 | Read-only MCP (feenlace) — toggle в Settings | Замена 1C MCP Toolkit | Существующие подключения не ломаем |
| 10 | Linear chat сохраняем | Cells default | Простота > амбиции на первой версии |
| 11 | Хирургическая декомпозиция loop.py | Архитектурный rewrite | 10h vs 30h, риск регрессий ниже |
| 12 | OV cert (если EV дорогой) | EV сразу | Pilot достаточно OV, upgrade на EV через 3 месяца |

---

## Что делаем СЕЙЧАС

**Стартую с P1.1 Sprint 3 Hermes wire-up.**

После P1.1 — пользователь решает: продолжать sequentially или подключиться (e.g. начать оформление code-signing cert параллельно).

---

## Связь с прошлыми артефактами

- Расширение `.planning/CHECKLIST-COMMERCE-2026-05-22.md` (43 тикета) → этот план — **операционная** карта на 4 фазы. Старый чек-лист остаётся как справочник, но executable — этот.
- `.planning/STATE.md` будет обновлён с M7 Wave 1/2/3/4 → M7 Phase 1/2/3/4 (соответствует новой структуре).
- `docs/идеи-для-развития/IDEAS-ADDENDUM-2026-05-21.md` §15 Open Questions — все 7 закрыты (см. Decision log выше).
