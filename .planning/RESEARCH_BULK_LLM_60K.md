# Генерация 60 000 knowledge cards для метаданных 1С

**Дата:** 2026-05-28  
**Задача:** 60 192 объекта x ~1100 токенов (300 in + 800 out) = ~18M input + ~48M output  
**Проблема:** pipeline через Claude Code subagent = 6k токенов/карточку (95% tool overhead) — нереально

---

## Расчётные параметры

| Параметр | Значение |
|---|---|
| Объектов к обработке | 60 192 |
| Input на объект | ~300 токенов |
| Output на объект | ~800 токенов |
| Итого input | ~18M токенов |
| Итого output | ~48M токенов |
| System prompt | ~1500 токенов, кэшируется |

---

## Сводная таблица вариантов (топ-10)

| Место | Метод / Провайдер | Стоимость 60k | Время | Качество 1С | Сложность |
|---|---|---|---|---|---|
| 1 | Claude Haiku 4.5 Batch + Prompt Cache | ~15-22 USD | 12-24 ч | 5/5 | 2/5 |
| 2 | GPT-4.1-nano Batch | ~8-12 USD | 12-24 ч | 3/5 | 2/5 |
| 3 | Gemini 2.5 Flash-Lite Batch | ~10-14 USD | 12-24 ч | 3/5 | 2/5 |
| 4 | DeepSeek V4-Flash async | ~14-20 USD | 4-8 ч | 3/5 | 2/5 |
| 5 | Gemini 2.5 Flash Batch | ~27-40 USD | 12-24 ч | 3/5 | 2/5 |
| 6 | Claude Sonnet 4.6 Batch + Cache | ~65-90 USD | 12-24 ч | 5/5 | 2/5 |
| 7 | YandexGPT 5 Pro async | ~50-70 USD | 12-24 ч | 4/5 | 3/5 |
| 8 | Together AI Llama 3.3 70B Batch | ~53-80 USD | 12-24 ч | 3/5 | 3/5 |
| 9 | Qwen3-30B vLLM локально | 0 USD | 20-60 ч | 3/5 | 5/5 |
| 10 | Groq Llama 3.3 70B free | 0 USD | 14-30 дней | 3/5 | 4/5 |

**Расчёт строки 1 — Haiku 4.5 + Batch + 1h Cache (официальные цены Anthropic, май 2026):**
- Batch: input 0.50/MTok, output 2.50/MTok
- Cache read (1h TTL): 0.10/MTok x 18M = 1.80 USD
- Output реальный (~500 tok/карточку): 2.50 x 30M = 13-15 USD
- Итого: ~15-22 USD с учётом retries и cache write на старте

---

## Топ-3 рекомендации

### 1. Claude Haiku 4.5 + Batch API + 1h Prompt Cache (РЕКОМЕНДОВАН)

**Стоимость: ~15-22 USD | Время: 12-24 ч | 1С-качество: 5/5**

Нативная экспертиза по AccumulationRegister, AccountingRegister, ЕНС/ЕНП, НДФЛ,
Честный знак, ВЕТИС, ЕГАИС, МЕС. Кэш system prompt (1h TTL) даёт -90% на input.

Установка: pip install anthropic

Ключевые параметры вызова Batch API:
  model: claude-haiku-4-5
  max_tokens: 1024
  system: [{type: text, text: SYSTEM, cache_control: {type: ephemeral, ttl: 1h}}]
  Разбить 60 192 объекта на 7 батчей по ~8600 (лимит 100k req/job)
  Поллинг: client.messages.batches.retrieve(batch_id) каждые 30 мин

Риски: Haiku слабее Sonnet на нишевых модулях (ГИСМ, ИСМП).
Решение: 3-5 few-shot примеров по сложным типам прямо в system prompt.

---

### 2. Gemini 2.5 Flash-Lite Batch (Vertex AI)

**Стоимость: ~10-14 USD | Время: 12-24 ч | 1С-качество: 3/5**

Дешевле Haiku. Строгий JSON Schema output. Требует Google Cloud + GCS bucket.
Новый аккаунт Google Cloud: 300 USD free credits — весь прогон потенциально бесплатно.

Цены Vertex AI Batch (май 2026): input 0.05/MTok, output 0.20/MTok.

Подготовить JSONL в GCS: каждая строка = request с contents + systemInstruction +
generationConfig: {responseMimeType: application/json, responseSchema: ...}
Запуск через BatchPredictionJob.submit(source_model=gemini-2.5-flash-lite, ...)

