# Идеи развития «1С Аналитик» — из стека Cloude_PR (2026-05-21)

> Что можно перенести/применить из нашего общего 1С-стека и недавнего deep research'а в проект «1С Аналитик».
> Источник: `.claude/research/1c-knowledge-roadmap-2026-05-21/`, `.claude/research/ecosystem-deep-revision-2026-05-21/`, и инструменты в `C:/CLOUDE_PR/tools/`.
>
> **Соблюдены ограничения проекта** (см. `.claude/rules/design-bans.md`, `CLAUDE.md`):
> - НЕТ предложений про work-modes / Object-IDE / Workflow editor / AI right-rail (банные итерации v0/v0b)
> - НЕТ предложений про Inter font, светлую тему как default, mobile UI
> - НЕТ предложений про Ollama / local LLM (отвергнуто 2026-05-08)
> - Учтены: brand Stencil Signal `#FF6A3D`, Plex Mono lockup, desktop ≥ 1280px

---

## TL;DR — топ-5 идей с максимальным ROI

| # | Идея | Где применить | Фаза проекта | Gain |
|---|---|---|---|---|
| 1 | **БСП-corpus для RAG** (Phase 10) — индексировать `tools/ssl_3_2/`+`ssl_3_1/` (CC-BY-4.0) | Phase 10 sqlite-vec | M5+ | Качество ответов про БСП subsystems +40% |
| 2 | **Read-only MCP как default-канал** для prod-баз клиентов через feenlace/mcp-1c v1.6.6 | Backend MCP клиент | M5 | Безопасность для боевых баз +100% |
| 3 | **System prompts из 25 шаблонов petr-panda** + OnesTemplates few-shot | Orchestrator | M4-5 | Стабильность типовых запросов +30% |
| 4 | **Configuration-detection** (УТ/ERP/КА/БГУ) → tailored system prompt | Orchestrator | M5 | Точность ответов по типовым +25% |
| 5 | **Citations cards** — ссылки в ответе LLM на конкретные строки БСП/типового | Phase 11+ карточки | M5-6 | Анти-галлюцинация, доверие +50% |

---

## Структура документа

1. RAG / Phase 10 — что взять из bsl-atlas, БСП, типовых
2. MCP-стратегия — read-only канал, fallback, multi-channel
3. Промпт-инжиниринг — корпуса, system prompts, few-shot
4. Multi-config awareness — определение и адаптация под УТ/ERP/КА/БГУ
5. Карточки — новые типы из инфраструктуры
6. Качество ответов — eval, citations, anti-hallucination
7. Безопасность — анти-PII, audit log, read-only mode
8. DevX — orobra/superpowers, /goal, Agent View
9. Knowledge base offline — bundled docs для desktop
10. Eval harness — regression test set на реальных кейсах

---

## 1. RAG / Phase 10 — конкретный план

Текущий стек проекта (`.claude/rules/tech-stack.md`): **sqlite-vec + OpenAI text-embedding-3-small**. Это уже принято — не предлагаю менять основу. Но есть улучшения по содержимому corpus'а.

### 1.1 БСП исходники как первичный corpus

Уже склонированы в общий стек: `C:/CLOUDE_PR/tools/ssl_3_2/` (БСП 3.2, актуальная) и `tools/ssl_3_1/` (3.1, для клиентов на УТ 11.5 на старой БСП). **Лицензия CC-BY-4.0** — легально использовать с атрибуцией.

**Что даёт:**
- Полный исходный код 60+ подсистем БСП (ДлительныеОперации, БезопасноеХранилище, ВерсионированиеОбъектов, УправлениеДоступом, ЭлектроннаяПодпись и др.)
- ~50 000 строк кода с комментариями на русском
- Готовые паттерны вызовов БСП-методов

**Как применить:**
1. Скопировать relevant модули из `tools/ssl_3_*/src/` в `backend/data/knowledge/bsp/`
2. Chunking по процедурам/функциям (можно через `bsl-language-server` AST или простой regex split по `Процедура/Функция`)
3. Индексация в sqlite-vec через OpenAI text-embedding-3-small
4. Источник в ответе: `bsp:3.2:Документооборот:Server.bsl:ЗарегистрироватьВерсию`

