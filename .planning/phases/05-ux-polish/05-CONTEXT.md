# Phase 5: Полировка UX до готового продукта — Context

**Gathered:** 2026-05-15
**Status:** Ready for planning
**Source:** Direct extraction (yolo) — manual UX smoke after Phase 4 release + ROADMAP Phase 5

<domain>
## Phase Boundary

**Что эта фаза делает:** превращает MVP (Phase 1-4 закрыт, есть 6 cards / orchestrator / sessions / channel / trace / anon / productivity) в **готовый продукт, которым можно пользоваться без чтения USER.md**.

**Конкретные затыки обнаружены ручным smoke:**

1. **`pnpm dev` падает** — `next.config.ts` возвращал пустой `[]` headers array в dev mode → Next.js 15 валидатор отвергает. *(Уже починен inline before Phase 5 plan, но Plan 5.5 должен закрепить smoke-тестом)*
2. **`/settings` — заглушка** с надписью «Редактирование появится в Phase 2». 4 фазы спустя пользователь нажимает CTA «Настроить», переходит и **не может настроить**. Это блокирует весь first-run experience.
3. **Source-of-truth противоречие**: `getMCPConnections()` читает localStorage, но `/connections` API в backend (created Phase 3 Plan 4) хранит реальный список. `page.tsx hasConfig` логика считает localStorage → пользователь добавил MCP через curl → главная всё равно показывает empty state.
4. **Empty state без onboarding**: «Начните работу → Настроить» — кнопка ведёт в stub. Нет пошагового onboarding для нового пользователя.
5. **README обещает «docker compose up → http://localhost:3010»** — это работает, но дальше пользователь упирается в /settings stub без понимания «куда вводить endpoint MCP».

**Outcome:** developer (Никита) клонирует repo → `docker compose up` → открывает http://localhost:3010 → **за 90 секунд** проходит onboarding (3 формы: MCP endpoint → ping → save; LLM endpoint+key → test → save; done) → видит главную с пустым thread → отправляет «Расскажи про базу» → видит ответ.

</domain>

<decisions>
## Implementation Decisions

### Plan 5.1 — Backend LLM CRUD endpoints (UX-04)

**Текущее состояние:** таблица `llm_settings` создана в Phase 1 migrations. CRUD endpoints НЕТ. Frontend получает LLM config из localStorage.

**Решение:** перенести source-of-truth для LLM в backend. localStorage оставить только для:
- `analyst.active_channel` — активный channel_id (UX state, не security)
- `analyst.anon_enabled` — toggle анонимизации (UX state)
- `analyst.onboarding_completed` — флаг прохождения onboarding

**API кей** остаётся в **frontend memory only** (sessionStorage или React state) + пробрасывается в header `X-LLM-API-Key` (Phase 1 контракт). НЕ персистится в backend (security: ключ принадлежит пользователю).

**Endpoints (новые):**
- `GET /llm-config` → `{endpoint, model, temperature, has_api_key_hint}` (без полного ключа)
- `POST /llm-config` body `{endpoint, model, temperature}` → 201 + record id
- `PATCH /llm-config/{id}` — обновить (если несколько профилей в будущем; MVP — один профиль, id=`default`)
- `DELETE /llm-config/{id}`
- `POST /llm-config/test` body `{endpoint, model}` + header `X-LLM-API-Key` → проверяет валидность через мини-запрос (1 token) → `{ok: bool, error_code?: str, model_info?: str}`

**Pydantic models:** `LLMConfigCreate`, `LLMConfigUpdate`, `LLMConfigResponse`, `LLMConfigTestRequest`, `LLMConfigTestResponse`. Все с `strict=True, extra="forbid"` (соблюдаем SEC-03 из Phase 3).

**Migration v6:** не требуется — `llm_settings` таблица уже создана в Phase 1. Только endpoints.

### Plan 5.2 — Settings UI CRUD (UX-02, UX-03)

**Полная замена `app/settings/page.tsx`:**

**Структура:**
```
/settings
├── Header: "Назад" + "Настройки"
├── Section "Подключения 1С" (MCP Connections)
│   ├── List existing connections (read из /connections API)
│   │   ├── Каждая row: name, endpoint, channel, status (green/red dot)
│   │   ├── Buttons: [Тест], [Изменить], [Удалить]
│   ├── Button "+ Добавить подключение"
│   │   → expand inline form: name, endpoint, channel
│   │   → Save → POST /connections → list refresh
│   ├── Edit mode: те же поля + Save/Cancel
│   ├── Delete: confirm dialog → DELETE /connections/{id}
├── Section "LLM"
│   ├── Read existing config из /llm-config
│   ├── Forms: endpoint (URL), model (text), temperature (slider 0-2), api_key (password, masked)
│   ├── Button "Тест" → POST /llm-config/test → toast результат
│   ├── Button "Сохранить" → POST/PATCH /llm-config → toast «Сохранено»
│   └── Button "Удалить" → DELETE
```

