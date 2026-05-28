# DEEP RESEARCH -- 60K JSON-КАРТОЧЕК: НЕСТАНДАРТНЫЕ МЕТОДЫ

**Тема:** Массовая генерация 60 000 JSON-карточек метаданных 1С
**Домен:** LLM batch inference / cost engineering
**Дата:** 2026-05-28
**Профиль:** 300 tok input + 800 tok output = 1 100 tok/карточку -> 66M токенов суммарно

---

## СТАТИСТИКА ИССЛЕДОВАНИЯ

- Поисковых запросов: 12
- Источников проанализировано глубоко: 10 (WebFetch)
- Нестандартных методов: 8
- Противоречий: 2

---

## КРИТИЧЕСКИЙ ФАКТ: claude -p НЕ ИДЁТ В ПОДПИСКУ

По умолчанию --bare -p использует ANTHROPIC_API_KEY, не OAuth Max-плана.
Источник: GitHub Issue #37686 -- пользователь получил 1800 USD счёт за 2 дня.
С июня 15, 2026: claude -p потребляет отдельный Agent SDK credit.

**Параллельный запуск 5+ инстансов ночью -> выбьет лимит за часы.**

---

## ВАРИАНТ 1: Haiku 4.5 Batch API + Prompt Cache 1h (РЕКОМЕНДОВАН ДЛЯ ПЛАТНОГО)

Официально подтверждено: batch (-50%) и cache (-90%) стекаются мультипликативно.
Источник: platform.claude.com/docs/en/about-claude/pricing (проверено 2026-05-28).

| Компонент | Токены | Стоимость |
|-----------|--------|-----------|
| Haiku 4.5 batch dynamic input (200 tok x 60k) | 12M | .00 |
| Cache write 1h (5k sys prompt, 1 раз) | 5K | /usr/bin/bash.01 |
| Cache read (batch 0.5 x cache 0.1) | 54M x 0.05 | .70 |
| Haiku 4.5 batch output (800 tok x 60k) | 48M | 20.00 |
| **ИТОГО** | | **~29** |

Без оптимизации: 58. Экономия 50%.

Плюсы: официальный API, JSON schema через tool_use, качество 1С-домена.
Минусы: 29 из кармана, 24ч ожидание.

---

## ВАРИАНТ 2: Modal + vLLM Qwen 2.5 7B (САМЫЙ ДЕШЁВЫЙ)

Modal docs: ~4 цента за M токенов, ~2000 output tok/sec на A100.

| Параметр | Значение |
|----------|----------|
| 48M output токенов / 2000 tok/sec | 6.7 часов |
| Стоимость 66M токенов x 4 цента/M | .64 |
| Modal free credits при регистрации | 0 |
| **Из кармана** | **/usr/bin/bash (free credits покрывают)** |

Архитектура:
- modal.com: регистрация -> 0 credits
- vLLM LLM(model=Qwen/Qwen2.5-7B-Instruct)
- GuidedDecodingParams(json=CARD_SCHEMA) -- гарантированный JSON
- Checkpoint каждые 5k документов
- Итого 6-8 часов A100, /usr/bin/bash из кармана

Плюсы: /usr/bin/bash (free credits), checkpoint-and-resume, JSON гарантия.
Минусы: Qwen для 1С-специфики (ЕНС, ВЕТИС) нужен few-shot, 6-8ч GPU.

---

## ВАРИАНТ 3: Knowledge Distillation + LoRA (ГЛАВНЫЙ ЛАЙФХАК)

Идея: сгенерировать 500 эталонов дорогой моделью, обучить дешёвую, гнать 60k локально.

Фаза 1 -- 500 эталонов Sonnet batch:
- 500 x 1100 tok x .50/MTok = /usr/bin/bash.83 (2-4 часа)

Фаза 2 -- LoRA fine-tune Qwen 2.5 7B на Kaggle (бесплатно):
- Kaggle T4x2 GPU, free, 4 часа
- LoRA rank=64, 3 epochs
- Источник arxiv KD-LoRA: 98% качества учителя при 40% меньшем GPU

Фаза 3 -- 60k inference RunPod spot A10G:
- /usr/bin/bash.30/час x 9 часов = .70
- Или Modal free (/usr/bin/bash из кармана)