**Acceptance:** «как правильно сохранить вложение к объекту?» → ответ со ссылкой на конкретный модуль БСП.

**Атрибуция:** добавить в About / README: «Includes БСП 3.1/3.2 from github.com/1c-syntax under CC-BY-4.0».

### 1.2 OnesTemplates как seed для few-shot

`C:/CLOUDE_PR/tools/OnesTemplates/` — production BSL сниппеты по стандартам ИТС/EDT/Sonar.

**Как применить:**
- Парсить шаблоны → seed examples для system prompt
- Использовать как «gold standard» при генерации кода в ответах
- Для CodeCard: «вот как пишут по стандартам ИТС»

### 1.3 Платформенная справка `shcntx_ru.hbk`

У пользователя есть локально (`C:/Program Files/1cv8/8.3.27.1644/bin/`). Можно либо:
- (a) Использовать существующий `bsl-context` MCP (уже работает у Никиты в Транзите) — добавить как опциональный MCP-канал
- (b) Извлечь в markdown через `tools/platform-context-exporter/` (требует gradle build с Maven SNAPSHOT — пока заблокировано)
- (c) Bundle с installer'ом если есть лицензионная возможность (платформенная справка не открытая)

**Рекомендация:** (a) — наименьший риск, плагин уже работает у автора, добавить как опциональное подключение.

### 1.4 Альтернативный embedding для русского (опц., не для MVP)

OpenAI `text-embedding-3-small` неплохо работает с русским, но **Qwen3-Embedding-4B** даёт лучшее качество на ruMTEB (см. наш research). Это **не сейчас** — заранее принятый pivot 2026-05-08 говорит «cloud-only, без Ollama». Но если в будущем будет on-prem версия — рассмотреть Qwen3 через cloud-API (Qwen DashScope OpenAI-compatible).

### 1.5 Architecture для RAG (Phase 10)

```
┌─ FastAPI orchestrator
│  ├─ Hybrid retrieval:
│  │   1. FTS5 (BM25) по corpus'у + код базы клиента
│  │   2. sqlite-vec (semantic) по тому же corpus'у
│  │   3. RRF merge top-K результатов
│  ├─ Cross-encoder rerank (опц. для топ-N)
│  └─ Context window injection в LLM
```

**Источник архитектуры:** наш research отчёт `RAG/embeddings/semantic search для 1С` — Habr статья про documents1c + metadata1c (раздельные RAG для документации vs метаданных).

**Идея:** **2 раздельных RAG-индекса в проекте:**
1. `bsp_index` — корпус БСП исходников + платформенная справка (общий для всех клиентов)
2. `client_index` — корпус кода базы клиента (отдельный per-channel, инкрементальный)

Это решает проблему «БСП не должна замусоривать поиск по клиенту».

---

## 2. MCP-стратегия

### 2.1 Read-only MCP как default-канал

**Проблема:** текущий 1С MCP Toolkit v1.7.0 даёт `execute_code` — write-capable. Для prod-баз клиентов это **риск** (АРМ-кейс с дублём контрагента в Транзите показал — даже опытный разработчик может ввести base в плохое состояние).

**Решение:** добавить второй MCP-канал `feenlace/mcp-1c` (v1.6.6 уже скачана в `tools/`) — **read-only by design**:
- 9 tools: get_metadata_tree, get_object_structure, get_form_structure, search_code (BM25+synonyms), execute_query (SELECT only!), validate_query, get_event_log, bsl_syntax_help
- Write-операции **физически невозможны**
- Bin-only установка, не требует переустановки EPF при обновлении версии

**UI:** в Settings → Connections добавить флаг «Mode: read-only / read-write». Default = read-only для всех новых подключений.

**Acceptance:** аналитик подключается к prod-базе клиента → не может случайно изменить данные.

### 2.2 REST API fallback через `bia-technologies/rat`

