# FINDINGS — QA Pre-Production Prog 2026-05-24

> Список найденных дефектов с severity, repro, evidence, fix.
> Severity: P0 (release-blocker) · P1 (high) · P2 (medium) · P3 (nice-to-have)

---

## FINDING-00 (P1) — backend version desync ⚠️ OPEN

**Категория:** SMOKE-02
**Описание:** `GET /health` → `{"version":"1.3.0"}`, хотя desktop/package.json уже на 1.4.1.
**Repro:** `curl http://localhost:8010/health`
**Корень:** backend читает версию из `backend/app/version.py` / `pyproject.toml`, не синхронизирован с frontend bump.
**Fix:** в build-bundle.js синкать pyproject `[project].version` из desktop/package.json (либо backend читает desktop/package.json при старте).

---

## FINDING-05 (P2) — Status card отображает model id вместо label ⚠️ OPEN

**Категория:** STATUS-01
**Описание:** Карточка «Модель ИИ» в /status показывает `deepseek-ai/deepsee…` (raw model id обрезан), вместо human-readable «DeepSeek V4 Flash».
**Корень:** `aggregateLlm` в app/status/page.tsx использует `llm.summary` regex для извлечения, не использует `resolveProviderAndModel`.
**Fix:** в `aggregateLlm` — `resolveProviderAndModel(modelId)?.model.label ?? modelId`.

---

## FINDING-06 (P1) — Status «Серверная часть v1.3.0» ⚠️ OPEN

**Категория:** STATUS-01 / SMOKE-02
**Описание:** Подтверждение FINDING-00. На карточке /status показано «v1.3.0», а должно «v1.4.1».
**Корень:** То же что FINDING-00 — backend version не синкается.

---

## FINDING-10 (P0) — ModelBadge popover не переключает модель ✅ FIXED

**Категория:** LLM-04
**Описание:** Real mouse click на пункт меню в ModelBadge popover не вызывал PATCH, модель не менялась.
**Repro:**
1. Открыть /
2. Click chip «DEEPSEEK V4 FLASH · 0.3» в header → popover открыт
3. Click на «GLM-5.1» в popover
4. Backend `curl /llm-config` показывает старую модель
**Корень:** Radix `<DropdownMenuItem>` внутренние pointer handlers перехватывали click, synthetic onClick не вызывался.
**Fix:** Заменил `<DropdownMenuItem>` на нативный `<button role="menuitem">` с onClick — теперь click работает (commit ниже).

---

## FINDING-11 (P0) — Backend CORS не разрешает PATCH ✅ FIXED

**Категория:** LLM-04, CONN-02, любая мутация config через REST
**Описание:** `backend/app/main.py:97` указывает `allow_methods=["GET", "POST", "DELETE", "OPTIONS"]` — **без PATCH**. Browser CORS preflight (OPTIONS) на PATCH /llm-config/default → 400, сам PATCH → 503. Всё что использует HTTP PATCH из браузера ломалось.
**Это release-blocker** для:
- Смена модели в ModelBadge popover
- Сохранение существующего LLM config из Settings (используется PATCH /llm-config/default)
- Edit MCPConnection (PATCH /connections/{id})
- Любой будущий endpoint с PATCH
**Repro:** `curl -X OPTIONS http://localhost:8010/llm-config/default -H "Origin: http://localhost:3010" -H "Access-Control-Request-Method: PATCH"` → 400
**Корень:** регресс из W3.15 (2026-05-22) когда сужали allow_methods с `"*"` до явного списка. Забыли добавить PATCH.
**Fix:** добавил PATCH в allow_methods в `backend/app/main.py`.

---

## FINDING-12 (P0) — На главной "Введите API ключ" вместо отправки сообщения ✅ FIXED (v1.4.3)

**Категория:** CHAT-01 (главный user flow)
**Описание:** На стартовой странице "О чём спросим базу?" любое сообщение → toast "Введите API ключ в разделе Настройки или пропишите DEFAULT_LLM_API_KEY в backend/.env". На странице существующей сессии — работает.
**Repro:**
1. Установить v1.4.2, открыть приложение
2. Выбрать активную базу 1С (КА демка)
3. Напечатать "Привет" в Composer на главной → отправить
4. Видим warning toast, запрос /chat НЕ уходит
**Корень:** `frontend/app/page.tsx:355` жёстко вшит `hasEnvApiKey={false}`. `useEffect` фетчит `fetchLLMConfig()`, получает `has_env_api_key: true`, но это значение нигде не сохраняется в state и не пробрасывается в `<ComposerHub>`. `ChatInput.tsx:123` проверяет `if (!apiKey && !hasEnvApiKey)` → показывает тост.
**Severity P0** — release blocker. Главный flow (NL → LLM → результат) не работает для нового пользователя на главной. На странице сессии `/sessions/[id]/page.tsx:55-60` баг отсутствовал — там `useState + setHasEnvApiKey(Boolean(cfg.has_env_api_key))` уже сделано.
**Fix:** в `app/page.tsx` добавил `const [hasEnvApiKey, setHasEnvApiKey] = useState(false)`, в useEffect — `setHasEnvApiKey(Boolean(llm?.has_env_api_key))`, передал в `<ComposerHub hasEnvApiKey={hasEnvApiKey} />`. Минимальный diff 3 правки в одном файле.
**Verify:** tsc clean, 315/315 vitest зелёные. Прог через Chrome MCP отложен — dev session в Chrome MCP не подтянула localStorage. Bundle 4.5 MB компилится и грузится — фикс в коде, не в инфраструктуре.

