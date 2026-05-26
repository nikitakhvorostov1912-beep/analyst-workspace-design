# M-K2.5 Typical Configurations Knowledge — PLAN

> Параллельный milestone между M-K2 (Knowledge Foundation) и M-K3
> (Relational + Behavioral). Цель: бот глубоко понимает логику типовых
> конфигураций 1С (УТ, ERP, КА, БП, ЗУП, УСО, Документооборот).

## Цель

После закрытия M-K2.5 пользователь спрашивает: «Объясни как в УТ 11.5
работает проведение РеализацииТоваровУслуг» — и бот отвечает с
детализацией:

- Какие движения создаются (8 регистров)
- В каком порядке вызываются процедуры
- Какие проверки выполняются (остатки, цены, контрагент)
- Что делает РАУЗ в этом сценарии
- Какие предусловия из учётной политики влияют

С ссылками на карточки объектов + ИТС стандарты + БСП-методы.

## Use cases (приоритизированы)

| Запрос пользователя | Tool которое использует LLM |
|---|---|
| «Объясни как работает проведение X» | `explain_object` |
| «Где меняется поле Y?» | `trace_calls` (reverse search по WRITES_TO + USES) |
| «Что доработано в этом коде относительно типовой?» | `compare_with_typical` |
| «Откуда берётся цена в строке этого документа?» | `trace_data_flow` |
| «Почему документ не проводится?» | `diagnose` (M-K3 + типовые + ИТС combined) |
| «Какие регистры пишет этот документ?» | `trace_movements` |
| «Найди мне справочник для хранения договоров с банком» | `search_typical` |

## Декомпозиция на phases

### Phase 0 — Infrastructure (1 день)

**Цель:** база данных + python skeleton готовы принимать типовые.

**Артефакты:**
- Migration v17: `typical_configurations` (реестр) + `typical_indexing_runs` (журнал)
- `backend/app/knowledge/typical/registry.py` — namespace резервирование
- `backend/app/knowledge/typical/storage.py` — CRUD
- ADR-003 — почему snapshot, почему embedding только описаний, почему 6 графов
- Тесты ≥25 unit

**Acceptance:** pytest зелёный, backend стартует без ошибок, миграция применяется на пустой и существующей БД.

### Phase 1 — BSL Parser AST (1.5 недели)

**Цель:** production-уровневый BSL парсер.

**Варианты реализации:**
- **A.** tree-sitter-bsl (community grammar 1c-syntax/tree-sitter-bsl)
- **B.** BSL Language Server (у нас уже есть `tools/bsl-language-server-0.29.0-exec.jar`) через subprocess + JSON-RPC
- **C.** Расширение существующего regex-парсера из `bsp_loader.py`

**Рекомендация:** A (tree-sitter) — самый стабильный, есть Python bindings.
B как fallback если grammar окажется неполной. C — только для прототипа.

**Артефакты:**
- `backend/app/knowledge/typical/bsl_ast.py` — парсер
- `backend/app/knowledge/typical/bsl_models.py` — frozen dataclasses (Module / Method / Variable / Region / CompileDirective)
- Поддержка регионов, директив #Если, маркеров `// Доработка START/END`
- Тесты на синтетических BSL fixtures (минимум 40)

### Phase 2 — Query Parser (1 неделя)

**Цель:** BSL Query Language → структура без выполнения.

**Артефакты:**
- `backend/app/knowledge/typical/query_ast.py`
- Извлечение: таблицы (физические + виртуальные), поля, фильтры, соединения, ВТ
- Связь: какой регистр читается / пишется (для графа движений)
- Тесты на запросах из БСП (минимум 30)

### Phase 3 — XML Metadata Parser (1 неделя)

**Цель:** Configuration.xml + дерево папок → объекты метаданных.

**Артефакты:**
- `backend/app/knowledge/typical/xml_parser.py`
- Документы / регистры / справочники / отчёты / формы / подписки на события / регламентные задания / роли
- Связи: документ X → ПодпискаНаСобытия Y → модуль Z
- Тесты на синтетической XML-выгрузке (минимум 25)

### Phase 4 — Semantic Graph Builder (2 недели)

**Цель:** 6 графов поверх одной типовой через graph_storage.

**Графы:**
1. **CALLS** — метод A → вызывает метод B (из BSL AST)
2. **CONTAINS** — модуль содержит метод, документ содержит реквизит
3. **USES** — метод использует тип / справочник
4. **WRITES_TO** — документ → регистр (через `Движения.X.Записать()`)
5. **READS_FROM** — отчёт → регистр (через `Запрос` или `.Остатки()`)
6. **REFERENCES** — реквизит → справочник через тип

**Артефакты:**
- `backend/app/knowledge/typical/graph_builder.py`
- 6 extractor функций
- Тесты на синтетических данных (минимум 50)

### Phase 5 — Object Cards Generator (2 недели)

**Цель:** LLM-описание каждого ключевого объекта на русском.