**Проблема:** 1С MCP Toolkit требует ручного запуска EPF в тонком клиенте на каждой базе. Это **friction** для аналитика, работающего с 5+ базами клиентов параллельно.

**Решение:** `tools/rat/` (Remote API for Testing) — REST API сервис, публикуемый в IIS на сервере 1С. Аналитик подключается через стандартный HTTP без запуска EPF.

**Trade-off:** требует deployment на стороне клиента (IIS + публикация). Не для MVP, но для enterprise-варианта установки.

### 2.3 Multi-channel улучшения

В проекте уже есть Channel Selector. Идеи расширения:
- **Channel health probe** — периодический ping всех каналов, индикатор статуса в Sidebar (зелёный/жёлтый/красный точка рядом с именем)
- **Auto-discovery** — backend сканирует localhost:6000-6010 range, находит активные MCP-сервера, предлагает добавить
- **Channel tagging** — `prod / staging / dev` теги для предотвращения случайных execute на prod
- **Channel switch confirmation** — для prod-каналов confirm dialog при первом execute_code

---

## 3. Промпт-инжиниринг

### 3.1 Использовать 25 шаблонов petr-panda как seed

В стеке есть `.claude/skills/1c-prompt-library/SKILL.md` — 25 готовых промпт-шаблонов под типовые задачи 1С-аналитика (запросы, СКД, регексы, тесты, формы, RLS, HTTP, XDTO).

**Применение в orchestrator:**
- Парсить вопрос аналитика → detect категорию (запрос/СКД/тест/...) через regex или маленький LLM-call
- Подставлять соответствующий шаблон в system prompt LLM
- Шаблоны уже учитывают: префиксы, A1-A11 антипаттерны, ВТ_-конвенции

**Acceptance:** «дай мне регулярку для ИНН + код проверки» → ответ использует структуру шаблона P12, без галлюцинаций.

### 3.2 Configuration-specific system prompts

Сейчас orchestrator работает с одним общим system prompt. Идея — **set prompts per configuration:**
- `prompts/УТ-11.5.md` — знание архитектуры подсистем, ключевых регистров (ТоварыНаСкладах, ВзаиморасчетыСКонтрагентами), правила проведения
- `prompts/ERP-2.5.md` — аналогично для ERP (УСО, Финансы, Производство)
- `prompts/КА-2.5.md`, `prompts/БГУ-3.0.md` — для других

**Detection:**
- При первом подключении — `get_metadata_tree` → проверка наличия ключевых объектов (например `Документ.ОтчетПроизводстваЗаСмену` = ERP, `Документ.ОперацияБух` = БГУ)
- Сохранить в SQLite per-channel
- Подгружать соответствующий prompt в orchestrator

**Источник идеи:** наш research D показал — нет публичных «УТ 11.5 архитектура подсистем» cheatsheet. Можно собрать internal по своему опыту Транзита.

### 3.3 Few-shot examples из OnesTemplates

В system prompt добавить 2-3 примера из OnesTemplates: «вот как пишут код по стандартам ИТС, придерживайся этого стиля».

---

## 4. Multi-config awareness

### 4.1 Configuration detector (новый backend module)

```python
# backend/app/services/config_detector.py
async def detect_configuration(mcp_client) -> ConfigType:
    """Определяет тип конфигурации по метаданным."""
    metadata = await mcp_client.call("get_metadata_tree", {"max_depth": 2})
    
    signatures = {
        "УТ-11.5": ["Документ.РеализацияТоваровУслуг", "Регистр.ТоварыНаСкладах"],
        "ERP-2.5": ["Документ.ОтчетПроизводстваЗаСмену", "Подсистема.УчетПроизводства"],
        "КА-2.5": [...],
        "БГУ-3.0": ["Документ.ОперацияБух", "ПланСчетов.Хозрасчетный"],
        "ЗУП-3.1": ["Документ.НачислениеЗарплаты", ...],
        "УСО-2.5": ["Документ.СтроительныйУчет", ...],
    }
    
    for config_type, sig in signatures.items():
        if all(s in metadata.objects for s in sig):
            return config_type
    
    return "Unknown"
```

