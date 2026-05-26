---
milestone: M-K2.5
milestone_name: "Typical Configurations Knowledge"
status: in_progress
started_at: "2026-05-26T23:50:00Z"
last_updated: "2026-05-26T20:30:00Z"
branch: main (8 фаз merged FF)
parent_milestone: "M-K2 (closed 2026-05-26)"
parallel_with: "M-K3 (Relational + Behavioral)"
phases_total: 9      # 8 build + 1 SUMMARY
phases_done: 8       # 0-7 done + 8 частично (2/7 конфигураций)
phase_8_done: 2      # БП 3.0 + КА 2.5 — полные графы + карточки
phase_8_pending: 5   # УТ 11.5, ERP 2.5, ЗУП 3.1, УСО 2.5, Документооборот 3 — ждут снапшоты
---

# M-K2.5 Typical Configurations Knowledge — STATE

## Контекст

После закрытия M-K2 (Knowledge Foundation) пользователь поднял запрос:
бот должен **глубоко понимать логику типовых конфигураций 1С** — не просто
«есть документ Х», а «при проведении X происходит А → Б → В, регистры Y/Z
получают такие движения, потому что обработка проведения такая».

Это **новый параллельный milestone** между M-K2 и M-K3 — потому что
M-K3 (граф) и M-K2.5 (типовые) используют один фундамент graph_storage,
но независимы по контенту. Граф можно делать на синтетических данных,
типовые — отдельный пайплайн от .dt до карточек.

## Архитектурные решения (ADR-003)

См. `ADR-003-typical-configurations.md` рядом. Кратко:

1. **Snapshot-based, не live.** Разбираем фиксированные версии типовых.
   Клиент с расхождением версий получает fallback на ближайшую известную.
2. **Reserved channel namespaces** `_ut115_*`, `_erp25_*`, `_bp30_*` и т.д.
   Реальные MCP-каналы используют UUID v4, никогда не начинаются с `_`.
3. **Embedding только описаний** (LLM-сгенерированные карточки на русском),
   код хранится локально и в OpenAI **не уходит**. Юридически чисто.
4. **6 графов поверх одной типовой**: CALLS / CONTAINS / USES / WRITES_TO /
   READS_FROM / REFERENCES. Использует graph_storage из M-K3.17.1a.
5. **Парсим всё что выгружается DESIGNER'ом**. Защищённые модули
   технически выгружаются без тела — это техническое ограничение 1С,
   не нарушение лицензии.
6. **СКД отчёты глубоко** — весь XML (запросы + настройки + ресурсы +
   вычисляемые поля).

## Phases

