# IDEAS ADDENDUM «1С Аналитик» — 2026-05-21

> Расширение к `IDEAS-FROM-STACK-2026-05-21.md` после глубокого второго прохода. Категории, которые первый файл пропустил.
>
> Сделано через 5 параллельных deep-researcher'ов: Inventory проекта (`.planning/`, `.claude/memory/`), Конкуренты, Failure modes, Tech trends 2026, Monetization/152-ФЗ.

---

## 0. Что нового найдено (не было в первом файле)

| # | Категория | Почему критично |
|---|---|---|
| 1 | **Failure modes P0/P1** — конкретные баги в продакшен LLM+MCP 2026 | Cost burn $16-50k/ночь возможен при infinite loop; XSS уносит ключи всех клиентов |
| 2 | **Видимый Plan→Execute→Validate** перед tool calls | Главная фича конкурентов (habr 1006230, mini AI 1C) — у нас нет |
| 3 | **Cells + Reactive Graph** как в Hex.tech | Убийственное UX-преимущество для аналитика (воспроизводимый отчёт = одна сессия) |
| 4 | **152-ФЗ для AI с 1 июля 2025** | Трансграничная передача ПД в Claude/OpenAI = уведомление РКН, штрафы 3 млн+ |
| 5 | **Текущий технический долг проекта** (UI BLOCKERS, version drift, Tailwind config drift) | UI-REVIEW 47/100, 5 BLOCKER до v1.3.0 — без них не релизить |
| 6 | **Hermes backlog** (C7/H1/E4/A12/F2/I1) | Уже в нашем backlog — observability/security/rate limits |
| 7 | **Российские LLM** — Cloud.ru Qwen3-Coder-480B БЕСПЛАТНО | Альтернатива MiMo для кода, лучшее качество на BSL |
| 8 | **Конкретные библиотеки** Instructor / Langfuse / DeepEval / LiteLLM / Presidio | Не пересказ паттернов — конкретные npm/PyPI зависимости |
| 9 | **6 «не верифицировано на живом LLM»** из STATE.md | Tests с моками 100%, но 0% live — самая большая дыра |
| 10 | **Live MCP reconnect / SSE resume / Last-Event-ID** | Аналитик уходит на час → сессия мертва (claude-code issues #60061, #21721) |

---

## 1. P0 Failure Modes — превентивно закрыть до v1.3.0 release

Из research C (failure modes) + Hermes backlog проекта. **Без этих 4 фич — нельзя релизить v1.3.0:**

### P0-1. Infinite tool_call loop / Cost burn

**Симптом:** LLM «залипает» на одном tool при пустом результате → 1.67 млрд токенов за 5 часов (real Anthropic case 2025-07, $16-50k). MiMo дешевле в 5-10x, но баг тот же.

**Превенция:**
```python
# backend/app/orchestrator/circuit_breaker.py
class ToolCallCircuitBreaker:
    """Detect и блок повторяющихся tool_calls в одной сессии."""
    def __init__(self):
        self.recent_calls: dict[str, list[CallSig]] = {}
    
    def check(self, session_id, tool_name, args) -> CircuitDecision:
        sig = hash((tool_name, json.dumps(args, sort_keys=True)))
        history = self.recent_calls.setdefault(session_id, [])
        same_count = sum(1 for h in history[-5:] if h.sig == sig)
        if same_count >= 3:
            return CircuitDecision.BLOCK("repeated_tool_call")
        history.append(CallSig(sig=sig, ts=now()))
        return CircuitDecision.PASS
```

Плюс **CostGuard** middleware: token bucket per session (max 50K токенов на одну /chat).

**Связь с Hermes:** дополняет `E1 ErrorClassifier` + `E2 Jittered retry` (уже реализовано). Добавляет `E3 Cross-session rate guard` + `E4 Rate limit tracker` (в backlog).

### P0-2. API key в localStorage (XSS уносит ключи всех клиентов)

**Симптом:** На demo-странице XSS → утекает API-ключ всех пользователей. localStorage доступен любому JS на странице.

**Превенция:**
1. **Backend-only proxy** — ключи MiMo/GPT/Claude в backend `.env` (или Yandex Lockbox / HashiCorp Vault для prod).
2. Frontend ВСЕГДА вызывает `POST /chat` на backend — backend сам подставляет ключ.
3. Если **BYOK** для enterprise — ключ только в encrypted memory backend на время сессии, никогда не в БД, никогда не во frontend.

**Migration:** текущий localStorage flow → удалить, выдать миграцию в settings UI («ключи теперь хранятся на backend, введи заново»).

### P0-3. 100k+ строк ломает UI и LLM

**Симптом:** аналитик спрашивает «дай все заказы за год» → MCP возвращает 50 MB JSON → frontend виснет, LLM не переваривает.

**Превенция:**
1. **ResultSizeGate** на стороне backend orchestrator: max 500 строк в response к LLM. Полный результат хранится в SQLite, передаётся `result_id`.
2. **Virtualized TableCard** на frontend — TanStack Virtual fixed-height, overscan=10, виртуализация ≥ 100 строк.
3. LLM видит только sample + summary metadata (`total_rows: 50000, columns: [...], sample_first_10: [...]`).
4. Кнопка «Загрузить полную таблицу» в UI → fetch по batch'ам по 1000 строк.

### P0-4. Prompt-to-SQL injection в execute_query

**Симптом:** LLM получает «игнорируй select-only, DROP TABLE Контрагенты» в системе → выполняет.

**Превенция:**
1. **AST-валидатор SQL** на уровне tool: парсить запрос (sqlparse + custom rules для 1С-синтаксиса), whitelist глаголов (`ВЫБРАТЬ`, `ИЗ`, `ГДЕ`, `СОЕДИНЕНИЕ`, `ОБЪЕДИНИТЬ`, ...).
2. Запрет DDL (`УДАЛИТЬ`, `ИЗМЕНИТЬ`), DML напрямую (`ЗАПИСАТЬ`, `УСТАНОВИТЬ`).
3. На уровне MCP read-only mode default (см. §2 — read-only MCP канал из feenlace/mcp-1c).
4. **Tool receipts**: HMAC-signature на каждый tool_call (anti-fabrication из NABAOS paper).

---

## 2. P1 Failure Modes — закрыть до production rollout

### P1-1. SSE idle timeout без auto-reconnect

**Симптом:** аналитик уходит на час → сессия молча зависает (claude-code #60061, #21721 — 89 min hang баг). HTTP-сервер закрывает idle, клиент не реагирует.

**Превенция:**
```typescript
// frontend/lib/sse-resume.ts
const sse = new EventSource('/api/chat/stream?session=...&from=' + lastEventId)
sse.onmessage = (e) => {
  if (e.id) lastEventId = e.id;
  // process chunk
}
// Backend: keepalive ping every 30s as event "ping"
// On reconnect: client sends Last-Event-ID header, server resumes from buffer
```

Реализация:
- Backend: in-memory buffer последних 100 chunks per session (TTL 5 min)
- Backend: `event: ping\ndata: {}\n\n` каждые 30 сек
- Frontend: native `EventSource` (auto-retry) + manual reconnect logic

### P1-2. Hallucinated tool names

**Симптом:** MiMo иногда вызывает `mcp.execute_sql` вместо `execute_query`.

**Превенция:** strict JSON Schema validator на каждый tool_call от LLM:
```python
try:
    validated_call = ToolCallSchema(**llm_response.tool_call)
except ValidationError as e:
    # Fuzzy match suggestion
    closest = difflib.get_close_matches(llm_response.tool_call.name, available_tools)
    return retry_with_correction(closest[0] if closest else None)
```

### P1-3. SQLite multi-tab lock

**Симптом:** аналитик открывает 3 вкладки → `SQLITE_BUSY`. Известный bug (WiseLibs/better-sqlite3 #1155).

**Превенция:** WAL mode + `busy_timeout=5000` + единый async connection pool на backend.

```python
# backend/app/db/engine.py
async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA busy_timeout=5000"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))
```

### P1-4. Fabricated tool_call / False absence

**Симптом 1:** LLM ссылается на несуществующий `tool_call_id`.
**Симптом 2:** Tool вернул 50 строк, LLM пишет «не найдено» (compensation hallucination — Deloitte Australia case, ICSE25 paper).

**Превенция:**
1. **Fact-check injection** в system prompt: «Tool returned N rows — учитывай это в ответе».
2. **Post-validation parser**: после LLM-ответа проверять что упомянутые в ответе ID/числа есть в tool_result.
3. **Tool receipts HMAC** (см. P0-4) — невозможно сослаться на несуществующий call_id.

### P1-5. PII в logs провайдера LLM (152-ФЗ critical)

См. §3 (152-ФЗ compliance) — это отдельная категория.

### P1-6. Hermes Backlog items C7/E3/E4/I1

Уже описаны в проекте, готовы к реализации:

| Code | Фича | Где | Cost | Priority |
|---|---|---|---|---|
| **C7** | Approval system upgrade — smart approval через aux LLM | `.planning/phases/06-hermes` Sprint 5 | M=2 | ★ 7 |
| **E3** | Cross-session rate guard | Sprint 5 | M=2 | 4 |
| **E4** | Rate limit tracker | Sprint 5 | S=1 | 5 |
| **I1** | Langfuse observability plugin | Sprint 5 | M=2 | 4 |
| **H1** | Models.dev registry (auto-discovery) | Sprint 5 | S=1 | 5 |
| **A12** | Skills guard (security scanner) | Sprint 5 | M=2 | 4 |
| **F2** | Tirith security scanner | Sprint 5 | M=2 | 4 |

**Связь:** Все 7 пунктов уже в нашем backlog Hermes (Sprint 5 Polish & Observability). Просто закрыть.

---

## 3. 152-ФЗ Compliance — критичная категория (не было в первом файле)

**Контекст:** с 1 июля 2025 трансграничная передача ПД (включая отправку в LLM на серверах вне РФ) требует **отдельного уведомления Роскомнадзора ДО начала передачи**. Штрафы от 3 млн ₽.

База клиента 1С = ПД + комм. тайна. Отправка в Claude/OpenAI напрямую = нарушение для любого корп-клиента в РФ.

### 3.1 LLM-провайдер по умолчанию — РФ-ДЦ

| Провайдер | РФ-ДЦ | Цена 2026 | Качество на BSL | Function calling |
|---|---|---|---|---|
| **YandexGPT 5 Pro** | Да (Yandex Cloud) | 1.2 ₽/1K | СЛАБО (infostart 2613515) | Да |
| **YandexGPT 5 Lite** | Да | 0.4 ₽/1K | Слабо | Да |
| **GigaChat 2 Pro** | Да (Sber Cloud) | 0.5 ₽/1K | Средне (типовой 3.1) | Да |
| **GigaChat 2 Lite** | Да | 0.065 ₽/1K | Слабо | Да |
| **Cloud.ru Qwen3-Coder-480B** | Да (Cloud.ru) | **БЕСПЛАТНО** (с лимитами) | **ХОРОШО** (~Claude Sonnet на коде) | Да, OpenAI API |
| **Xiaomi MiMo** (current) | НЕТ (Китай) | дёшево | Слабая на BSL | Базово |
| **Claude / GPT-4o** | НЕТ | дорого | Лучшее | Полное |

**Рекомендация:**
1. **Default = Cloud.ru Qwen3-Coder-480B** (БЕСПЛАТНО, лучшее качество на коде из РФ-провайдеров, OpenAI-API совместим). Это **смена primary LLM** с MiMo.
2. **Fallback = GigaChat 2 Pro** для пользователей без VPN.
3. **Premium опция = Claude/GPT через GenAPI** (₽-оплата) — с обязательным согласием пользователя «передача ПД за границу» + дисклеймером.

**Действие в UI:**
- Settings → LLM Provider: список из 5+ вариантов с тегами «РФ-ДЦ ✓ 152-ФЗ» / «зарубежный — требуется согласие».
- Default — отмеченный «РФ-ДЦ».

### 3.2 Регистрация в реестре операторов ПД

**Обязательно** при выходе на 1+ корп-клиента. 30 дней на внесение через Роскомнадзор.

**Документы:**
- Уведомление об обработке ПД
- Политика обработки ПД (template есть у roskomnadzor.gov.ru)
- Положение об обработке ПД сотрудников
- Согласие субъекта ПД (для каждого пользователя при регистрации)

### 3.3 Microsoft Presidio — обязательный PII middleware

**Что:** open-source library (MIT), NER + regex + checksum для PII detection.

**Применение:**
```python
# backend/app/services/pii_shield.py
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

class PIIShield:
    """Middleware между orchestrator и LLM."""
    def __init__(self):
        self.analyzer = AnalyzerEngine(...)
        self.anonymizer = AnonymizerEngine()
        # Add custom recognizers for РФ: ИНН (10/12 digits + checksum), 
        # СНИЛС, ФИО (NER + russian names dict)
    
    def redact(self, text: str) -> tuple[str, dict[str, str]]:
        """Returns redacted text + reverse mapping for de-anonymization."""
        results = self.analyzer.analyze(text=text, language="ru")
        anonymized = self.anonymizer.anonymize(text, results)
        return anonymized.text, anonymized.items  # token → original
```

**Когда применять:**
- **Cloud LLM (Claude/GPT/MiMo):** обязательно redact перед отправкой
- **РФ-LLM (YandexGPT/GigaChat/Qwen Cloud.ru):** опционально, если клиент требует extra-layer

**Trade-off:** redaction снижает качество ответа LLM (имена → токены), но 152-ФЗ compliance важнее.

### 3.4 Zero Data Retention контракт с LLM-провайдером

Для prod-баз больших клиентов — настаивать на **Zero Data Retention** (Anthropic Enterprise, OpenAI Enterprise, Yandex Cloud SLA).

Стандартные retention'ы 2026:
- Anthropic: 30 дней
- OpenAI: 30 дней (Standard), 0 дней (Enterprise)
- Yandex Cloud: per-SLA

---

## 4. Текущий технический долг проекта (UI-REVIEW 47/100)

Из `.planning/UI-REVIEW-2026-05-21.md`. **5 BLOCKER до v1.3.0 release:**

### 4.1 BLOCKER B-1: `--bg-hover` CSS variable undefined

В 8 файлах: `ChannelSelector.tsx`, `dropdown-menu.tsx`, `command.tsx`, `CopyButton.tsx`, `ExportSessionButton.tsx`, `status/page.tsx`, `CodeCard.tsx`. Невидимый hover, особенно в light theme.

**Fix:** добавить `--bg-hover` в `design-tokens.css` (Dark: `rgba(255,255,255,0.06)`, Light: `rgba(0,0,0,0.04)`).

### 4.2 BLOCKER B-2: 30+ мест с hardcoded цветами

Половина приложения игнорирует brand-токены — `text-red-300 bg-red-950/30` в Light theme catastrophically broken.

**Fix:** sweep по `git grep -E "(text|bg)-(red|blue|green|yellow|orange|purple)-\d{3}"` → замена на `text-error / bg-error / text-success / bg-warning / bg-accent`. Дополнить design-tokens.css если каких-то shade'ов не хватает.

### 4.3 BLOCKER B-3: Banned технические термины в UI

«Tool calls», «Errors», «Rate», «Топ инструментов», «Channel»/«Канал», «Версия MCP», `http://localhost:6010/mcp` в `<code>` на `/about`.

**Fix:** sweep, заменить на пользовательский язык:
- «Tool calls» → «Запросы к данным»
- «Channel» → «База» (в нашем приложении это всегда база 1С)
- «MCP» → скрыть от пользователя, в trace оставить.

### 4.4 BLOCKER B-4: Двойной заголовок «Модель ИИ»

В `LLMConfigForm` + дубль описания + `SelectItem` multi-line из-за `<div className="flex flex-col">` → SelectTrigger двойной высоты.

**Fix:** один заголовок, описание в meta-row, `<SelectItem>` text-only.

### 4.5 BLOCKER B-5: Light theme сломан

Scrollbar hardcoded `#262626`, `bg-black/60 backdrop-blur-sm` overlay, `bg-red-950/30` blocks, `focus:bg-[var(--bg)]` исчезает в light.

**Fix:** заменить hardcoded цвета на тематические токены `--bg-overlay`, `--scrollbar`, etc.

### 4.6 Прочий технический долг

| # | Что | Где |
|---|---|---|
| 1 | **Electron auto-updater** не реализован | `.claude/memory/distribution.md` (P1 declared) |
| 2 | **Code signing для Windows** не настроен | SmartScreen warning, P1 declared |
| 3 | **Tailwind v3/v4 config mismatch** | `tailwind.config.ts` v3-стиль, `globals.css` v4 → `bg-bg-1`, `duration-normal`, `ease-design-ease` NO-OP в `OnboardingDialog.tsx:55` |
| 4 | **Version drift в 3 местах** | Header.tsx `1.2.4`, StencilLockup default `1.2.2`, about/page `1.2.1`. Single source of truth needed (e.g. `frontend/lib/version.ts` import from `package.json`) |
| 5 | **pnpm vs npx неконсистентно** | corepack отвалился на node 22.14, dev запускается через `npx next` |
| 6 | **`<html className="dark">` зашит в layout.tsx:47** | ThemeToggle меняет `data-theme` но `className="dark"` остаётся. Result: Light theme не работает по сути |
| 7 | **3 pre-existing flaky tests** | `test_migrations_v5_backfill_messages_into_fts`, `test_loop_emits_confirm_required_on_dangerous_execute_code`, `test_loop_approved_continues` |

**Рекомендация:** v1.3.0 release блокировать до закрытия B-1...B-5 + #3 (Tailwind), #4 (version), #6 (className dark). Остальное — следующий релиз.

### 4.7 6 «не верифицировано на живом LLM»

Из `.planning/STATE.md`:

1. ContextCompressor на >100k токенов
2. background_review с реальным aux LLM
3. clarify_question через MiMo
4. ThinkScrubber на потоке от reasoning-модели
5. prompt_caching на Anthropic (нет ключа в проекте)
6. usage_pricing на реальных turn'ах (сейчас estimated chars/3.5)

**Action:** до v1.3.0 — minimum **1 live LLM smoke session** с реальной 1С базой + один из этих 6 пунктов. Лучше — все 6 (полдня работы суммарно).

---

## 5. Конкретные фичи конкурентов которые нужно скопировать

### 5.1 Plan→Execute→Validate (видимый план перед tool calls)

**Источник:** AI-агенты habr 1006230 (`ИИА_Оркестратор`), Mini AI 1C v1.2.7.

**Что:** пользователь жмёт «Спроси про продажи» → видит **список шагов до выполнения**:
```
Я выполню:
  1. find_metadata(Документ.РеализацияТоваровУслуг)
  2. execute_query SELECT * FROM ... WHERE Период BETWEEN ...
  3. format_table

[Подтвердить] [Изменить план] [Прервать]
```

**Зачем:**
- **Безопасность:** read-only mode + явное подтверждение перед execute_code
- **Доверие:** аналитик понимает что система делает, не «магия»
- **Cost control:** видно если LLM пошла «не туда»

**Реализация:** новый orchestrator-режим `plan_first`:
1. LLM в planning mode → возвращает structured plan (JSON schema)
2. UI показывает план → ждёт confirm
3. Backend выполняет план шаг за шагом, показывая результат каждого

**Связь с проектом:** запреты v0/v0b НЕ затрагивают (это не Workflow editor — это **видимость плана**, не его создание пользователем).

### 5.2 Cells + Reactive Graph (Hex.tech-style)

**Что:** один диалог = последовательность ячеек:
```
[Cell 1] NL: "Покажи продажи за май"
         → execute_query SELECT ... WHERE Период = '2026-05'
         → TableCard (1247 строк)

[Cell 2] NL: "Сгруппируй по контрагентам, top-10"
         → reduce(cell_1, group=Контрагент, top=10)
         → TableCard (10 строк)

[Cell 3] NL: "Постройте диаграмму"
         → chart(cell_2)
         → ChartCard
```

**Reactive:** если пользователь правит Cell 1 («май» → «июнь») — Cell 2 и Cell 3 **автоматически пересчитываются**.

**Зачем:**
- **Воспроизводимый отчёт:** одна сессия = готовый отчёт для руководства
- **Композиция:** аналитик строит pipeline без программирования
- **Share URL:** ссылка на сессию = полный отчёт коллеге

**Реализация:** новый тип сообщения `cell`, новый виджет UI, новый orchestrator-режим, DAG executor.

**Trade-off:** invasive change. Не для v1.3.0. **M7-M8 candidate**.

### 5.3 Chat-команды `/explain`, `/optimize`, `/safe-rerun`

**Источник:** 1С:Напарник чат-навыки.

**Что:** короткие slash-команды в чате:
- `/explain <последний tool_call>` — объясни что делал последний запрос
- `/optimize <SQL>` — оптимизируй последний запрос
- `/safe-rerun` — повтори последний запрос с дополнительным confirm
- `/compare <session_id>` — сравни эту сессию с другой
- `/export pdf` — экспорт в PDF
- `/share` — создай share-link

**Реализация:** простой парсер на frontend → специальный backend endpoint per команда. Не блокирует основной /chat.

### 5.4 RAG-индексация при подключении новой базы

**Источник:** AI-агенты habr 1006230 (1 час индексации перед использованием).

**Что:** при первом подключении к базе 1С — фоновая 30-60 минутная индексация:
- Метаданные (имена объектов, реквизиты, типы)
- Экспортные методы общих модулей (имя + параметры + комментарий)
- Структура форм (для get_form_structure ответов)
- BSP version detection

**UI:** прогресс-бар в Channel Selector «Индексация: 47%». В режиме read-only можно использовать пока идёт.

**Trade-off:** invasive — требует Phase 10 RAG (DEFERRED). Активируется если LEARN engine возвращается.

### 5.5 Telegram secondary UI

**Источник:** PromptPilot (infostart 2653416) — Worker + FastAPI + SQLite WAL + TG-bot. Стек идентичен нашему.

**Что:** аналитик задаёт вопрос в Telegram-боте → пуш в основное приложение → ответ приходит в бот.

**Зачем:**
- «Дай мне квартальную сводку» с телефона на встрече
- Долгие запросы (30+ сек) — не висеть в браузере
- Уведомления о завершении aux LLM background_review

**Реализация:** библиотека `aiogram` (Python), bot connected к нашему FastAPI через webhook. ~3 дня работы.

---

## 6. Конкретные библиотеки для внедрения

Не общие концепты — конкретные npm/PyPI зависимости.

### 6.1 Python backend (FastAPI)

| Библиотека | Что даёт | Куда внедрить | Размер |
|---|---|---|---|
| **instructor** | Structured output через Pydantic, `Partial[T]` streaming, multi-provider | Replace JSON parsing в orchestrator/loop.py | ~100KB |
| **litellm** | Multi-LLM routing, fallback, retry, cooldown 429 | Replace прямые httpx.AsyncClient вызовы LLM | ~5MB |
| **microsoft-presidio-analyzer + presidio-anonymizer** | PII detection + redaction | `app/services/pii_shield.py` | ~50MB (spaCy models) |
| **sqlparse** | SQL AST parsing для validator | `app/services/sql_validator.py` | ~200KB |
| **tiktoken** | Pre-flight token counting | `app/services/token_counter.py` | ~3MB |
| **deepeval** | Eval framework, pytest-нативный | `tests/evals/` | ~500KB |
| **langfuse** | Observability self-hosted, OpenTelemetry-compatible | `app/middleware/observability.py` | ~2MB |
| **aiogram** | Telegram bot async | `app/integrations/telegram_bot.py` | ~3MB |
| **jemalloc** (system lib) | Async memory fragmentation fix | Docker image base | ~1MB |

### 6.2 Frontend (Next.js)

| Библиотека | Что даёт | Куда внедрить |
|---|---|---|
| **@tanstack/react-virtual** | Виртуализация TableCard ≥ 100 строк | `frontend/components/cards/TableCard.tsx` |
| **partial-json** | Streaming JSON parsing для inline cards | `frontend/lib/streaming-json.ts` |
| **mermaid** | WorkflowCard диаграммы | `frontend/components/cards/WorkflowCard.tsx` |
| **monaco-editor** + **monaco-diff-editor** | CodeCard + ComparisonCard (если ещё не подключён) | Cards |
| **ai** (Vercel AI SDK) | Streaming + Last-Event-ID + Resume | `frontend/lib/chat-stream.ts` |
| **html2pdf.js** или server-side puppeteer | PDF export TableCard (P2 backlog) | Server-side preferable |

### 6.3 Инфраструктура

| Tool | Что | Где |
|---|---|---|
| **HashiCorp Vault / Yandex Lockbox** | Хранилище API keys | Production-only, для BYO-режима enterprise |
| **Langfuse self-hosted** | Observability dashboard | Docker compose, ClickHouse под капотом |
| **Redis** (опц.) | Semantic cache GPTCache + rate limit tracker | Docker compose |
| **Zitadel** (опц.) | SSO для B2B РФ | Docker compose, AGPL 3.0 |

---

## 7. Архитектурные слои (новая модель)

Сейчас orchestrator/loop.py — единое место для всего. Предлагается **прослоить middleware-style:**

```
Frontend (Next.js)
    ↓ POST /chat (SSE)
┌───────────────────────────────────────────────────┐
│ FastAPI Backend                                    │
│                                                    │
│  Pre-LLM middleware:                               │
│  ├─ RateLimitGuard (E3/E4 from Hermes backlog)    │
│  ├─ CostGuard (token bucket, circuit breaker)     │
│  ├─ PII Shield (Presidio redact для cloud-LLM)    │
│  └─ Prompt Composer (system + history + tools)    │
│       ↓                                            │
│  Orchestrator Loop (с CircuitBreaker)             │
│  ├─ LLM call (LiteLLM router)                     │
│  │   → fallback chain: Qwen3 → MiMo → GigaChat    │
│  ├─ Tool call validator                            │
│  │   → strict JSON Schema + fuzzy match suggestion│
│  ├─ MCP call (через connection pool)              │
│  │   → SSE keepalive, Last-Event-ID resume        │
│  └─ Result processor                               │
│       ├─ ResultSizeGate (LIMIT 500 для LLM)       │
│       ├─ SQL Validator (AST если execute_query)   │
│       └─ Tool receipt (HMAC sign)                 │
│       ↓                                            │
│  Post-LLM middleware:                              │
│  ├─ PII Unmask (reverse mapping для UI)           │
│  ├─ Cost Tracker (usage_pricing real turns)       │
│  ├─ Fact-check validator (anti-hallucination)     │
│  └─ Observability (Langfuse spans)                 │
│       ↓                                            │
│  SSE Stream → Frontend                             │
│                                                    │
└───────────────────────────────────────────────────┘
```

**Зачем:** каждый middleware — независимый модуль, тестируется отдельно, можно включать/выключать. Текущий монолит orchestrator/loop.py становится тонким клиентом.

---

## 8. Eval harness — конкретный план

**Текущее:** 652 backend pytest + 304 vitest зелёные. **Но 0 регрессионных тестов на промпты.** Любое изменение system prompt — игра в рулетку.

### 8.1 Golden test pairs

```python
# tests/evals/golden_pairs.py
GOLDEN_PAIRS = [
    {
        "id": "ut11-sales-basic",
        "config": "УТ-11.5",
        "user_question": "Покажи продажи за май 2026",
        "expected_tools": [{"name": "execute_query", "args_pattern": r"Период.*2026-05"}],
        "expected_card_types": ["table"],
        "expected_topics": ["продажи", "период"],
        "forbidden_in_response": ["я не могу", "не знаю"],
    },
    {
        "id": "erp25-production-cost",
        "config": "ERP-2.5",
        "user_question": "Себестоимость продукции за квартал",
        "expected_tools": [...],
        ...
    },
    # 20-30 пар
]
```

### 8.2 DeepEval integration

```python
# tests/evals/test_regression.py
import pytest
from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualRelevancyMetric,
    HallucinationMetric,
)

@pytest.mark.parametrize("pair", GOLDEN_PAIRS)
def test_orchestrator_regression(pair):
    response = orchestrator.run(pair["user_question"], config=pair["config"])
    
    # Check expected tools called
    assert any(t.name == pair["expected_tools"][0]["name"] for t in response.tool_calls)
    
    # Check cards
    assert pair["expected_card_types"][0] in [c.type for c in response.cards]
    
    # DeepEval metrics
    test_case = LLMTestCase(
        input=pair["user_question"],
        actual_output=response.text,
        expected_output=" ".join(pair["expected_topics"]),
    )
    evaluate([test_case], metrics=[AnswerRelevancyMetric(), HallucinationMetric()])
```

### 8.3 CI gate

```yaml
# .github/workflows/eval.yml
- name: Run regression evals
  run: pytest tests/evals/ -m eval --eval-budget 5
  env:
    MIMO_API_KEY: ${{ secrets.MIMO_API_KEY }}
  # Fails build if score < 0.85
```

**Стоимость:** 20-30 запросов × ~5 центов = $1-2 за прогон. Раз в PR.

### 8.4 Использовать Транзит-кейсы из MEMORY

```python
# tests/evals/transit_real_cases.py — реальные баги
TRANSIT_CASES = [
    {
        "id": "arm-empty-lists",
        "from_memory": "russian_transit_arm_empty_lists_root_2026_05_20.md",
        "user_question": "В АРМ пустые списки документов после выбора контрагента",
        "expected_tools": ["execute_query"],
        "expected_topics": ["дубликаты контрагентов", "разрешённые в запросах"],
        "ground_truth": "Дубль контрагента К1 (608 ОПП) vs К2 (0 ОПП). Объединение через ОбщегоНазначения.ЗаменитьСсылки",
    },
    # ...
]
```

---

## 9. Sharing/collaboration детально (под Hex.tech-pattern)

### 9.1 Share-link на сессию

**MVP:** read-only URL `/shared/<token>` с TTL 7 дней:
```
https://analyst.example.com/shared/abc123def456
```

**Доступ:** read-only view сессии, без возможности отправить новое сообщение. Каждый visitor видит идентичный snapshot.

**Реализация:** новая таблица `shared_sessions` (token, session_id, expires_at, view_count).

### 9.2 PDF / PPTX export

**PDF:** server-side через Puppeteer → render session page → save as PDF.
**PPTX:** Python `python-pptx` → каждая card = слайд.

**Когда нужно:** аналитик делает доклад руководству → нужны слайды быстро.

### 9.3 Comments inline на карточку

Hex.tech-style: каждая card может иметь thread комментариев.

**Use case:** аналитик отправил share-link бухгалтеру → бухгалтер пишет комментарий «здесь не учтены проводки X» → аналитик видит уведомление.

**v2:** real-time через WebSocket. **MVP:** static comments + refresh.

### 9.4 Bookmarks

«Сохранить этот ответ как закладку» → быстрый доступ из Sidebar.

### 9.5 Cmd-K fuzzy search по сессиям

Уже в P2 backlog. Дополняется search по тексту cards (через FTS5 в SQLite).

### 9.6 Telegram export

`/share` в чате → отправить summary в Telegram-канал (для команды).

---

## 10. Pricing & Multi-tenant — конкретные цифры

### 10.1 3-tier pricing model

| Тир | Цена | Включено | Целевая аудитория |
|---|---|---|---|
| **Соло** | 1 990 ₽/мес | 1 user, 5M токенов YandexGPT/GigaChat в месяц, 1 база 1С, history 30 дней | Фриланс-аналитик, внедренец-одиночка |
| **Команда** | 3 900 ₽/seat (от 3 seats) | Multi-user, 50M токенов pool, до 10 баз, sharing, comments, audit log, 90 дней history | Франчайзи 3-15 чел, корп IT-отдел |
| **Enterprise** | Custom (от 30 000 ₽/мес) | Unlimited tokens (BYO ключи или Yandex Lockbox), SSO (Zitadel/Bitrix24), on-prem MCP, audit log unlimited, SLA, дед-pickr РФ-ДЦ | 1С-партнёры 15+ чел, корпорации |

**Trial:** 14 дней full access, 100K токенов лимит, watermark на export.

### 10.2 Stripe vs российская тарификация

**Платежи:**
- **YooKassa** (Яндекс) — стандарт РФ B2B SaaS, фискализация
- **Tinkoff Касса** — alternative
- Stripe — игнорировать для РФ (санкции)

**Биллинг:** monthly post-paid с прогнозом по usage в месяц.

### 10.3 Multi-tenant архитектура — pooled на старте

**SQLite (текущее)** → **Postgres + RLS** при выходе в SaaS:

```sql
-- Каждая таблица с tenant_id
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    ...
);

-- RLS policy
CREATE POLICY tenant_isolation ON sessions
    USING (tenant_id = current_setting('app.current_tenant')::UUID);
```

**Self-hosted Electron режим** — остаётся SQLite. SaaS — Postgres.

### 10.4 Биллинг с прозрачным token counter

В Settings → Usage:
```
Этот месяц:
  ████████░░ 80% использовано (4M / 5M токенов)
  
  По дням:
    Пн ████ 350K
    Вт ██ 180K
    ...
  
  По задачам:
    Запросы:       1.2M
    Объяснение:    800K
    Генерация:     500K
    ...
  
  Прогноз до конца месяца: 5.5M (+10% over)
  
  [Купить дополнительные токены]
  [Перейти на Команду]
```

**Без этого** — Replit-стиль непредсказуемость = убийство доверия.

---

## 11. Российские LLM — детальное сравнение для проекта

| Модель | Source | Cost (₽/1K tok) | BSL quality | Function calling | РФ-ДЦ | 152-ФЗ |
|---|---|---|---|---|---|---|
| **Cloud.ru Qwen3-Coder-480B** | Cloud.ru | **0** (free tier) | ★★★★ | ✓ | ✓ | ✓ |
| **YandexGPT 5 Pro** | Yandex | 1.2 | ★★ | ✓ | ✓ | ✓ |
| **YandexGPT 5 Lite** | Yandex | 0.4 | ★★ | ✓ | ✓ | ✓ |
| **GigaChat 2 Pro** | Sber | 0.5 | ★★★ | ✓ | ✓ | ✓ |
| **GigaChat 2 Lite** | Sber | 0.065 | ★★ | ✓ | ✓ | ✓ |
| **T-Pro 2.0** | T-Bank (open) | self-host | ★★ | ✓ | self-host | ✓ |
| **MiMo 7B** (текущее) | Xiaomi | дёшево | ★★ | ★ basic | ✗ Китай | ✗ |
| **Claude Sonnet 4.6** через GenAPI | GenAPI | дорого | ★★★★★ | ✓ | ✗ (proxy) | требует согласие |
| **GPT-4o** через GenAPI | GenAPI | дорого | ★★★★ | ✓ | ✗ (proxy) | требует согласие |

**Главный pivot:** **MiMo → Cloud.ru Qwen3-Coder-480B**. Бесплатно, лучшее качество на коде, в РФ, 152-ФЗ compliant.

**MiMo оставить:** как option для опытных users (если кто-то конкретно его хочет).

---

## 12. Observability с Langfuse — детальный план

### 12.1 Что показывает Langfuse

- **Traces:** каждый /chat = trace из spans: prompt construction → LLM call → tool calls → response
- **Costs:** реальная стоимость каждого диалога (по usage в LLM response)
- **Latency breakdown:** где тратится время
- **Errors:** percentile, top errors
- **User feedback:** thumbs up/down per ответ
- **Comparison:** A/B test разных промптов

### 12.2 Self-hosted setup

```yaml
# docker-compose.langfuse.yml
services:
  langfuse-server:
    image: langfuse/langfuse:3
    ports:
      - "3001:3000"  # avoid conflict with our :3010
    env:
      - DATABASE_URL=postgresql://...
      - NEXTAUTH_SECRET=...
  
  langfuse-postgres:
    image: postgres:16
    ...
```

### 12.3 Integration в наш FastAPI

```python
# backend/app/middleware/observability.py
from langfuse import Langfuse
from langfuse.openai import OpenAI  # drop-in replacement

langfuse = Langfuse(host="http://localhost:3001", secret_key="...")

# В orchestrator/loop.py
@langfuse.observe(name="chat_loop")
async def run_chat(session_id, user_message):
    trace = langfuse.trace(...)
    
    with langfuse.span(name="llm_call"):
        response = await llm.chat.completions.create(...)
    
    with langfuse.span(name="tool_call"):
        tool_result = await mcp.call_tool(...)
    
    trace.update(output=response.text)
```

### 12.4 Что увидим через неделю production

- Топ-10 самых дорогих диалогов → оптимизировать
- Топ ошибок → починить
- Latency breakdown → где bottleneck
- Какие prompts работают лучше других

---

## 13. Granular roadmap по фазам

### M7 (после v1.3.0 release, ~1 неделя)

**Тема:** Production readiness — закрыть P0 failures.

1. ResultSizeGate (P0-3) — backend + frontend virtualization
2. CircuitBreaker на tool calls (P0-1)
3. API key → backend-only (P0-2)
4. SQL AST validator (P0-4)
5. UI BLOCKER fixes B-1 ... B-5
6. Tailwind config consolidation (v3/v4)
7. Version drift fix
8. Live LLM smoke session (закрыть один из 6 «не верифицировано»)

**Acceptance:** v1.3.1 stable release без P0 failures.

### M8 (~2 недели)

**Тема:** 152-ФЗ compliance + Observability.

1. **Cloud.ru Qwen3-Coder-480B как default** LLM
2. GigaChat 2 Pro fallback
3. PII Shield (Presidio) middleware для cloud-LLM
4. Регистрация в реестре операторов ПД
5. Langfuse self-hosted setup
6. OpenLLMetry instrumentation
7. SSE Last-Event-ID resume

**Acceptance:** компания готова к корп-клиенту в РФ.

### M9 (~2 недели)

**Тема:** Tool reliability + Eval.

1. Structured output (JSON Schema strict) для всех card-генераций
2. Instructor `Partial[T]` для streaming cards
3. DeepEval в pytest + 20 golden pairs
4. CI gate на eval threshold
5. Tool receipts HMAC (anti-fabrication)
6. Fact-check validator (anti-compensation hallucination)

**Acceptance:** меньше галлюцинаций, прозрачные источники в ответах.

### M10 (~2-3 недели)

**Тема:** Конкурентные фичи.

1. **Plan→Execute→Validate** видимый план перед tool calls
2. Chat-команды `/explain`, `/optimize`, `/safe-rerun`, `/export`, `/share`
3. Share-link на сессию (read-only)
4. PDF/PPTX export
5. Telegram secondary UI (aiogram)
6. LiteLLM multi-LLM router с fallback chain

**Acceptance:** feature-parity с конкурентами + 2-3 уникальных фичи.

### M11 (~3-4 недели)

**Тема:** RAG возврат + Cells.

1. Phase 10 RAG возвращается:
   - БСП corpus (ssl_3_2/ssl_3_1) индексирован
   - Hybrid retrieval (BM25 + sqlite-vec)
   - Citations cards
2. Cells + Reactive Graph (Hex-style)
3. Configuration detector (УТ/ERP/КА/БГУ) → tailored system prompts

**Acceptance:** product становится уникальным на рынке.

### M12+ (1 квартал)

**Тема:** Enterprise + Multi-tenant.

1. Postgres + RLS вместо SQLite (для SaaS режима)
2. SSO через Zitadel
3. Stripe-аналог (YooKassa) интеграция
4. 3-tier pricing model запуск
5. Bitrix24 OAuth коннектор
6. Audit log unlimited (Enterprise)
7. BYO API keys (Yandex Lockbox)

**Acceptance:** готовность к корп-продажам.

---

## 14. Что НЕ предлагаю (после deep дайва)

| Идея | Почему отказ |
|---|---|
| LangChain как dependency | Overhead для single-project, vendor lock-in. Брать точечно: Instructor + Langfuse + LiteLLM |
| LangSmith Hub для prompts | Pricing + vendor lock-in. Заменить файлами `.yaml` + watchdog hot reload (30 мин работы) |
| Real-time co-editing | Слишком сложно, нужен Y.js/Liveblocks. Comments inline + share-link достаточно |
| Inhouse CRM | Слив маржи. Outbound webhook + Bitrix24 OAuth коннектор |
| Voice input | Out-of-scope MVP, не критично |
| Mobile app native | Out-of-scope. Web responsive (≥1280px desktop, но и iPad возможно как viewer-only) |
| Polyfill для всех браузеров | Только Chromium-based (Edge, Chrome) — это Electron stack |
| Локальный Ollama / ALL LLM локально | Pivot 2026-05-08 — cloud-only |
| Tree-sitter BSL grammar | Никто не сделал, самим 2+ нед |
| Своя tokenization для всех LLM | tiktoken для оценки + usage из response — достаточно |
| Self-hosted Stripe-альтернатива | YooKassa proven для РФ B2B |

---

## 15. Открытые вопросы для пользователя

После deep research остались **вопросы где нужен твой выбор**:

1. **Pivot на Cloud.ru Qwen3-Coder-480B вместо MiMo как default LLM** — согласен?
   - Pros: бесплатно, лучше на BSL, РФ-ДЦ, 152-ФЗ
   - Cons: invasive migration MiMo → новый провайдер

2. **Cells + Reactive Graph** vs текущая линейная история — какой режим важнее?
   - Cells: уникальная фича, отстраиваемся от Aether/Напарника
   - Линейная: проще, уже работает

3. **152-ФЗ регистрация** — когда инициировать?
   - Сейчас (до v1.3.0): даёт уверенность в продаже корп-клиентам
   - После первого PoC: economy

4. **Telegram bot** как secondary UI или Web-only?
   - Telegram: PromptPilot-стек, лишний канал
   - Web-only: проще, фокус

5. **Plan→Execute→Validate** видимый план — внедрить как:
   - Default mode (более безопасно, но больше кликов)
   - Opt-in mode (как сейчас, добавить toggle в Settings)

6. **Eval harness DeepEval** — golden pairs:
   - Брать из реальных Транзит-кейсов в memory
   - Создать синтетический набор для УТ/ERP demo
   - Оба

7. **MCP read-only канал** (feenlace/mcp-1c) — добавить рядом с 1С MCP Toolkit:
   - Сейчас (v1.3.x): default для prod-баз
   - M9+: после observability

---

## 16. Связь с существующим IDEAS-FROM-STACK-2026-05-21.md

| Категория в первом файле | Соответствие в этом ADDENDUM | Статус |
|---|---|---|
| §1 RAG / Phase 10 | §13 M11 (RAG возврат) | Дополнено: ВНЕДРИТЬ в M11 |
| §2 MCP-стратегия read-only | §1 P0-2 + §2 P1 | Усилено: P0 priority |
| §3 Промпт-инжиниринг | §5.3 Chat-команды + §8 Eval | Дополнено |
| §4 Multi-config awareness | §13 M11 (configuration detector) | Без изменений |
| §5 Новые карточки | §9 (sharing) + §5.2 Cells | Заменён Cells подход |
| §6 Качество ответов | §1-2 (failure modes) + §8 (eval) | Сильно расширено |
| §7 Безопасность | §3 (152-ФЗ) + §1 (P0-2/P0-4) | Сильно расширено |
| §8 DevX | §6 (libraries) | Конкретизировано |
| §9 Knowledge offline | §13 M11 | Без изменений |
| §10 Eval harness | §8 (DeepEval план) | Конкретизировано |
| — (новое) | §3 152-ФЗ | **НОВАЯ КАТЕГОРИЯ** |
| — (новое) | §4 Технический долг | **НОВАЯ КАТЕГОРИЯ** |
| — (новое) | §10 Pricing | **НОВАЯ КАТЕГОРИЯ** |
| — (новое) | §12 Observability | **НОВАЯ КАТЕГОРИЯ** |

---

## 17. Источники

### Из deep research 2026-05-21

- `.claude/research/1c-knowledge-roadmap-2026-05-21/` — общий research roadmap
- 5 параллельных subagent отчётов (deep-researcher) по: Inventory проекта, Конкуренты, Failure modes, Tech trends 2026, Monetization/152-ФЗ

### Конкуренты

- [Aether Lab tariffs](https://aether-lab.ru/products/query-console/tariffs/) · [docs](https://aether-lab.ru/query-console/docs/)
- [1С:Напарник](https://code.1c.ai/) · [Портал ИТС](https://portal.1c.ru/applications/1C-Second-Pilot)
- [AI-агент внутри 1С (habr 1006230)](https://habr.com/ru/articles/1006230/) — Plan→Execute→Validate
- [PromptPilot (infostart 2653416)](https://infostart.ru/1c/articles/2653416/) — стек идентичен нашему
- [MiroFish (habr 1020504)](https://habr.com/ru/companies/1yes/articles/1020504/) — симуляция через граф
- [Mini AI 1C v1.2.7 (infostart 2639822)](https://infostart.ru/1c/articles/2639822/)
- [Hex Notebook Agent](https://hex.tech/blog/introducing-notebook-agent/) — Cells + Reactive Graph

### Failure modes

- [Claude Code #60061 SSE drop](https://github.com/anthropics/claude-code/issues/60061)
- [MCP HTTP 89 min hang #21721](https://github.com/anthropics/claude-code/issues/21721)
- [SqliteError multi-tab #1155](https://github.com/WiseLibs/better-sqlite3/issues/1155)
- [opencode SSE leak 7GB #17628](https://github.com/anomalyco/opencode/issues/17628)
- [P2SQL Injection (ICSE25)](https://syssec.dpss.inesc-id.pt/papers/pedro_icse25.pdf)
- [Tool Receipts NABAOS (arxiv 2603.10060)](https://arxiv.org/html/2603.10060v1)
- [BetterUp jemalloc memory leak FastAPI](https://build.betterup.com/chasing-a-memory-leak-in-our-async-fastapi-service-how-jemalloc-fixed-our-rss-creep/)

### Tech trends

- [Instructor docs](https://python.useinstructor.com/)
- [LiteLLM Router](https://docs.litellm.ai/docs/routing)
- [Langfuse GitHub](https://github.com/langfuse/langfuse)
- [DeepEval](https://www.braintrust.dev/articles/deepeval-alternatives-2026)
- [Vercel AI SDK 6](https://vercel.com/blog/ai-sdk-6)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

### Monetization & legal

- [152-ФЗ AI обработка ПД (habr 1015694)](https://habr.com/ru/articles/1015694/)
- [Локализация ПД с 1 июля 2025](https://comply.ru/tpost/c43ezsout1-lokalizatsiya-i-transgranichnaya-peredac)
- [Microsoft Presidio](https://github.com/microsoft/presidio)
- [Cloud.ru free LLM access](https://cloud.ru/blog/besplatniy-dostup-k-open-source-llm-modelyam)
- [GigaChat API tariffs](https://developers.sber.ru/docs/ru/gigachat/api/tariffs)
- [YandexGPT обзор 2026](https://ai-journal.ru/yandexgpt/)
- [Cursor Pricing 2026](https://cursor.com/pricing)
- [Zitadel vs Keycloak](https://blog.houseoffoss.com/post/keycloak-vs-authentik-vs-zitadel-2026-which-open-source-login-tool-should-you-use)
- [Hex.tech Pricing](https://hex.tech/pricing/)

### Внутренняя кухня проекта

- `.planning/STATE.md` (M6 closed 2026-05-20)
- `.planning/UI-REVIEW-2026-05-21.md` (47/100)
- `.planning/phases/06-hermes/SPRINT-SUMMARY.md`
- `.planning/phases/10-learn-engine/DEFERRED.md`
- `.claude/memory/open-questions.md`
- `.claude/memory/distribution.md`

---

## Финальная сводка

**Что добавлено в ADDENDUM (vs первый файл):**
- 4 P0 failure modes с готовыми решениями
- 6 P1 failure modes
- Категория 152-ФЗ compliance целиком
- 5 BLOCKER текущего технического долга
- 5 конкретных фич конкурентов (Plan→Execute, Cells, Chat-команды, RAG-индексация, Telegram)
- 9 конкретных Python библиотек + 6 frontend
- 6-фазная granular roadmap (M7 → M12+)
- 7 open questions для решения тобой
- Pricing model с конкретными цифрами 1990₽ / 3900₽ / Custom

**Total добавлено:** ~50 KB конкретной аналитики, 17 секций, 80+ источников.

**Следующий шаг:** обсудить open questions §15 → запустить M7 (Production readiness P0 fixes).