**UI:** в карточке Channel в Sidebar показывать badge с типом конфигурации («УТ 11.5», «ERP 2.5»).

### 4.2 Configuration-specific cheatsheets (knowledge content)

`backend/data/knowledge/cheatsheets/`:
- `УТ-11.5.md` — таблица «где что лежит»: подсистемы, ключевые регистры, документы по цепочке закупки/продажи/склада
- `ERP-2.5.md` — аналогично

**Используется:** RAG retrieval → подкладывает в контекст когда аналитик задаёт config-specific вопрос.

**Источник:** Курсы-по-1С.рф «Схема проведения документов в УТ 11/ERP 2/КА 2» — единственный публичный источник схем (см. наш Research D).

### 4.3 БСП version detection

Дополнительно к типу конфы — версия БСП (3.1.x / 3.2.x). Через метаданные:
```python
bsp_version = await mcp.call("execute_query", {
    "query": "ВЫБРАТЬ * ИЗ Константа.ВерсияБиблиотекиСтандартныхПодсистем"
})
```

Используется для выбора corpus'а (ssl_3_1 vs ssl_3_2) при RAG-поиске.

---

## 5. Новые карточки

Проект уже имеет 6 типов: Table / Object / Log / Metric / References / Code. Идеи дополнительных:

### 5.1 CitationCard — источник ответа

**Что:** небольшая inline-карточка под ответом LLM, показывающая на основе чего был дан ответ.

**Структура:**
```
┌─────────────────────────────────────────┐
│ Источники:                              │
│ • БСП 3.2 → ДлительныеОперации (lines 47-89)
│ • Платформенная справка → HTTPСоединение
│ • Метаданные клиента → Документ.РеализацияТоваровУслуг
└─────────────────────────────────────────┘
```

**Реализация:** RAG retrieval возвращает chunks → backend агрегирует источники → отдаёт фронту как `card: { type: "citations", sources: [...] }`.

**Эффект:** анти-галлюцинация, доверие. Самая важная карточка для analiстов которые проверяют ответы.

### 5.2 WorkflowCard — диаграмма проведения документа

**Что:** Mermaid-диаграмма lifecycle документа (ПередЗаписью → ОбработкаПроведения → Движения → Подписки).

**Когда показывать:** на вопросы «как проводится X», «что происходит при записи X».

**Реализация:** `mermaid.js` уже совместим с Next.js. Backend генерирует mermaid-код через LLM с подсказкой схемы.

### 5.3 GraphCard — граф зависимостей

**Что:** мини-визуализация связей между объектами конфигурации (D3.js или vis-network).

**Когда:** «что использует Документ.X», «что вызывает функцию Y».

**Реализация:** требует `mdclasses` + `bsl-graph` (наш стек). Не для MVP, но в M6+ как «pro feature».

### 5.4 SchemaCard — схема таблицы

**Что:** структура объекта (реквизиты + типы) в визуальном виде (как DBML или dbdiagram.io).

**Когда:** «какие поля у Документ.X».

**Уже есть:** ObjectCard покрывает базовую функциональность. SchemaCard = визуальная версия.

### 5.5 ComparisonCard — diff двух объектов/конфигураций

**Что:** side-by-side сравнение (типового vs кастомного, версии до vs после).

**Когда:** «что добавили в расширение по сравнению с типовой», «что изменилось между релизами».

**Реализация:** `monaco-diff-editor` (уже в зависимостях если используется Monaco для CodeCard).

---

## 6. Качество ответов

### 6.1 Eval framework на pre-recorded прогонах

Из нашего research'а (Research A — Anthropic skills): eval-планирование critical для AI-приложений.

**Что:**
- Набор `data/evals/` с golden questions:
  - 50 типичных вопросов аналитика (по 10 для УТ, ERP, КА, БГУ, ЗУП)
  - Каждый: question + expected_topics + expected_sources
- Regression-прогоны через CI: на каждый PR — прогон evals, сравнение с предыдущим
- Score: BLEU / semantic similarity к expected_topics + presence of expected_sources