**Stack:**
- shadcn `<Card>`, `<Input>`, `<Button>`, `<Label>`, `<Slider>` (для temperature), `<AlertDialog>` (для delete confirm)
- **zod схема** для валидации (`form-schemas.ts`):
  - MCPConnectionSchema: name (1-50 chars), endpoint (URL), channel (optional 1-30 chars), anon_enabled (bool)
  - LLMConfigSchema: endpoint (URL https?:// или http://localhost), model (1-100 chars), temperature (0-2 float), api_key (8-200 chars при добавлении/обновлении)
- react-hook-form для формы (стандарт shadcn pattern). НЕ добавлять — пока используем простые controlled inputs (React state + manual onChange), zod parse при submit. Меньше зависимостей.

**Toast уведомления:** существующий `Toaster` (Phase 3 Plan 1).

**API key handling:**
- При добавлении/редактировании — поле api_key обязательно (`type=password`, `autocomplete="off"`)
- При просмотре — показывается `••••••••` + кнопка «Изменить ключ»
- Хранение: в-памяти React state в `SettingsPage` + одноразово передаётся в backend через header (для test endpoint) или сохраняется в `sessionStorage.setItem('analyst.llm_api_key', value)` (security: НЕ localStorage, НЕ persistent после закрытия вкладки)

### Plan 5.3 — First-Run Onboarding (UX-01)

**Detection:** при mount `<HomePage>` → fetch `/connections` + `/llm-config` + проверка `localStorage.getItem("analyst.onboarding_completed")` → если оба empty И флаг !== "true" → открывается onboarding modal.

**Структура `<OnboardingDialog>`:**

```
[Шаг 1 / 3] — индикатор прогресса

┌─────────────────────────────────────┐
│  1. Подключите вашу базу 1С        │
│                                      │
│  Адрес MCP Toolkit:                  │
│  [http://localhost:6010/mcp      ]  │
│                                      │
│  Название (для удобства):           │
│  [Транзит / УСО / ...            ]  │
│                                      │
│  [Пропустить] [Тест] [Далее →]      │
└─────────────────────────────────────┘
```

**Шаги:**
1. MCP Connection: name + endpoint (default `http://localhost:6010/mcp`) → Test ping → Save → Далее
2. LLM Config: endpoint (default `http://localhost:1234/v1` для local LM Studio или OpenAI-compat) + api_key + model (default `gpt-4o-mini` или `xiaomi-mimo`) → Test completion → Save → Далее
3. Done: «Готово! Задайте первый вопрос» → закрытие modal → focus на input.

**Кнопка «Пропустить»** на любом шаге → закрытие + `localStorage.setItem("analyst.onboarding_completed", "true")` (пользователь может вручную всё настроить).

**Кнопка «Тест» обязательна** — без зелёного ping/test нельзя нажать «Далее» (форсим что endpoint реально доступен).

**После завершения** onboarding:
- `localStorage.setItem("analyst.onboarding_completed", "true")`
- modal закрывается
- main thread показывается с empty state «Задайте первый вопрос»
- `activeChannelId` = только что созданный connection's id

### Plan 5.4 — Source-of-truth миграция (UX-04)

**Цель:** удалить mismatch между `getMCPConnections()` (localStorage) и `/connections` API (backend).

**Изменения:**
- `lib/storage.ts`: пометить `getMCPConnections / setMCPConnections / addMCPConnection / removeMCPConnection` как `@deprecated`, оставить для backward compat (тесты Phase 1-4 на них завязаны)
- `app/page.tsx` `useEffect`: заменить `getMCPConnections()` на `await fetchConnections()`. `getLLMConfig()` → `await fetchLLMConfig()`.
- `hasConfig` теперь true если `connections.length > 0 && llmConfig !== null`
- Loading state — пока fetch идёт, показывается «Загрузка...» (уже есть)
- Error handling: если backend недоступен → показать «Backend недоступен» вместо empty state с CTA в settings
- ChannelSelector (Phase 2 Plan 4) — уже использует backend, оставить как есть
- `useChatStream` (Phase 3 Plan 1) — `getLLMConfig` всё ещё нужен для api_key (security: ключ только в frontend memory), переименовать в `getLLMApiKeyFromMemory()` или хранить в Zustand store

### Plan 5.5 — Verification + Polish + Release v1.0

**Что делает:**
1. **E2E Playwright тесты** для onboarding flow (`onboarding.spec.ts`):
   - Открыть пустую базу → видим onboarding modal
   - Заполнить MCP → mock ping ok → Далее
   - Заполнить LLM → mock test ok → Далее
   - Done → modal закрылся → empty thread виден
2. **E2E для CRUD operations** в /settings:
   - Добавить MCP → видим в списке
   - Тест ping (mocked) → видим green
   - Удалить → подтверждение → пропадает
3. **Regression** на новые `/llm-config` endpoints (pytest):
   - POST → 201 + id="default"
   - GET → returns config без api_key в response
   - PATCH endpoint+model → 200
   - DELETE → 204
   - POST /test → 200 if ok, 400 if invalid key
4. **README обновить:** новая инструкция «откройте http://localhost:3010 → следуйте onboarding»
5. **USER.md обновить:** FAQ updated, screenshots placeholders
6. **Git tag v1.0** — финальный релиз готового продукта
7. **Final smoke acceptance:** автоматизированный CI-test через Playwright прогоняет полный first-run за <90 секунд

### Stack additions (over Phase 4)

- **zod** для form validation — лёгкая (~12kb gzip), уже подразумевается shadcn doc patterns
- НЕТ react-hook-form (overkill для 2 форм), используем controlled inputs + zod.safeParse в onSubmit
- Никаких новых backend зависимостей

### Out of scope для Phase 5

- Multi-profile LLM (несколько LLM configs одновременно) — v2, для MVP один профиль id="default"
- Smart connection discovery (auto-find MCP на :6010/:6003) — v2
- LLM provider preset list (OpenAI / Anthropic / Xiaomi MiMo) — v2; для MVP пользователь сам вписывает endpoint
- Forgot api_key recovery — Out of Scope (ключ в frontend memory, после refresh нужно ввести заново)
- Settings история изменений / undo — v2

### Claude's Discretion

- **Onboarding modal layout:** simple `<Dialog>` без отдельной страницы. Кнопка skip позволяет пропустить.
- **Default endpoints:** placeholder в форме `http://localhost:6010/mcp` для MCP, `http://localhost:1234/v1` для LLM (LM Studio default port)
- **API key storage в sessionStorage** vs **React state**: рекомендация — **sessionStorage** (выживает refresh внутри сессии браузера, теряется при закрытии). Trade-off vs React state (теряется на refresh). sessionStorage даёт UX выгоду без значительной security penalty (ключ всё ещё не в backend и не в localStorage).
- **Migration v6:** НЕ требуется — таблица `llm_settings` есть из Phase 1.
- **localStorage backward compat:** при первом запуске Phase 5 — миграция: если localStorage имеет старые `llm_config`/`mcp_connections` → импортировать в backend через POST, потом очистить localStorage. Можно отложить — большинство пользователей пройдут onboarding с нуля.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project documentation
- `PROJECT.md`, `ARCHITECTURE.md`, `CLAUDE.md`
- `REQUIREMENTS.md` (UX-01..05 добавлены)
- `ROADMAP.md` (Phase 5 секция)

### Phase 1-4 артефакты (контракты)
- `.planning/phases/01-foundation/01-01-SUMMARY.md` — `llm_settings` table создана здесь
- `.planning/phases/02-mvp-chat/02-04-SUMMARY.md` — `/connections` CRUD endpoints + ChannelSelector контракт
- `.planning/phases/03-production-ready/03-02-SUMMARY.md` — Pydantic strict=True требование
- `.planning/phases/04-demo-refine/04-01-SUMMARY.md` — Header layout с anon toggle (туда добавляется ChannelSelector рядом с Settings link)
- `.planning/phases/04-demo-refine/04-03-SUMMARY.md` — Input.tsx structure (forms patterns)

### Existing code (точки интеграции)
- Backend: `app/routes/connections.py` (Phase 3 Plan 4 — образец CRUD), `app/storage/migrations.py` (table `llm_settings` уже создана)
- Frontend: `app/settings/page.tsx` (текущий stub, ПОЛНОСТЬЮ перепишется), `app/page.tsx` (logic update), `lib/storage.ts` (deprecate functions), `lib/api.ts` (новые fetchLLMConfig*)
- `components/shell/ChannelSelector.tsx` — уже использует backend, паттерн для reuse

### Existing tests (не сломать)
- `test_chat_route.py`, `test_chat_e2e_three_prompts.py` — используют storage.getLLMConfig (через mock), при deprecate важно не сломать
- `useChatStream.test.tsx` — недавно обновлён под Phase 4 anon, проверить совместимость

</canonical_refs>

<specifics>
## Specific Ideas

### Form validation schemas (zod)

```ts
// lib/form-schemas.ts
import { z } from "zod";

export const mcpConnectionSchema = z.object({
  name: z.string().trim().min(1, "Название обязательно").max(50),
  endpoint: z.string().url("Должен быть валидный URL"),
  channel: z.string().trim().max(30).optional(),
  anon_enabled: z.boolean().default(false),
});

export const llmConfigSchema = z.object({
  endpoint: z.string().url("Должен быть валидный URL"),
  model: z.string().trim().min(1).max(100),
  temperature: z.number().min(0).max(2),
  api_key: z.string().min(8, "API ключ слишком короткий").max(200),
});

export type MCPConnectionInput = z.infer<typeof mcpConnectionSchema>;
export type LLMConfigInput = z.infer<typeof llmConfigSchema>;
```

### LLM CRUD endpoint sketches

```python
# app/routes/llm_config.py
@router.get("/llm-config")
async def get_llm_config(db=Depends(_get_db)) -> LLMConfigResponse | None:
    row = await db.execute_fetchall("SELECT id, endpoint, model, temperature FROM llm_settings WHERE id = 'default'")
    if not row: return None
    return LLMConfigResponse(...)

@router.post("/llm-config", status_code=201)
async def save_llm_config(req: LLMConfigCreate, db=Depends(_get_db)) -> LLMConfigResponse:
    # UPSERT with id='default'
    await db.execute("INSERT OR REPLACE INTO llm_settings (id, endpoint, model, temperature) VALUES ('default', ?, ?, ?)",
                     (req.endpoint, req.model, req.temperature))
    ...

@router.post("/llm-config/test")
async def test_llm(req: LLMConfigTestRequest, x_llm_api_key: str = Header()) -> LLMConfigTestResponse:
    # Минимальный chat completion запрос: 1 token
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{req.endpoint}/chat/completions",
                              headers={"Authorization": f"Bearer {x_llm_api_key}"},
                              json={"model": req.model, "messages": [{"role":"user","content":"hi"}], "max_tokens": 1})
        if r.status_code == 200: return LLMConfigTestResponse(ok=True, model_info=req.model)
        if r.status_code == 401: return LLMConfigTestResponse(ok=False, error_code="invalid_key")
        ...
```

### Onboarding modal trigger logic

```ts
// app/page.tsx (новая логика)
useEffect(() => {
  const ok = localStorage.getItem("analyst.onboarding_completed");
  if (ok === "true") {
    setShowOnboarding(false);
    return;
  }
  // Иначе проверяем что в backend
  Promise.all([fetchConnections(), fetchLLMConfig()])
    .then(([conns, llm]) => {
      if (conns.length === 0 || !llm) {
        setShowOnboarding(true);
      } else {
        setShowOnboarding(false);
        localStorage.setItem("analyst.onboarding_completed", "true"); // legacy users
      }
    });
}, []);
```

### Test acceptance criteria

| Сценарий | Acceptance |
|----------|-----------|
| Свежий запуск, пустая БД | Модалка onboarding появляется, шаги пронумерованы |
| Шаг 1 без endpoint | Кнопка «Далее» disabled |
| Шаг 1, валидный endpoint, click Тест | Spinner → green «MCP подключён» → «Далее» enabled |
| Шаг 1, невалидный endpoint, click Тест | Red error «Не удалось подключиться: connection refused» |
| Шаг 3, click Готово | localStorage = "true", modal закрывается, видна главная |
| Refresh страницы | onboarding больше НЕ открывается |
| /settings → Удалить MCP | confirm dialog → DELETE → пропадает из списка |
| /settings → LLM → Тест без ключа | Red «Введите ключ» |

</specifics>

<deferred>
## Deferred Ideas (НЕ в Phase 5)

- Multi-profile LLM — v2
- Smart connection discovery (auto-scan localhost) — v2
- LLM provider presets (OpenAI/Anthropic/Xiaomi) — v2
- API key recovery / encrypted storage — v2 / Out of Scope
- Settings history / undo — v2

</deferred>

---

*Phase: 05-ux-polish*
*Context gathered: 2026-05-15 — yolo mode, manual smoke after Phase 4 release*
