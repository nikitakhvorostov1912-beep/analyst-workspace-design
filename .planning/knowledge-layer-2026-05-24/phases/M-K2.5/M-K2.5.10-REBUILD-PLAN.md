# M-K2.5.10 — Real LLM Card Rebuild (Production-Quality Эталон)

> Полная замена 63 197 mock-карточек на эталонные карточки от real LLM.
> Все 4 типовые: БП 3.0 / КА 2.5 / УТ 11.5 / ERP 2.5.

---

## 1. Контекст и зачем

После закрытия Phase v2.0 (CRITICAL Preventive) карточки технически
безопасны (помечены `is_mock=1`, валидируются против графа, имеют
hard limits и closed vocab), но **содержимое = шаблонный stub**:

```yaml
# Mock-карточка (типовой пример):
summary: "Документ «РеализацияТоваровУслуг»."
purpose: "Структурный элемент, тип Документ. Записывает движения в 8 регистр(ов)."
posting_flow: ["Срабатывает ОбработкаПроведения"]
typical_scenarios: []
preconditions: []
```

Это бесполезно для бизнес-аналитика. Бот может отвечать только пересказом
структуры графа, без методологии. **M-K2.5.10 создаёт ЭТАЛОННЫЕ карточки**
через real LLM, чтобы бот объяснял **бизнес-смысл** каждого объекта.

После M-K2.5.10:
- ✅ 63 197 карточек с реальным методологическим описанием
- ✅ `is_mock = False` для всех успешно сгенерированных
- ✅ Validation pass rate ≥ 95% (LLM не галлюцинирует)
- ✅ Бот отвечает аналитику как грамотный методолог 1С

---

## 2. Scope

### 2.1 Что включено

| Конфигурация | Объектов | channel_id |
|---|---:|---|
| БП 3.0.138.24 (Бухгалтерия) | 11 713 | `_bp30_138_24` |
| КА 2.5.25.92 (Комплексная) | 19 683 | `_ka2_25_92` |
| УТ 11.5.17.226 (Управление торговлей) | 11 781 | `_ut115_17_226` |
| ERP 2.5.21.118 (ERP) | 20 020 | `_erp25_21_118` |
| **Итого** | **63 197** | |

### 2.2 Что НЕ включено

- ❌ ЗУП 3.1 / УСО 2.5 / Документооборот 3 — нет графов (Phase 8 pending)
- ❌ ITS-нормативка в `its_links` — отдельная фаза M-K4
- ❌ Реальный re-embed (embedding API вызовы) — отдельный шаг после rebuild
- ❌ Клиентские базы — M-K3

---

## 3. Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│  CLI typical_cards_rebuild.py                                │
│  ├─ resolve LLM provider (user_secrets → endpoint+model+key) │
│  ├─ filter cards (channel / kind / status / is_mock)         │
│  ├─ chunk batches (default 50, configurable)                 │
│  ├─ progress checkpoint (resume on crash)                    │
│  └─ telemetry (tokens / cost / latency / errors)             │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│ build_card_context()     │  │ validate_card_against_graph  │
│ (existing M-K2.5.5)      │  │ (existing M-K2.5.9.5)        │
│                          │  │                              │
│ Собирает контекст из     │  │ После генерации — проверка   │
│ графа: attributes,       │  │ phantom_movement /           │
│ methods, writes_to, ...  │  │ phantom_related              │
└──────────────────────────┘  └──────────────────────────────┘
              │                         ▲
              ▼                         │
┌──────────────────────────┐            │
│ OpenAICompatLLMCaller    │            │
│ (NEW M-K2.5.10.2)        │            │
│                          │            │
│ HTTP non-stream POST     │            │
│ /chat/completions        │            │
│ + rate limit + retry     │            │
│ + cost tracking          │            │
└──────────────────────────┘            │
              │                         │
              ▼                         │
        Real LLM API                    │
        (MiMo/DeepSeek/etc.)            │
              │                         │
              ▼                         │
     JSON ответ → parse → ──────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│ upsert_card(card, is_mock=False, llm_model=<real_model>)     │