**Зачем:** не допустить регрессий качества при изменении prompts / orchestrator'а.

### 6.2 Source citations (см. §5.1)

Каждый ответ LLM должен ссылаться на источник. Это **anti-hallucination** механизм.

**Реализация:**
- В system prompt: «Указывай источники как `[bsp:3.2:ИмяМодуля:строка]` или `[client:Документ.X:реквизит]`»
- Backend post-processing: парсит ссылки → формирует CitationCard
- LLM без source = warning в UI

### 6.3 Confidence scoring

LLM показывает свою уверенность в ответе. Идеи:
- При уверенности < 70% — карточка `LowConfidenceCard` с предложением «уточните вопрос»
- При полном незнании — честно «не знаю + почему» (правило брутальной честности из session-contract.md)

---

## 7. Безопасность для боевых баз

### 7.1 Auto-anonymization improvements

Текущая анонимизация — toggle в Header. Идеи усиления:

**Regex-based PII detection:** автоматический preview перед отправкой в LLM:
- ИНН (10-12 цифр)
- СНИЛС (XXX-XXX-XXX XX)
- Email
- Номер договора
- Имя сотрудника (через словарь типичных русских имён)

**UI:** при наборе вопроса — inline-маркеры жёлтым «найдено PII: 3 ИНН». Click → preview анонимизированной версии.

**Source:** rules/1c имеют логику в `1c-logging-strategy.md` § «Что НЕ должно идти в лог».

### 7.2 Audit log на стороне приложения

Сейчас все действия идут через MCP. Логирование на стороне приложения:
- Каждый `execute_query/execute_code` → запись в `audit_log` SQLite таблицу
- Поля: timestamp, channel, user_question, tool_call_args, result_summary, hash_of_data
- UI: Settings → Audit Log — последние 100 операций, экспорт в CSV

**Зачем:** compliance, post-mortem багов, доказательство «я этого не делал» при инциденте.

### 7.3 Two-step confirm для опасных операций

Сейчас есть Confirm Dialog для execute_code. Расширить:
- Detect опасных паттернов в коде до confirm: `Удалить()`, `Записать()`, `НачатьТранзакцию()` без commit/rollback
- Показывать в Confirm: «Этот код может: удалить объекты / записать данные / открыть транзакцию»

---

## 8. DevX — обновления стека из нашего research

### 8.1 obra/superpowers v5.1 review pipeline

В стеке Cloude_PR обновлены obra-* skills до v5.1 — review-loops в 50x быстрее (30 сек вместо 25 мин).

**Применить в проекте:** при коммитах в analyst-workspace-design — использовать `/awd-quality-gate` (уже есть) + дополнить obra-стилем self-review checklists вместо параллельных агентов.

### 8.2 `/goal` для автономного workflow

Claude Code v2.1.146 даёт `/goal <условие>` — автономная работа до выполнения условия.

**Применить:**
- `/goal все vitest зелёные + build clean + Playwright проходит` — для end-of-day проверки
- `/goal Phase 11.4 acceptance criteria выполнены` — для milestone closure

### 8.3 Agent View для multi-task аналитики

В Claude Code появилась команда `claude agents` — единый дашборд параллельных сессий. Полезно при работе над несколькими фазами одновременно (Phase 11 + STACK + SESSIONS).

### 8.4 Hooks API расширения

Из нашего research'а: новые `terminalSequence`, `effort.level`, `duration_ms`, `background_tasks` в Stop/SubagentStop hooks.

**Применить:** на pre-commit hook — `terminalSequence` для desktop notification «vitest passed/failed».

---

## 9. Knowledge base offline (Bundled docs)

### 9.1 Bundled БСП subset

Размер `tools/ssl_3_2/` — ~50 MB исходников. Это **значительно** для Electron installer (сейчас 105.9 MB). Идеи:

**Вариант A:** включить **только metadata** БСП — список subsystems + signatures экспортных методов (~1 MB), полные исходники подгружать on-demand по сети из publicly hosted версии (CDN или GitHub raw).