| Этап | Стоимость |
|------|-----------|
| 500 эталонов Sonnet batch | /usr/bin/bash.83 |
| Fine-tune Kaggle | /usr/bin/bash |
| 60k inference RunPod spot | .70 |
| **ИТОГО** | **< ** |

Плюсы: в 30x дешевле Haiku Batch, после fine-tune модель знает твой 1С-домен.
Минусы: 2 дня setup, нужна верификация 100 карточек после генерации.

---

## ВАРИАНТ 4: OpenRouter Free Models (БЕСПЛАТНО, МЕДЛЕННО)

27 бесплатных моделей май 2026. Rate limit: 20 req/min, 200 req/day на модель.
Лучшие для русского: DeepSeek V4 Flash (1M ctx), Qwen3 Coder, Llama 3.3 70B.

- 200 req/day x 5 моделей = 1000 карточек/день
- 60k = 60 дней (1 аккаунт) или 20 дней (3 аккаунта x 5 моделей)
- Стоимость: /usr/bin/bash

---

## ВАРИАНТ 5: GitHub Actions + Max OAuth (НЕ РАБОТАЕТ ДЛЯ 60K)

OAuth токен истекает каждые ~24ч (issue #727 anthropics/claude-code-action).
Все parallel jobs тянут из одного weekly pool.
Max 20x: ~220k tok/5h -> 200 карточек/окно.
60k / 200 = 300 окон = 1500 часов = 62 дня.

**Вывод: из подписки за 1 день -- невозможно физически.**

---

## COMBO-ПЛАН РЕКОМЕНДОВАННЫЙ

### Combo A: Быстро, /usr/bin/bash -- 1 день

1. Зарегистрировать modal.com -> 0 free credits
2. Написать ~100 строк Python с vLLM + GuidedDecodingParams
3. Запустить 60k batch на A100 (6-8 часов)
4. Верифицировать 200 случайных карточек

Итого: /usr/bin/bash, 1 рабочий день.

### Combo B: Максимальное качество -- 2 дня, < 

1. День 1 утро: 500 эталонов Sonnet batch (/usr/bin/bash.83)
2. День 1 вечер: fine-tune Qwen 2.5 7B на Kaggle (бесплатно, 4ч)
3. День 2: 60k inference RunPod spot или Modal free (~/usr/bin/bash-3)

Итого: < , профессиональный pipeline на будущее.

---

## ПРОТИВОРЕЧИЯ

1. claude -p vs подписка: офиц. docs говорят OAuth работает в headless.
   Issue #37686: если ANTHROPIC_API_KEY в env -> API billing.
   Разрешение: --bare ВСЕГДА требует API key (документировано явно).
   Без --bare и без env var -> OAuth может работать, но ненадёжно.

2. Cache + Batch стекаются: ПОДТВЕРЖДЕНО официальной pricing страницей 2026-05-28.
   Мультипликатив: batch 0.5 x cache_read 0.1 = 0.05 от base price.

---

## ПРЯМОЙ ОТВЕТ

60k за 1 день БЕЗ дополнительных $ к Max-подписке: НЕТ.
Max физически ограничен ~200 карточками/5h окно.

60k за 1 день бесплатно через Modal free 0 credits: ДА.

60k за  через LoRA distillation за 2 дня: ДА.

---

## НАЙДЕННЫЕ GITHUB ПРОЕКТЫ

- vllm-project/vllm: examples/offline_inference/structured_outputs.py
- instructor-ai/instructor: 11k+ stars, Pydantic schemas, Anthropic + Qwen
- raine/claude-code-proxy: proxy Claude Code через другие подписки
- anthropics/claude-code-action: GitHub Actions OAuth (практично только для <100 карточек)

Специфических open-source 1C-metadata-to-knowledge-card нет.
Ближайший аналог: SAP/Salesforce metadata enrichment -- только закрытые корпоративные.

---

## ИСТОЧНИКИ

- https://platform.claude.com/docs/en/about-claude/pricing
- https://code.claude.com/docs/en/headless
- https://modal.com/docs/examples/vllm_throughput
- https://github.com/anthropics/claude-code/issues/37686
- https://costgoat.com/pricing/openrouter-free-models
- https://docs.vllm.ai/en/latest/features/structured_outputs/
- https://arxiv.org/pdf/2410.20777 (KD-LoRA)
- https://codersloth.medium.com/how-to-install-claude-as-a-github-action-on-a-pro-or-max-subscription-a8de7dc18c32