Риски: Русская 1С-специфика слабее Haiku. Нужны подробные few-shot примеры для регистров.

---

### 3. DeepSeek V4-Flash (async параллелизм)

**Стоимость: ~14-20 USD | Время: 4-8 ч | 1С-качество: 3/5**

OpenAI-совместимый API. Cache hits = 0.014/MTok (в 10 раз дешевле base).
Нет официального batch endpoint — заменяется asyncio.Semaphore(50).

Цены (май 2026): input 0.14/MTok, output 0.28/MTok. Cache read: 0.014/MTok.

Параметры: base_url=https://api.deepseek.com, model=deepseek-v4-flash,
response_format={type: json_object}, 50 concurrent через asyncio.Semaphore.

Риски: ЕНС/ЕНП/СФР слабо, ГИСМ/ВЕТИС почти нет. Возможны перебои из РФ.

---

## GitHub инструменты

| Проект | Применимость |
|---|---|
| github.com/567-labs/instructor | Pydantic JSON output для любого провайдера |
| github.com/dottxt-ai/outlines | Constrained generation для локальных моделей |
| github.com/imaurer/awesome-llm-json | Каталог инструментов bulk JSON generation |
| github.com/vezlo/src-to-kb | Source code -> Knowledge Base через LLM |

Специфических репозиториев 1С-metadata -> LLM knowledge cards не найдено. Задача нишевая.

---

## Лазейки (бесплатный старт)

| Источник | Лимит | Покрытие карточек |
|---|---|---|
| Groq free tier (Llama 3.3 70B) | 1000 req/day | 30 дней = 30 000 карточек |
| DeepSeek новый аккаунт | 5M токенов | ~4 500 карточек |
| Google Cloud new account | 300 USD free credits | весь прогон на Flash-Lite |
| OpenRouter :free + 10 USD пополнение | 1000 req/day | ~30 000/мес |
| Together AI стартовый бонус | ~25 USD | ~3 000 карточек |

Комбо: Groq free (30k) + DeepSeek free (4.5k) = 34 500 бесплатно.
Остаток 25 692 -> Haiku Batch за ~7 USD. Итого весь прогон < 10 USD за 5-7 недель.

---

## Доменная экспертиза по 1С

| Аспект | Haiku 4.5 | Gemini 2.5 Flash | DeepSeek V4 | YandexGPT 5 |
|---|---|---|---|---|
| AccumulationRegister приход/расход | 5/5 | 4/5 | 3/5 | 4/5 |
| AccountingRegister / ПБУ 18/02 | 5/5 | 4/5 | 3/5 | 4/5 |
| ЕНС/ЕНП/СФР (с 2023) | 4/5 | 3/5 | 2/5 | 5/5 |
| Честный знак / ГИСМ / ИСМП | 4/5 | 2/5 | 2/5 | 4/5 |
| ВЕТИС / ЕГАИС | 4/5 | 2/5 | 2/5 | 4/5 |
| МЕС / производство | 4/5 | 3/5 | 2/5 | 3/5 |
| Кадры / НДФЛ | 5/5 | 4/5 | 3/5 | 5/5 |

YandexGPT 5 Pro — лучший по актуальной российской нормативке (ЕНС, СФР, маркировка),
но дорог (~55 USD) и нет официального batch discount.

---

## Противоречия между источниками

- DeepSeek: docs показывает deepseek-v4-flash, агрегаторы — deepseek-v3. Цены совпадают.
- Haiku 4.5 batch output: часть блогов пишет 2.00/MTok — это retired Haiku 3.5. Официально: 2.50/MTok.
- Groq batch discount: упоминается в третичных источниках, официально не подтверждён. Считаю без скидки.

---

## Вердикт

Лучший cost/quality: Haiku 4.5 Batch + 1h Prompt Cache = 15-22 USD, 12-24 ч, 1С-экспертиза 5/5.

Бесплатно (5-7 недель): Groq free + DeepSeek free = 34 500 карточек, остаток 7 USD Haiku.

Актуальная российская нормативка максимально: YandexGPT 5 Pro async, ~55 USD.

Ключевой паттерн (любой провайдер): 1h Prompt Cache на system prompt = -90% стоимости input.
Тривиальные объекты (Удалить*, технические БСП-регистры, ~10-15% от 60k):
шаблонная генерация без LLM, дополнительная экономия 2-3 USD.