**Структура карточки:**
```yaml
object: "Документ.РеализацияТоваровУслуг"
config: "UT_115_18_193"
summary: "Документ продажи товаров и услуг покупателю..."
purpose: "Регистрирует факт реализации в БУ и управленческом учёте"
key_attributes:
  - Контрагент: "получатель"
  - Договор: "основа для расчётов и НДС"
  - Склад: "источник списания товаров"
movements:
  - регистр: "РегистрНакопления.ТоварыНаСкладах"
    направление: "расход"
    условие: "при списании реальных товаров"
  - регистр: "РегистрНакопления.ВзаиморасчетыСКонтрагентами"
    направление: "приход/расход в зависимости от ВидаДоговора"
  ...
posting_flow:
  - "Заполнение шапки реквизитов"
  - "Подбор товаров через ТЧ"
  - "Проверка остатков и резервов"
  - "Расчёт НДС"
  - "Запись движений в 8 регистров"
typical_scenarios:
  - "Оптовая продажа со склада"
  - "Возврат от покупателя через тот же документ"
preconditions:
  - "УчётнаяПолитика.УчётНДС включён"
  - "Контрагент.НеЯвляетсяОрганизацией"
related_objects:
  - "Документ.ВозвратТоваровОтПокупателя"
  - "Регистр.ПродажиПоВидамДеятельности"
its_links:
  - "std.proveryat_zapolnenie_polej"
```

**Технология:**
- LLM: GPT-4o-mini (дешёво) или GPT-4o (качественно)
- Промпт: code → анализ → структура → русское описание
- Эмбедятся **только summary + purpose + posting_flow** (не сам код)
- ~5 тыс объектов × $0.01-0.05 = **$50-250 на конфигурацию через GPT-4o-mini**

**Артефакты:**
- `backend/app/knowledge/typical/card_generator.py`
- Промпт-шаблон в `prompts/typical_card_generator.md`
- Тесты с mock LLM (минимум 20)

### Phase 6 — LLM Tools (1 неделя)

**Цель:** новые tools для chat orchestrator'а.

**Tools:**
- `search_typical(config, query)` — поиск по карточкам
- `explain_object(config, object_full_name)` — карточка целиком
- `trace_calls(config, method_name, direction)` — граф вызовов
- `trace_movements(config, doc_or_reg, direction)` — движения
- `trace_data_flow(config, attribute)` — откуда берётся значение
- `compare_with_typical(config, client_channel, object)` — diff с типовой
- `list_typical_configurations()` — какие типовые загружены

**Артефакты:**
- `backend/app/knowledge/typical/tools.py`
- Wired в `loop.py _build_openai_tools`
- Async dispatch в `loop.py` (как search_its / search_bsp)
- Тесты (минимум 25)

### Phase 7 — Frontend UI (1 неделя)

**Артефакты:**
- Селектор типовой в Header (рядом с ChannelSelector): «Сравнить с УТ 11.5», «Сравнить с БП 3.0», ...
- `TypicalCard.tsx` — раскрывающаяся карточка объекта в chat-потоке
- `CompareWithTypicalCard.tsx` — diff с клиентским объектом
- vitest (минимум 15)

### Phase 8 — Run all 7 configurations

**По одной конфигурации:**

1. **УТ 11.5** (пилот, 2 недели) — обкатываем пайплайн
2. **БП 3.0** (1.5 недели)
3. **ЗУП 3.1** (1.5 недели)
4. **ERP 2.5** (2.5 недели) — самая крупная
5. **КА 2** (2 недели)
6. **УСО 2.5** (1.5 недели)
7. **Документооборот** (1 неделя)

**Acceptance per config:**
- Все объекты разобраны без ошибок (≥95% coverage)
- Карточки сгенерированы с валидацией (LLM judge)
- Графы построены полностью
- 10 проверочных запросов от пользователя дают релевантные ответы
- Privacy badge показывает количество загруженных карточек

## Зависимости

```
Phase 0 (Infrastructure)
  ↓
Phase 1 (BSL Parser) ──── Phase 2 (Query Parser) ──── Phase 3 (XML Parser)
                                  ↓
                          Phase 4 (Graph Builder)
                                  ↓
                          Phase 5 (Card Generator)
                                  ↓
                          Phase 6 (LLM Tools)
                                  ↓
                          Phase 7 (Frontend UI)
                                  ↓
                          Phase 8 (Run configurations)
```

Phases 1-3 могут идти параллельно (3 разных парсера, независимы друг от друга).
Phase 4 требует все три парсера готовыми.

## Риски

| Риск | Митигация |
|---|---|
| Tree-sitter BSL grammar неполная | Fallback на BSL LS subprocess (есть в tools/) |
| Защищённые модули типовых дают пробелы | Документируем в карточке "защищённый код, логика недоступна" |
| LLM-карточки галлюцинируют | LLM-judge валидация + grounding на AST + ITS standards |
| OpenAI токены съедают бюджет | Кеширование карточек (chunk_hash как в ИТС), переход на GPT-4o-mini |
| Версии конфигураций смещаются | Snapshot + fallback на ближайшую известную версию |
| Один прогон конфигурации > 1 дня | Resumable indexing (см. `typical_indexing_runs.progress_pct`) |

## Связь с другими milestones

- **M-K2 (closed):** ИТС + БСП индексы — типовые карточки могут ссылаться на ИТС/БСП через `its_links` / `bsp_links`
- **M-K3 (parallel):** граф клиентской базы + типовых — общий graph_storage. `compare_with_typical` использует оба графа.
- **M-K4:** нормативный layer — типовые карточки знают учётную политику и нормативку.
- **M-K5 (distribution):** локальный embedding позволит эмбедить и сам код (не только описания).