│ save_validation_result(validation_result)                    │
│ Checkpoint .planning/.../rebuild-checkpoint-{channel}.json   │
└──────────────────────────────────────────────────────────────┘
```

### 3.1 Где живёт API key

**НЕ в коде, НЕ в коммите.** Через существующую инфраструктуру
`user_secrets` (AES-GCM шифрование, ключ дешифровки в `app_master_key`):

```python
# Сохранить:
await save_user_secret(db, key="typical_rebuild_llm_api_key", value="sk-...")
await save_user_secret(db, key="typical_rebuild_llm_endpoint", value="https://...")
await save_user_secret(db, key="typical_rebuild_llm_model", value="model-name")

# Прочитать в CLI:
api_key = await get_user_secret(db, "typical_rebuild_llm_api_key")
```

CLI команда для администратора:
```bash
python -m scripts.set_rebuild_credentials \
  --endpoint "https://api.deepseek.com/v1" \
  --model "deepseek-chat" \
  --api-key-prompt   # ввод через stdin без echo, не через argv
```

### 3.2 Выбор провайдера

Адаптер универсальный (OpenAI-compatible), поддерживает 4 опции:

| Провайдер | Endpoint | Цена 63k | Качество | Note |
|---|---|---:|---|---|
| **DeepSeek** | api.deepseek.com/v1 | $2-5 | Хорошо | Дёшево, на русском OK, рекомендую |
| **NVIDIA NIM** | integrate.api.nvidia.com/v1 | $0 free tier | Хорошо | nvidia/llama-3.3-nemotron — дефолт проекта |
| **MiMo / Xiaomi** | (нужен URL) | TBD | Хорошо | Если ключ от Xiaomi cloud |
| **OpenAI GPT-4o-mini** | api.openai.com/v1 | $50-80 | Отлично | Топ качество, нужен отдельный ключ |

**Шаг 4 плана**: Probe тестового ключа против всех 4 endpoints, выбираем
тот что работает + лучшее соотношение цена/качество.

---

## 4. Этапы реализации

### M-K2.5.10.1 — План (этот документ) ✅

### M-K2.5.10.2 — OpenAICompatLLMCaller adapter (~1 час)

Новый файл `app/knowledge/typical/openai_compat_llm_caller.py`:

- Реализует `LLMCaller` Protocol (existing из card_generator.py)
- Конструктор: `endpoint, model, api_key, timeout=180, temperature=0.2`
- Метод `complete(messages) -> LLMResponse`:
  - HTTP POST `/chat/completions` через httpx (non-streaming)
  - `response_format={"type": "json_object"}` где поддерживается
  - Парсинг `choices[0].message.content` + `usage` (tokens)
  - Возврат `LLMResponse(content, tokens_in, tokens_out, model)`
- Error handling:
  - 429 Too Many Requests → exponential backoff (1s, 2s, 4s, 8s, max 60s, max 5 retry)
  - 503 Service Unavailable → backoff с retry
  - 5xx → 3 retry с backoff, потом fail
  - 4xx (auth/bad request) → fail immediately
- Cost tracking:
  - `calculate_cost(tokens_in, tokens_out, model)` → USD
  - Хардкод prices для DeepSeek / NVIDIA / OpenAI / Anthropic
- 5 unit-тестов через respx mock

### M-K2.5.10.3 — Secure key storage (~30 мин)

- Использовать existing `user_secrets` (AES-GCM из P2.1, commit `app/storage/secrets.py`)
- CLI скрипт `scripts/set_rebuild_credentials.py`:
  - Запрашивает endpoint / model через argv
  - Запрашивает api-key через `getpass.getpass()` (не через argv — не попадёт в shell history)
  - Сохраняет 3 secrets: `typical_rebuild_llm_endpoint`, `_model`, `_api_key`
  - Без ключа в логах / output
- 2 unit-теста (save + retrieve)

### M-K2.5.10.4 — Probe ключа (~15 мин)

CLI `scripts/probe_llm_provider.py`:

- Принимает api_key
- Пробует endpoints в порядке: DeepSeek → NVIDIA → OpenAI → Anthropic
- На каждом — простой call `messages=[{"role": "user", "content": "Привет"}]`
- Печатает provider name + status (200 OK / 401 Unauthorized / etc.)
- Не сохраняет ключ нигде

### M-K2.5.10.5 — Bulk rebuild CLI (~2 часа)

Расширенный `scripts/typical_cards_rebuild.py` поверх existing
`typical_cards_pilot.py`:

**Параметры:**
```
--channel-id          фильтр канала (default: все)
--object-kind         фильтр kind (Document/Catalog/...)
--limit               ограничение количества (для тестов)
--only-mock           rebuild только is_mock=True (default True)
--batch-size          сколько в parallel (default 5)
--rate-limit-rps      max requests per second (default 10)
--retry-max           max retries per card (default 3)
--checkpoint-dir      где хранить progress (default .planning/.../checkpoints/)
--resume              продолжить с последнего checkpoint
--dry-run             не вызывать LLM, только посчитать что будет сделано
--confirm             обязательный флаг для реальной записи
```

**Workflow на каждую карточку:**
1. Проверить is_mock=True (skip иначе)
2. Загрузить CardContext через build_card_context()
3. Если context пустой (нет графа) — skip с warning
4. Вызвать LLM через OpenAICompatLLMCaller
5. Парсить ответ через _payload_to_card()
6. Validate через validate_card_against_graph()
7. Save: upsert_card(is_mock=False, llm_model=<real>) + save_validation_result()
8. Append в checkpoint file
9. Обновить telemetry

**Telemetry per channel:**
- total_processed / total_failed / total_skipped
- cumulative tokens_in / tokens_out
- cumulative cost USD
- validation: valid / issues_found / object_not_in_graph counts
- avg latency per card
- ETA до finish

**Checkpoint format** (JSON):
```json
{
  "channel_id": "_bp30_138_24",
  "started_at": "2026-05-27T12:00:00Z",
  "last_updated": "2026-05-27T13:30:00Z",
  "total_in_channel": 11713,
  "processed_qnames": ["Document.A", "Document.B", ...],
  "failed_qnames": [{"qname": "X", "error": "..."}],
  "cost_usd": 1.23,
  "tokens_total": 4567890
}
```

Resume: при `--resume` скрипт читает checkpoint, фильтрует processed_qnames,
продолжает с unprocessed.

### M-K2.5.10.6 — Pilot rebuild на 10 объектах БП (~10 минут)

Конкретный список «звёздных» объектов БП для pilot:

1. `Document.РеализацияТоваровУслуг`
2. `Document.ПоступлениеТоваровУслуг`
3. `Document.СчётФактураВыданный`
4. `Document.СчётФактураПолученный`
5. `Document.АвансовыйОтчёт`
6. `Document.ПриходныйКассовыйОрдер`
7. `Document.РасходныйКассовыйОрдер`
8. `Document.ПлатёжноеПоручениеИсходящее`
9. `Catalog.Контрагенты`
10. `ChartOfAccounts.Хозрасчетный`

После rebuild:
- Бот ответ через explain_typical_object на каждый — есть `summary`, `purpose`, `key_attributes` с осмысленными role, `movements` с direction+condition, `posting_flow` 4-6 шагов, `typical_scenarios` 2-4, `related_objects` 5-8 имён
- Validation: error_count == 0 для всех 10
- Пользователь смотрит вручную → green light

### M-K2.5.10.7 — Bulk rebuild всех 63k (~6-12 часов wallclock)

После green light на pilot:

```bash
# БП (11k):    ~1-2 часа
python -m scripts.typical_cards_rebuild --channel-id _bp30_138_24 --only-mock --confirm

