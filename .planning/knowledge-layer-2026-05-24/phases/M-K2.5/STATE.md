---
milestone: M-K2.5
milestone_name: "Typical Configurations Knowledge"
status: in_progress
started_at: "2026-05-26T23:50:00Z"
last_updated: "2026-05-27T02:00:00Z"
branch: main (3 ветки merged FF)
parent_milestone: "M-K2 (closed 2026-05-26)"
parallel_with: "M-K3 (Relational + Behavioral)"
phases_total: 9      # 8 build + 1 SUMMARY
phases_done: 3       # 0/1/3 closed in one session
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
| M-K2.5.2 | Query Parser | pending | — | BSL Query Language → AST. Извлечение таблиц, полей, фильтров, ВТ, виртуальных таблиц |
| **M-K2.5.3** | **XML Metadata Parser** | ✅ DONE | `f96dde7` | xml.etree + namespace-агностично. 30 unit-тестов. xml_models (28 MetadataKind + DIRECTORY_TO_KIND маппинг + ModuleKind + MetadataAttribute/TabularSection/Form/Module/Object/Configuration). xml_parser: parse_configuration_xml / parse_metadata_file / discover_metadata_files / parse_configuration_tree. Document / Catalog / AccumulationRegister с Dimensions+Resources / CommonModule. Modules + Forms discovery через Ext/. BOM-aware. Graceful degradation |
| M-K2.5.4 | Semantic Graph Builder | pending | — | 6 графов через graph_storage (M-K3.17.1a). Вызовов / движений / ссылок / зависимостей данных / событий / ролей-RLS |
| M-K2.5.5 | Object Cards Generator | pending | — | LLM-генерация описательных карточек на русском. Эмбедятся описания, не код. ~$50-250 на конфигурацию через GPT-4o-mini |
| M-K2.5.6 | LLM Tools | pending | — | search_typical / explain_object / trace_calls / trace_movements / compare_with_typical. Интеграция в loop.py |
| M-K2.5.7 | Frontend UI | pending | — | Селектор типовой в чате, карточка объекта раскрывающаяся, кнопка «Сравнить с типовой» |
| M-K2.5.8 | Run all 7 configurations | pending | — | УТ 11.5 (пилот) → БП 3.0 → ЗУП 3.1 → ERP 2.5 → КА 2 → УСО 2.5 → Документооборот |

## Прогресс сессии 2026-05-26 → 2026-05-27

- 4/9 phases закрыты атомарными коммитами в одной сессии
- 6 коммитов в main: 5 phase + 1 pilot results
- 197 новых unit-тестов (82 + 39 + 30 + 46 + 1)
- 370 тестов в узком регрессионном наборе зелёные
- Зависимости pyproject.toml: +tree-sitter +tree-sitter-bsl

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
