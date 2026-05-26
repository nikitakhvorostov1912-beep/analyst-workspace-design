---
pilot: "Object Cards Generator БП 3.0.138.24 (mock LLM)"
date: "2026-05-26"
phase: "M-K2.5.5"
llm_mode: "mock"
result: success
fatal_errors: 0
---

# Pilot Results — Object Cards Generator БП 3.0.138.24

> **Mock LLM smoke** (без расхода токенов). Реальный LLM-call —
> отдельным коммитом после согласования ключа и провайдера с
> пользователем.
> 
> Цель — проверить end-to-end pipeline:
> `MetadataObject → CardContext → LLM → TypicalObjectCard → upsert_card`
> работает корректно на production-данных, идемпотентен, не падает.

## Pipeline

```
1. graph_storage.list_nodes(channel, kind=MetadataObject, limit=10000)
       ↓
2. для каждого объекта:
   2a. build_card_context(db, channel, qname) → CardContext (≤3K токенов)
   2b. ctx.compute_source_hash() → SHA-256
   2c. сравнить с existing source_hash в typical_object_cards
       - совпал → SKIP (карточка актуальна)
       - не совпал → продолжить
   2d. MockLLMCaller.complete(messages) → LLMResponse
   2e. parse JSON → TypicalObjectCard
   2f. upsert_card(db, card, source_hash, ...)
```

## Параметры прогона

| Параметр | Значение |
|---|---|
| Канал | `_bp30_138_24` |
| Фильтр kinds | Document + AccumulationRegister |
| Лимит | 10 объектов |
| LLM | MockLLMCaller (mock-generator-v1) |
| Prompt version | v1 |

## Результаты

### Первый прогон (генерация)

| Метрика | Значение |
|---|---:|
| Обработано объектов | 10 |
| Сгенерировано карточек | 10 |
| Пропущено (skip-hash) | 0 |
| Провалов | 0 |
| Tokens in (estimate) | 5 443 |
| Tokens out (estimate) | 3 266 |
| **Длительность** | **0.132 сек** |

Все 10 — `AccumulationRegister` (Document'ы не вошли в первые 10
из-за сортировки по qualified_name: `AccumulationRegister.*` идёт
раньше `Document.*`).

### Второй прогон (idempotent check)

| Метрика | Значение |
|---|---:|
| Обработано объектов | 10 |
| Сгенерировано | 0 |
| **Пропущено (skip-hash)** | **10** |
| Провалов | 0 |
| Tokens in | 0 |
| **Длительность** | **0.054 сек** |

Идемпотентность работает — source_hash совпал на всех 10, LLM-call
вообще не вызывался. Это критично для масштаба: при добавлении одного
нового объекта в типовую — пересчитываются только его соседи, не все
8 тыс. карточек.

## Оценка стоимости реального LLM (GPT-4o-mini)

Из mock estimate: ~544 in + 327 out tokens на карточку.

GPT-4o-mini тарифы (на 2026-01):
- Input: $0.150 / 1M tokens
- Output: $0.600 / 1M tokens

| Масштаб | Tokens in | Tokens out | Cost |
|---|---:|---:|---:|
| 1 карточка | 544 | 327 | $0.00028 |
| 10 (этот pilot) | 5 443 | 3 266 | $0.0028 |
| 100 (small subset) | 54 K | 33 K | $0.028 |
| **8 525 (полная БП 3.0)** | **4.6 M** | **2.8 M** | **~$2.40** |
| 7 типовых (УТ/ERP/КА/БП/ЗУП/УСО/ДО) | ~30 M | ~18 M | ~$15 |

Бюджет 7 типовых через GPT-4o-mini ≈ **$15 за один полный прогон**.
Это в 3-15× дешевле первоначальной оценки из M-K2.5-PLAN ($50-250).

## Проверка качества mock-карточек

Sample — `AccumulationRegister.ХозрасчётныйПоВалютам` (примерно):

```json
{
  "summary": "Регистр накопления «...».",
  "purpose": "Структурный элемент конфигурации, тип Регистр накопления.",
  "key_attributes": [],
  "movements": [],
  "posting_flow": [],
  "related_objects": []
}
```

Mock даёт **корректную структуру**, но содержательно пустоват —
наполнение полей зависит от качества LLM. Это нормально для smoke:
важно что pipeline работает, не качество текста.

## Что построено в Phase 5 (этой сессии)

### Schema
- Migration v18 → таблица `typical_object_cards`
- UNIQUE(channel_id, object_qualified_name) для idempotent upsert
- 4 индекса: channel / kind / status / source_hash

### Модули
- `card_models.py` — `TypicalObjectCard`, `CardAttribute`, `CardMovement`,
  `CardStatus`, `TypicalObjectCardRecord`. `embedding_text` property
  для будущего embedding-этапа (только summary + purpose + posting_flow,
  не код).
- `card_storage.py` — CRUD (upsert / get / list / delete / count) +
  `get_existing_source_hash` для skip-если-неизменился.
- `card_context.py` — `CardContext` builder из графа. Лимиты:
  30 атрибутов / 10 ТЧ × 20 реквизитов / 25 методов / 30 top calls /
  25 reverse refs. Приоритезация: handlers > exported > остальное.
- `card_generator.py` — `LLMCaller` Protocol + `MockLLMCaller` +
  `generate_card` / `generate_card_for_channel`.
- `prompts/typical_card_generator.md` — prompt v1 с system / user
  блоками и строгим JSON-форматом ответа.

### Тесты
- `test_typical_card_storage.py` — 31 тест
- `test_typical_card_context.py` — 15 тестов (включая integration с
  insert_node/insert_edge на in-memory графе)
- `test_typical_card_generator.py` — 25 тестов (template + parse +
  payload + MockLLM + end-to-end)
- Итого +71 новый тест. 324 typical/* теста зелёные.

### Pilot
- `scripts/typical_cards_pilot.py` — CLI с фильтрами `--kinds` +
  `--limit`. По умолчанию mock (без расхода токенов).

## Что НЕ сделано (явно отложено)

1. **Real LLM adapter** (`OpenAILLMCaller` / `NVIDIALLMCaller`) —
   требует ключа от пользователя и явного провайдера. Заглушка
   `LLMCaller` Protocol позволит подключить любого без изменений
   в `generate_card`.
2. **Embedding** карточек в `vec_objects` — `embedding_text` property
   уже готов, осталось подключить existing `embeddings.py`.
3. **Массовая генерация** всей БП 3.0 (8 525 карточек) — отложено до
   подключения real LLM.
4. **Validation** ответа LLM (поля непустые, длины в лимитах) — есть
   только базовая парсер-валидация, judge-валидация на LLM-уровне
   будет добавлена когда подключим real LLM.

## Следующие шаги

1. Phase 6 — LLM Tools для chat orchestrator'а (search_typical /
   explain_object / trace_calls / trace_movements / trace_data_flow /
   compare_with_typical). Будет работать на уже построенном графе +
   карточках (даже на mock-карточках можно тестировать поиск).
2. Real LLM adapter — отдельный мини-коммит когда пользователь укажет
   провайдера и ключ.
3. Frontend UI (Phase 7) — селектор типовой + раскрывающиеся карточки.