# КА (20k):    ~2-3 часа
python -m scripts.typical_cards_rebuild --channel-id _ka2_25_92 --only-mock --confirm

# УТ (12k):    ~1-2 часа
python -m scripts.typical_cards_rebuild --channel-id _ut115_17_226 --only-mock --confirm

# ERP (20k):   ~2-3 часа
python -m scripts.typical_cards_rebuild --channel-id _erp25_21_118 --only-mock --confirm
```

Запускаются последовательно (parallel'ный bulk = риск hit rate limit
сразу с 4 каналов). Каждый через `run_in_background` с мониторингом
checkpoint файла.

### M-K2.5.10.8 — Auto-validation (~30 минут)

Скрипт `scripts/typical_cards_validate_all.py`:
- Для каждой карточки в БД (или фильтр) → validate_card_against_graph()
- Save validation_result
- Печать сводки: 
  - total / valid / issues_found / object_not_in_graph
  - phantom_movement count
  - phantom_related count
  - missing_movement count (info, не error)

**Acceptance**: `error_count / total < 5%` для каждой типовой.
Если выше — корректируем prompt и re-rebuild карточек с error.

### M-K2.5.10.9 — Quality assurance (~30 мин)

1. **Spot-check 20 случайных карточек** из 4 типовых (5 от каждой):
   - summary > 50 символов и не template stub
   - purpose > 80 символов и описывает бизнес-смысл
   - movements[].direction заполнен (если есть movements)
   - movements[].condition осмысленный (если есть movements)
   - typical_scenarios имеет ≥ 1 элемент для документов
   - related_objects ссылается на существующие в графе объекты

2. **Расширенный smoke (130+ проверок)**: добавить Q22-Q31:
   - Q22: explain Реализации в УТ возвращает summary > 100 chars
   - Q23: bot answer для «зачем СчётФактура» содержит «НДС»/«налог»
   - Q24: validation_status='valid' для топ-10 объектов всех 4 типовых
   - Q25: is_mock=False для всех успешно ребилт
   - ...

3. **Полный typical/* регресс**: 400+ тестов зелёные.

### M-K2.5.10.10 — Closing (~15 мин)

- Atomic commit на каждый шаг (10 commits total)
- FF merge ветки в main
- Push origin/main
- Удалить feature ветку
- Обновить STATE.md + SUMMARY.md с финальными метриками:
  - Total carts rebuilt
  - Total cost USD
  - Total tokens
  - Validation pass rate %
  - Времени wallclock

---

## 5. Acceptance criteria (финальные)

**Все обязательные:**

- [ ] **63 197 / 63 197 карточек** имеют `is_mock = False` после rebuild
- [ ] **63 197 / 63 197 карточек** имеют `validation_status IS NOT NULL` (проверены валидатором)
- [ ] **Validation error_rate < 5%** для каждой типовой (БП / КА / УТ / ERP)
- [ ] **0 карточек со status='failed'** (все либо `generated`, либо `embedded`)
- [ ] **summary len > 50 chars** для 99% карточек (содержательный текст, не stub)
- [ ] **purpose len > 80 chars** для 95% карточек (бизнес-смысл, не шаблон)
- [ ] **Roundtrip 200/200 случайных** карточек parsable через from_payload_json
- [ ] **API key не попадает** ни в код, ни в коммиты, ни в логи (grep по «sk-» в репо — пусто)
- [ ] **Cost фактический ≤ заложенному бюджету** (зависит от провайдера, см. §3.2)
- [ ] **Все 400+ typical/* тестов зелёные** (полный регресс)
- [ ] **Smoke 130+ проверок** зелёные (109 v2.0 + 20+ M-K2.5.10)
- [ ] **Spot-check 20 случайных** — экспертная оценка пользователя
- [ ] **STATE.md + SUMMARY.md** обновлены с метриками
- [ ] **FF merge в main + push** успешен

---

## 6. Бюджет и время

### Время wallclock

| Шаг | Время |
|---|---|
| M-K2.5.10.1 План | 30 мин (этот документ) |
| M-K2.5.10.2 Adapter | 1 час |
| M-K2.5.10.3 Key storage | 30 мин |
| M-K2.5.10.4 Probe | 15 мин |
| M-K2.5.10.5 Bulk CLI | 2 часа |
| M-K2.5.10.6 Pilot 10 объектов | 10 мин LLM + 30 мин ревью |
| **M-K2.5.10.7 Bulk 63k** | **6-12 часов LLM time** (в фоне) |
| M-K2.5.10.8 Validation | 30 мин |
| M-K2.5.10.9 QA + smoke | 30 мин |
| M-K2.5.10.10 Closing | 15 мин |
| **Итого активной работы** | **~6 часов** |
| **+Bulk фон** | **6-12 часов** (не блокирует) |

### Стоимость по провайдерам

Расчёт на 63 197 карточек × ~3 500 input tokens × ~700 output tokens =
~221M input + ~44M output ≈ 265M total tokens.

| Провайдер | Input $/M | Output $/M | Cost 63k | Note |
|---|---:|---:|---:|---|
| **DeepSeek-chat** | $0.07 | $1.10 | **~$64** | Рекомендую baseline |
| **DeepSeek-coder** | $0.014 | $0.28 | **~$15** | Если контент в основном JSON-ориентирован |
| NVIDIA Nemotron (free tier) | $0 | $0 | **$0** | Лимит 4 RPM / 1000 RPD → 63d не успеет, нужен paid tier |
| GPT-4o-mini | $0.15 | $0.60 | **$60** | Топ качество, баланс |
| GPT-4o | $2.50 | $10.00 | **$1 000** | Слишком дорого |
| Anthropic Claude Haiku 3.5 | $0.80 | $4.00 | **$350** | Качество хорошее |
| Anthropic Claude Sonnet 4.5 | $3.00 | $15.00 | **$1 320** | Эталон, слишком дорого |

**Рекомендация**: DeepSeek-chat или GPT-4o-mini (~$60-65). Если ключ
пользователя не подходит ни к одному — обсуждаем дальше.

---

## 7. Риски и mitigation

| Риск | Вероятность | Mitigation |
|---|---|---|
| API ключ не работает на пробных endpoints | Средняя | M-K2.5.10.4 probe заранее, выбираем рабочий или говорим user |
| LLM выдаёт невалидный JSON | Средняя | response_format=json_object + retry с corrective prompt + fallback на mock для проблемных |
| Rate limit от провайдера | Высокая | Exponential backoff + token bucket + adaptive RPS |
| Cost overrun (LLM пишет слишком многословно) | Средняя | Pydantic hard limits (M-K2.5.9.3) обрезают output; cost monitor с safety threshold |
| Crash в середине bulk | Низкая | Checkpoint после каждой карточки → resume |
| Validation > 5% error rate | Средняя | Корректируем prompt с дополнительной инструкцией о graph facts, re-rebuild карточек с error |
| Privacy concern (код типовой → облако) | Низкая | Это **публичные** типовые конфигурации 1С. ADR-003 уже подтверждает legal-clean. PII нет. |
| 4 типовых вместе превышают бюджет | Низкая | Поэтапный rebuild (по 1 типовой), pause после каждой для cost review |

---

## 8. Rollback plan

Если на любом шаге что-то идёт сильно не так:

1. **Карточки сохраняются атомарно** через upsert_card — старая карточка
   перезаписывается только если новая успешно сгенерирована и валидирована.
2. **БД checkpoint** перед bulk rebuild:
   `COPY typical_object_cards TO typical_object_cards_pre_rebuild`
3. При проблемах:
   ```sql
   -- Восстановить mock-карточки за один SQL:
   UPDATE typical_object_cards
   SET card_payload = (SELECT card_payload FROM typical_object_cards_pre_rebuild WHERE id = ...),
       is_mock = 1, llm_model = 'mock-generator-v1', ...
   WHERE channel_id = '<problematic>';
   ```
4. **Feature ветка**: вся работа на `feature/m-k2.5.10-real-llm-rebuild`,
   FF merge в main делается **только после** acceptance criteria PASS.
5. **Партиальный rollback**: можно откатить только 1 типовую (например ERP)
   а БП / КА / УТ оставить ребилт.

---

## 9. Что НЕ делаем в M-K2.5.10 (out of scope)

- ❌ Реальный re-embed карточек через embedding API (отдельный шаг M-K2.5.11)
- ❌ ИТС-ссылки в `its_links` (M-K4)
- ❌ Cross-config diff (M-K3)
- ❌ Прогон на ЗУП / УСО / Документооборот (нужны графы — Phase 8 pending)
- ❌ Web UI для управления rebuild (CLI достаточно)
- ❌ A/B сравнение mock vs real (можем добавить если нужно)

---

## 10. Зависимости

### От предыдущих фаз (всё готово)
- ✅ Граф для 4 типовых (Phase 8: 917k nodes, 1.71M edges)
- ✅ Cards storage / models / generator (Phase 5)
- ✅ LLMCaller Protocol (Phase 5)
- ✅ build_card_context (Phase 5)
- ✅ Pydantic safeguards (Phase v2.0 step-1/3/4)
- ✅ is_mock flag (Phase v2.0 step-2)
- ✅ Validator (Phase v2.0 step-5)
- ✅ Embedding versioning (Phase v2.0 step-6)
- ✅ user_secrets infrastructure (P2.1)

### Новое в M-K2.5.10
- OpenAICompatLLMCaller (адаптер)
- Bulk rebuild CLI с checkpoint
- Auto-validation CLI
- Spot-check checklist
- Cost tracking + telemetry

### От пользователя
- API ключ к одному из провайдеров (есть тестовый `sk-s1lyss...` — проверяем M-K2.5.10.4)
- Подтверждение что privacy ОК (передача публичных типовых в облако)
- Acceptance ревью pilot на 10 объектах
- Acceptance ревью spot-check 20 карточек

---

## 11. Что увидит пользователь после M-K2.5.10

### До rebuild (сейчас, mock)

Пользователь: *«Как работает Реализация в УТ?»*

Бот: *«Документ РеализацияТоваровУслуг в УТ. По структуре графа: реквизиты Контрагент, Договор, Склад, Валюта; делает движения в регистр ТоварыНаСкладах. ⚠️ Подробное методологическое описание — mock-данные, не верифицированы экспертом.»*

### После rebuild (real LLM)

Пользователь: *«Как работает Реализация в УТ?»*

Бот: *«**Документ РеализацияТоваровУслуг** — основной документ оперативного учёта продаж в УТ 11.5.

**Назначение:** Регистрирует факт реализации товаров/услуг покупателю, генерирует движения по 8 регистрам учёта. Влияет на расчёт выручки, себестоимости и взаиморасчётов.

**Ключевые реквизиты:**
- Контрагент — получатель товара и плательщик
- Договор — основание расчётов, фиксирует условия оплаты
- Склад — источник списания товаров
- Валюта — валюта взаиморасчётов

**При проведении:**
1. Проверка остатков товаров на складе
2. Расчёт себестоимости (по методу учётной политики)
3. Списание из ТоварыНаСкладах
4. Формирование задолженности в РасчётыСКлиентами
5. Запись в Продажи для отчётности
6. Регистрация НДС если ОСНО

**Типичные сценарии:** оптовая отгрузка, розница через РМК, услуги, комиссионная торговля.

**Связано с:** ВозвратТоваровОтПокупателя, СчётФактураВыданный, ПоступлениеБезналичныхДенежныхСредств.»*

Это уровень **опытного методолога 1С** вместо пересказа структуры.

---

## 12. Решения которые я принимаю «сам полноценно»

По указанию пользователя «делай для всех текущих конф»:

- ✅ **Scope: 4 типовые × все объекты** = 63 197 карточек (full rebuild, не selective)
- ✅ **Privacy: legal-clean** — публичные типовые, без клиентских баз, ADR-003 подтверждает
- ✅ **Provider: probe + автовыбор** — пробуем тестовый ключ против DeepSeek / NVIDIA / OpenAI / Anthropic, выбираем рабочий; если ни один не работает — обсуждаем с пользователем
- ✅ **Cost ceiling: $100** — если probe показывает что rebuild стоит >$100, ставим на pause и обсуждаем
- ✅ **Pilot mandatory** — 10 объектов БП перед bulk, пользователь смотрит вручную
- ✅ **Bulk последовательно** — БП → КА → УТ → ERP (не parallel, чтобы не упереться в rate limit)
- ✅ **Auto-validation после rebuild** — все карточки получают validation_status
- ✅ **Atomic commits per step** — 10 commits, rollback granular

---

**Следующий шаг:** M-K2.5.10.2 — реализация `OpenAICompatLLMCaller` adapter.