| Phase | Subject | Status | Commit | Note |
|-------|---------|--------|--------|------|
| **M-K2.5.0** | **Infrastructure** | ✅ DONE | `7167744` | Migration v17 + registry + storage + ADR-003. 82 unit-теста. 7 namespace-префиксов для типовых, lifecycle PENDING→READY |
| **M-K2.5.1** | **BSL Parser AST** | ✅ DONE | `f751d7a` | tree-sitter-bsl 0.1.6 (community grammar 1c-syntax). 39 unit-тестов. bsl_models + bsl_ast: методы / параметры / Знач / default / директивы &НаСервере / регионы вложенные / doc-comment / customization marker (Доработка) / has_preprocessor_branches / graceful degradation на ошибках / UTF-8 + cp1251 fallback |
| **M-K2.5.2** | **Query Parser** | ✅ DONE | `0019745` | BSL Query Language → AST. Извлечение таблиц, полей, фильтров, ВТ, виртуальных таблиц |
| **M-K2.5.3** | **XML Metadata Parser** | ✅ DONE | `f96dde7` | xml.etree + namespace-агностично. 30 unit-тестов. xml_models (28 MetadataKind + DIRECTORY_TO_KIND маппинг + ModuleKind + MetadataAttribute/TabularSection/Form/Module/Object/Configuration). xml_parser: parse_configuration_xml / parse_metadata_file / discover_metadata_files / parse_configuration_tree. Document / Catalog / AccumulationRegister с Dimensions+Resources / CommonModule. Modules + Forms discovery через Ext/. BOM-aware. Graceful degradation |
| **M-K2.5.4** | **Semantic Graph Builder** | ✅ DONE | `40297f3` | graph_builder.py orchestrator (Phase A/B/C/D). 6 EdgeKind: CONTAINS/REFERENCES/CALLS/USES/WRITES_TO/READS_FROM. _ConfigIndex для быстрого резолва без повторного SELECT. Регулярки извлечения: _REFERENCE_TYPE_RE (8 типов ссылок RU+EN), _USES_RE (15 коллекций RU+EN), _DVIZHENIYA_RE, _SAME_MODULE_CALL_RE с _BSL_KEYWORDS фильтром, _CROSS_MODULE_CALL_RE для CommonModule.Метод. _normalize_query_table_qname для русский→английский префиксов. 55 unit-тестов (включая end-to-end на синтетике). Идемпотентность через graph_storage upsert. Pilot на БП 3.0 (200 BSL): 60326 nodes / 65091 edges / 791 sec |
| **M-K2.5.5** | **Object Cards Generator** | ✅ DONE (mock) | `a077035` | Migration v18 (`typical_object_cards`). card_models + card_storage + card_context + card_generator + prompt template v1. LLMCaller Protocol + MockLLMCaller (без расхода токенов). Идемпотентность через source_hash. 71 unit-тест. Pilot на БП 3.0 (10 объектов): 0.13 сек на генерацию, второй прогон 0 токенов (skip-hash работает). Бюджет полной БП через GPT-4o-mini: ~$2.40. Real LLM adapter — отдельным мини-коммитом с явным согласием пользователя |
| **M-K2.5.6** | **LLM Tools** | ✅ DONE | `44468bf` | `typical/tool.py` — 6 OpenAI function schemas + dispatcher: list_typical_configurations / search_typical_objects / explain_typical_object / trace_typical_calls / trace_typical_movements / compare_with_typical. Интеграция в `loop.py` (_build_openai_tools + run_chat_loop dispatch). System prompt обновлён — добавлены инструкции когда вызывать typical tools vs MCP. 23 unit-теста. compare_with_typical — заглушка (требует client graph из M-K3) |
| **M-K2.5.7** | **Frontend UI** | ✅ DONE | `a07ae28` | Backend: `GET /knowledge/typical/configurations` + `GET /knowledge/typical/{channel}/object/{qname}`. Frontend: `TypicalSelector.tsx` в Header (рядом с ChannelSelector), `TypicalObjectCard.tsx` (раскрывающаяся карточка в чат-потоке), `lib/api.ts` расширен (fetchTypicalConfigurations + fetchTypicalObject), `lib/storage.ts` с `setActiveTypicalChannelId`. 7 vitest тестов |
| **M-K2.5.8** | **Run all 7 configurations** | 🟡 PARTIAL (2/7) | pending commit | **Phase 8 закрыт частично:** БП 3.0.138.24 (11713 объектов, 166769 nodes, 314008 edges, 11713 карточек) + КА 2.5.25.92 (19683 объекта, 300232 nodes, 559287 edges, 19683 карточки). 100% покрытие обеих типовых. Время: КА **7:11**, БП **3:49** — 30-50× быстрее оценки благодаря оптимизации `commit=False + RETURNING + WAL + batch`. **5/7 типовых ждут снапшоты:** УТ 11.5, ERP 2.5, ЗУП 3.1, УСО 2.5, Документооборот 3 |
| M-K2.5.7 | Frontend UI | pending | — | Селектор типовой в чате, карточка объекта раскрывающаяся, кнопка «Сравнить с типовой» |
| M-K2.5.8 | Run all 7 configurations | pending | — | УТ 11.5 (пилот) → БП 3.0 → ЗУП 3.1 → ERP 2.5 → КА 2 → УСО 2.5 → Документооборот |

## Прогресс сессии 2026-05-26 → 2026-05-27