**Вариант B:** включить только **самые часто используемые** subsystems: ДлительныеОперации, БезопасноеХранилище, ЭлектроннаяПодпись, ВерсионированиеОбъектов (~5 MB).

**Вариант C:** offline-режим как опция: «Загрузить знания БСП для offline» в Settings → ещё 50 MB.

**Рекомендация:** B по умолчанию, C опция.

### 9.2 Bundled 25 prompt templates

`.claude/skills/1c-prompt-library/SKILL.md` — copy в `backend/data/prompts/library.json` (~50 KB). Доступно в UI: Settings → Prompt Library.

### 9.3 Bundled cheatsheets

Cheatsheets per configuration (УТ/ERP/КА/БГУ) — 5-10 KB каждый. Включить все.

---

## 10. Eval harness на реальных кейсах Транзита

В Cloude_PR есть memory про реальные баги/фиксы Транзита — `russian_transit_arm_full_audit_2026_05_20.md`, `russian_transit_csv_loader_v4_v9.md`, `russian_transit_blocker_fix_2026_05_01.md` и др.

**Идея:** превратить в **regression eval set**:

```json
// data/evals/transit-real-cases.json
[
  {
    "id": "arm-empty-lists-2026-05-20",
    "question": "В АРМ Транзита пустые списки документов — что могло сломаться?",
    "expected_topics": ["дубликаты контрагентов", "разрешённые в запросах", "RLS"],
    "expected_tools": ["execute_query", "get_metadata"],
    "expected_sources": ["Справочник.Контрагенты"],
    "ground_truth": "Был дубль контрагента — К1 с 608 ОПП и К2 с 0 ОПП. Пользователь интуитивно выбирал К2. Объединение через ОбщегоНазначения.ЗаменитьСсылки"
  },
  {
    "id": "csv-loader-server-base",
    "question": "ЗагрузкаРееструТД падает на серверной базе ut_rt_copy — причина?",
    "expected_topics": ["временный файл", "ПолучитьИзВременногоХранилища"],
    ...
  }
]
```

**CI прогон:** `pytest tests/evals/test_regression.py` — на каждом PR.

**Эффект:** уверенность что новые prompts/orchestrator не ломают понимание реальных кейсов.

---

## 11. Что НЕ предлагаю (и почему)

| Идея | Почему отказ |
|---|---|
| Локальный Ollama embedding | Pivot 2026-05-08: cloud-only. Не возвращаться |
| Object-IDE / tree метаданных слева | Ban v0 mistake |
| Vector store через ChromaDB / Qdrant | Уже выбран sqlite-vec (Phase 10) |
| `bsl-atlas` MCP как replacement для 1С MCP Toolkit | Different scope — atlas индексирует выгрузку, проект работает с live базой через Toolkit. Не заменяют друг друга |
| Bundled зеркало ИТС | Закрытая подписка 1С, лицензионно нельзя |
| Бэкап типовой УТ в репо | Лицензия 1С запрещает |
| 1c-templates-mcp как замена prompt library | Docker, лишняя зависимость для desktop приложения. Bundle promtов в SQLite проще |
| Tree-sitter BSL grammar | Никто в community не сделал; самим — 2+ недели; не критично |
| AI right-rail / Workflow editor | Ban v0/v0b |

---

## 12. Карта приоритетов / phasing

### Сейчас (Phase 11 / v1.2.0 closure)
- **Не трогать** — закрываем design v2 import + smoke, не размывать scope

### M6 (после v1.2.0)
- **Read-only MCP как default** (§2.1) — security wins
- **25 шаблонов petr-panda в bundled prompts** (§3.1, §9.2)
- **Configuration detector** (§4.1) — backend module + UI badge
- **CitationCard** (§5.1) — anti-hallucination

### M7 (Phase 10 RAG)
- **БСП corpus как первичный datasource** (§1.1)
- **2 раздельных RAG-индекса** bsp + client (§1.5)
- **OnesTemplates few-shot** (§3.3)

### M8 (DevX / quality)
- **Eval harness** (§10) — regression test set на Транзит-кейсах
- **Source citations** в LLM ответах (§6.2)
- **Audit log** (§7.2)