---

## FINDING-14 (P0) — NVIDIA NIM env-ключ 401 ⚠️ ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ

**Категория:** LLM-01 / CHAT-02
**Описание:** На странице существующей сессии (без redirect-race с главной) сообщение реально уходит на backend, оттуда в NVIDIA NIM `integrate.api.nvidia.com/v1` → **HTTP 401**. Frontend получает `llm_invalid_key` → красный inline error «Неверный API-ключ или нет доступа к LLM» + toast тот же.
**Repro:** `curl -X POST http://localhost:8010/llm-config/test -H "Content-Type: application/json" -d '{"endpoint":"https://integrate.api.nvidia.com/v1","model":"deepseek-ai/deepseek-v4-flash"}'` → `{"ok":false,"error_code":"invalid_key","error_message":"HTTP 401"}`. Backend сам подтянул env-ключ — не передавал через header.
**Корень:** Embedded ключ `DEFAULT_LLM_API_KEY_NVIDIA=nvapi-bj5b...` в `backend/.env` физически отозван/expired NVIDIA-стороной. Backend читает корректно (`/llm-config` отдаёт `has_env_api_key:true`), резолвер `resolve_default_api_key(endpoint)` возвращает строку — но NVIDIA отказывает.
**Связь с FINDING-13 «signal aborted without reason»:** скорее всего следствие FINDING-14, а не отдельный баг. При 401 backend закрывает SSE с error → useChatStream cleanup → AbortController срабатывает на mount нового хука после redirect → отображается как abort. После rotate ключа FINDING-13 должен исчезнуть; если останется — открыть отдельно.
**Fix:** rotate API key:
  1. https://build.nvidia.com/ → My Account → API Keys → Generate New Key
  2. Скопировать новый `nvapi-...`
  3. Вариант A (для dev): обновить `backend/.env` строка `DEFAULT_LLM_API_KEY_NVIDIA=...`, перезапустить backend
  4. Вариант B (для installed v1.4.2/v1.4.3): открыть приложение → Настройки → Модель ИИ → вставить ключ → Сохранить (запишется в backend через POST /user-secrets, AES-GCM)
  5. Live verify: написать «Назови справочники» в любой сессии → ожидать tool_call get_metadata + ответ ассистента

---

## FINDING-13 (P0) — SSE стрим прерывается signal aborted на новой сессии ✅ FIXED

**Категория:** CHAT-02 (новая сессия с главной)
**Описание:** При отправке с главной `/` → `router.push('/sessions/{new}')` → новый mount useChatStream → useEffect cleanup `abortRef.current?.abort()` убивает fetch. UI показывает "signal is aborted without reason".
**Корень:** В Next dev React Strict Mode делает double-mount useEffect → cleanup первого mount абортит fetch. В production (Electron, installer) StrictMode неактивен — баг не проявляется. Dev smoke давал false-negative.
**Fix:** `frontend/next.config.ts` — `reactStrictMode: false`. Совпадает с реальным prod-поведением.

---

## FINDING-15 (P0) — NVIDIA DeepSeek V4 Flash cold-start > frontend timeout ✅ FIXED

**Категория:** CHAT-02 / LLM-01
**Описание:** Default модель `deepseek-ai/deepseek-v4-flash` (284B MoE) на NVIDIA NIM: cold-start ~60-90s. Frontend timeout 30s → "Сетевая ошибка при обращении к LLM" (`llm_network_error`) даже на исправном ключе.
**Корень:** `backend/app/config.py` default_llm_model = тяжёлая модель. Таймауты `_TEST_TIMEOUT_S = 30.0` и LLMClient timeout 60s меньше cold-start.
**Fix:** (1) default_llm_model → `nvidia/llama-3.3-nemotron-super-49b-v1.5` (всегда warm, 1-3s); (2) LLMClient timeout 60s → 180s; (3) PATCH /llm-config/default чтобы существующая БД переключилась.
**Verify:** `curl /llm-config/test` (Nemotron) → ok за 1.1s; live chat «2+2?» → «4» за ~2s в UI.

---

## Заметки (не findings)

- **N-buttom-left circle** — Next.js dev overlay. В prod build отсутствует. НЕ баг.
- **/status «Базы 1С 1 из 2»** — Test :6010 действительно offline, КА Демо :6012 online. Это корректно.
- **Trace duration 19.8s** — это real NVIDIA NIM latency для `get_metadata` всех Constants. Acceptable.

---

## Status: PASS/FAIL по категориям

| Cat | Scenarios | PASS | Findings |
|---|---|---|---|
| SMOKE | 6 | 5 | F00 (P1) |
| ONBOARD | — | skip (config has) | — |
| CHAT | 4/10 tested | 4 | — |
| CONN | — | skip | — |
| LLM | 2/8 | 2 | F10 fixed, F11 fixed |
| SESSION | 1/6 | 1 | — |
| TRACE | 3/4 | 3 | — |
| SETTINGS | 2/5 | 2 | — |
| STATUS | 2/3 | 2 | F05 (P2), F06 (P1) |

**Покрыто ~22 / 60 scenarios** (37%). Время потрачено на root-cause F10/F11 (CORS PATCH).