- **8/9 phases закрыты** атомарными коммитами (5 в этой сессии: 4/5/6/7/perf + Phase 8 частично)
- Все коммиты merged в main FF
- 346+ новых unit-тестов нарастающим итогом (82 + 39 + 30 + 46 + 55 + 71 + 23) + 7 vitest
- 347 typical/* теста + 46 graph_storage — все зелёные
- Зависимости pyproject.toml: +tree-sitter +tree-sitter-bsl
- **Полные графы 2 типовых в БД:**
  - КА 2.5.25.92: 300 232 nodes / 559 287 edges / 19 683 карточек (7:11)
  - БП 3.0.138.24: 166 769 nodes / 314 008 edges / 11 713 карточек (3:49)
- 6 LLM tools в orchestrator работают с реальными графами
- Frontend TypicalSelector в Header + TypicalObjectCard готов к рендерингу

## Пилотные прогоны на реальных типовых

| # | Конфигурация | Источник | channel_id | Время | Объектов | BSL мет. | Запросов |
|---|---|---|---|---|---|---|---|
| 1 | **КА 2.5.25.92** | DemoARAutomation202 | `_ka2_25_92` | 4:42 | 15 162 | 652 044 | 44 564 |
| 2 | **БП 3.0.138.24** | Accounting | `_bp30_138_24` | 2:30 | 8 525 | 412 539 | 17 962 |

**Не сработали (нужны creds):** ARAutomation2011 (рабочая КА 2),
Enterprise20 (рабочая ERP). Демо-баз ЗУП / УСО / Документооборот в
системе нет — нужны от пользователя.

Подробности — `PILOT-KA2-RESULTS.md` и `PILOT-BP30-RESULTS.md` рядом.

## Известное состояние окружения (обновлено 2026-05-27 00:30)

**Найдены 18+ зарегистрированных баз 1С** в `ibases.v8i`. Из них:

### Файловые (потенциально пилотные)

| База | Путь | Что это | Версия |
|---|---|---|---|
| Бухгалтерия предприятия | `C:\Users\Khvorostov\Documents\1C\Accounting` | БП 3.0 / иной? | проверить |
| ERP Управление предприятием 2 | `C:\Users\Khvorostov\Documents\1C\Enterprise20` | ERP 2.x | проверить |
| Комплексная автоматизация 2 (демо) | `C:\Users\Khvorostov\Documents\1C\DemoARAutomation201` | КА 2.x демо | проверить |
| КА 2 (демо) новый релиз | `C:\Users\Khvorostov\Documents\1C\DemoARAutomation202` | КА 2.x более свежий | проверить |
| Комплексная автоматизация 2 | `C:\Users\Khvorostov\Documents\1C\ARAutomation2011` | КА 2 рабочая | проверить |
| КА (Генпоставка) | `C:\Users\Khvorostov\Documents\1C\ARAutomation20` | КА доработанная | клиент |
| КА ДАМП 128 | `C:\Users\Khvorostov\Documents\1C\ARAutomation2013` | КА снапшот | клиент |
| InfoBase5 (Русский Транзит) | `C:\Users\Khvorostov\Documents\InfoBase5` | УТ + Русский Транзит CFE | 8.3.27 |
| УТ СД ГРУПП | `C:\Users\Khvorostov\Documents\InfoBase9` | УТ клиент | клиент |
| БУХА СД ГРУПП | `C:\Users\Khvorostov\Documents\InfoBase8` | БП клиент | клиент |
| Кубань логистик | `C:\Users\Khvorostov\Documents\InfoBase7` | сквозной клиент | клиент |
| Мегаполис | `C:\Users\Khvorostov\Documents\1C\AccountingBase1` | БП клиент | клиент |

### Серверные базы (через cluster IS-SRV1C-02, требуют DESIGNER на сервере)

- `atis_erp_demo` — ЕРП управление холдингом демо
- `base_2` — БУХА (8.3.24.1691)
- `kh_ip` — БП Кран хорс (8.3.24.1691)
- `erp_copy_xn` — АТИСС ERP (8.3.25.1286)
- `UTCOPY` — АЛРОКС-ЮГ УТ
- `kh_ka` — Кран Хорс КА (8.3.24.1691)
- `trade_ka24` — Трейд КА (8.3.27.1936)
- `trade_ka` — Трейд Новая (8.3.27.1688)
- `ut_rt_copy` — копия УТ Русского Транзита (8.3.27)
- `infocom` / `infocom_ut` — ИНФОКОМ

### Что ещё не найдено

- **ЗУП 3.1** — отдельной зарегистрированной базы нет
- **УСО 2.5** — нет
- **Документооборот 3** — есть серверная `DocMng` (8.3.20.2290, старая)
- **Чистые типовые без доработок** — все базы либо клиентские (с CFE), либо
  демо неизвестной свежести

### Выводы для пилота

1. **InfoBase5 (Русский Транзит)** — самая удобная для первого пилота:
   путь известен, креды Администратор/123, платформа 8.3.27.1989,
   DumpConfigToFiles уже отработан (deploy-changed.ps1 паттерн).
   После пилота можно будет извлечь именно типовую УТ из неё через
   diff CFE и base config.

2. Для **чистых типовых** ЗУП/УСО/Документооборот — нужно либо:
   - Развернуть `*_demo.dt` из дистрибутивов 1С (партнёрский кабинет)
   - Создать новую пустую базу из шаблона на release.1c.ru

3. Phases 0-4 строятся независимо от наличия конкретной базы — Phase 0
   уже закрыта инфраструктурой, Phases 1-3 пишут парсеры, тестируются
   на синтетических BSL/XML fixtures.

## Календарь (оценка)

- **Phase 0 (Infrastructure):** 1 день — этой сессией.
- **Phase 1 (BSL Parser AST):** 1.5 недели.
- **Phase 2 (Query Parser):** 1 неделя.
- **Phase 3 (XML Metadata Parser):** 1 неделя.
- **Phase 4 (Semantic Graph Builder):** 2 недели.
- **Phase 5 (Object Cards):** 2 недели + LLM-токены.
- **Phase 6 (LLM Tools):** 1 неделя.
- **Phase 7 (Frontend UI):** 1 неделя.
- **Phase 8 (Run всех 7 конфигураций):** по 1.5-2.5 недели на каждую.

**Итого infrastructure + parsers + graph + cards + tools + UI:** ~10 недель.
**Итого + прогон 7 конфигураций:** ~18-22 недели = 4.5-5.5 месяцев.

Идём параллельно с M-K3, который продолжается с M-K3.17.1b.

## Acceptance criteria для Phase 0 (сейчас)

- [ ] `.planning/knowledge-layer-2026-05-24/phases/M-K2.5/` создан со STATE.md, M-K2.5-PLAN.md, ADR-003-typical-configurations.md
- [ ] Migration v17: `typical_configurations` + `typical_indexing_runs` таблицы с индексами и FK CASCADE
- [ ] `backend/app/knowledge/typical/` package: `__init__.py`, `registry.py`, `storage.py`
- [ ] `TypicalConfigKind` enum + `RESERVED_PREFIXES` + `reserved_channel_id()` helper
- [ ] CRUD operations: `create_configuration`, `get_by_channel`, `list_configurations`, `update_status`, `create_run`, `update_run_progress`
- [ ] Тесты для миграции v17 + registry + storage (минимум 25 unit тестов)
- [ ] Полный backend pytest зелёный
- [ ] Atomic commit на ветке `feature/m-k2.5-infrastructure`
- [ ] FF merge в main + push (по команде)

## Что НЕ в Phase 0 (откладывается)

- DESIGNER загрузчик `.dt → выгрузка XML` (Phase 1, требует BSL parser ready)
- LLM карточки (Phase 5)
- Frontend UI (Phase 7)
- Прогон реальных конфигураций (Phase 8)

Phase 0 — чистый фундамент: миграции БД + python модули с тестами,
независимо от наличия .dt файлов.

## История

- **2026-05-26 23:50** — STATE создан, Phase 0 in_progress.