### M9+ (Pro features)
- **WorkflowCard** Mermaid (§5.2)
- **GraphCard** через mdclasses+bsl-graph (§5.3)
- **REST API fallback** через rat (§2.2) — для enterprise
- **Bundled offline knowledge** (§9)

---

## 13. Связь с текущим ROADMAP проекта

ROADMAP.md содержит M1-M4. Эти идеи — для M5+ (после Production Ready). Не блокируют закрытие текущих milestone'ов.

`.planning/STATE.md` показывает: M5 — Post-v1.1 Expansion (STACK + SESSIONS + LEARN + Design v2), Phase 11 in_progress (69%).

**Рекомендация:** этот документ — input для GSD `/gsd:new-milestone M6` когда Phase 11 закроется. Не пытаться запихнуть в текущую фазу.

---

## 14. Источники

### Из общего стека Cloude_PR
- `.claude/research/1c-knowledge-roadmap-2026-05-21/README.md` — 6 системных gaps в понимании 1С
- `.claude/research/1c-knowledge-roadmap-2026-05-21/APPLIED.md` — что применено (9 репо склонировано, 25 промптов, БСП Grep)
- `.claude/research/ecosystem-deep-revision-2026-05-21/README.md` — Phase 2 ecosystem revision
- `.claude/research/ecosystem-deep-revision-2026-05-17/` — baseline аудит

### Инструменты в `C:/CLOUDE_PR/tools/` (доступны прямо сейчас)
- `ssl_3_2/`, `ssl_3_1/` — БСП исходники (CC-BY-4.0)
- `OnesTemplates/` — production BSL сниппеты
- `bsl-atlas/` — Docker vector RAG (alt архитектура)
- `mcp-1c-windows-amd64.v1.6.6.exe` — read-only MCP (для прод-баз клиентов)
- `rat/` — REST API альтернатива MCP Toolkit
- `mdclasses/`, `bsl-graph/` — для GraphCard в будущем

### Внешние ссылки
- [1c-syntax/ssl_3_2 (БСП 3.2 CC-BY-4.0)](https://github.com/1c-syntax/ssl_3_2)
- [feenlace/mcp-1c v1.6.6](https://github.com/feenlace/mcp-1c)
- [Habr 1017498 — RAG documents1c + metadata1c](https://habr.com/ru/articles/1017498/) — архитектура раздельных RAG-индексов
- [Petr-Panda 25 промптов](https://petr-panda.ru/prompty-dlya-programmista-1s/)
- [Курсы-по-1С: схема проведения УТ/ERP/КА](https://xn----1-bedvffifm4g.xn--p1ai/articles/2017-09-07-documents-posting-scheme/)
- [matakov.com — секреты Claude Code](https://matakov.com/sekrety-produktivnoj-raboty-s-claude-code/)
- [bia-technologies/rat](https://github.com/bia-technologies/rat)

### Память (memory/)
- `russian_transit_arm_full_audit_2026_05_20.md` — кейс для eval'ов
- `russian_transit_csv_loader_v4_v9.md` — кейс для eval'ов
- `feedback_research_depth_before_judgment.md` — методология deep research
- `metr_deep_dive_2026_05_16.md` — паттерн исследования инструмента до вердикта

---

## 15. Не идеи, а напоминания

### Что уже доступно в проекте без внедрения
- `awd-claude-design-handoff` skill — для итераций UI через claude.ai/design
- `claude-code-bsl-lsp` плагин — BSL диагностика в редакторе (130+ правил)
- obra/superpowers v5.1 — review-pipeline 50x быстрее (в общем стеке)
- Все 25 промпт-шаблонов в `.claude/skills/1c-prompt-library/` (общий стек)

### Что точно НЕ изменилось из текущего проекта
- Brand Stencil — никаких изменений (Signal #FF6A3D, Plex Mono lockup)
- Запреты v0/v0b — без послаблений
- Tech stack lock (sqlite-vec для Phase 10, OpenAI-compat для LLM, MCP HTTP Streamable)
- Desktop-only ≥ 1280px
