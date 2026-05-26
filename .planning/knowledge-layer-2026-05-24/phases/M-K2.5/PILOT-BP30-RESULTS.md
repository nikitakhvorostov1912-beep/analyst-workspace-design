---
pilot: "БП 3.0.138.24 (Accounting)"
date: "2026-05-26"
duration_designer_s: 480     # ~8 минут DESIGNER /DumpConfigToFiles
duration_pipeline_s: 150     # ~2.5 минуты XML+BSL+Query
result: success
fatal_errors: 0
---

# Pilot Results — БП 3.0.138.24 (Бухгалтерия предприятия)

> Второй пилотный прогон. Цель — проверить парсеры на конфигурации с
> bookkeeping-focus (РегистрБухгалтерии). Validates что:
> 1. Парсеры различают разные семейства конфигураций
> 2. Performance не деградирует на разных типах объектов
> 3. Query parser корректно опознаёт ОборотыДтКт / ДвиженияССубконто

## Источник

| Параметр | Значение |
|---|---|
| Конфигурация | Бухгалтерия предприятия 3.0.138.24 |
| Vendor | Фирма «1С» |
| CompatibilityMode | Version8_3_17 (старее КА 2 — 8_3_27) |
| Каталог базы | `C:\Users\Khvorostov\Documents\1C\Accounting` |
| Snapshot | `data/typical-snapshots/bp30-accounting/` |
| channel_id | `_bp30_138_24` |

## Производительность

| Этап | Время | Темп |
|---|---|---|
| DESIGNER /DumpConfigToFiles | **8 минут** | 77 126 файлов |
| XML metadata parser | ~15 с | ~570 obj/sec |
| BSL parser | **104.9 с** | ~140 files/sec |
| Query parser | **27.7 с** | ~650 q/sec |
| **Полный pipeline** | **~2.5 минуты** | — |

## XML metadata (8 525 объектов)

| Тип | Кол-во |
|---|---:|
| Document | 345 |
| Catalog | 563 |
| AccumulationRegister | 102 |
| InformationRegister | 1004 |
| AccountingRegister | 1 |
| CalculationRegister | 0 |
| **ChartOfAccounts** | **1** ✅ (специфика БП) |
| ChartOfCalculationTypes | 3 |
| ChartOfCharacteristicTypes | 8 |
| CommonModule | 2639 |
| CommonForm | 354 |
| Report | 612 |
| DataProcessor | 307 |
| Enum | 957 |
| Constant | 575 |
| BusinessProcess | 7 |
| Task | 1 |
| Sequence | 5 |
| EventSubscription | 372 |
| ScheduledJob | 124 |
| Subsystem | 49 |
| ExchangePlan | 26 |
| DocumentJournal | 30 |

## BSL parser (14 725 модулей)

- **412 539 методов**, из них **144 264 экспорт** (35%)
- 51 949 регионов
- Parse errors: 5 837 (40%) — все на multi-line строках с `|`
- **Fatal errors: 0** ✅

## Query parser

- **17 962 запросов** в тел методов
- 11 293 физических table references
- **2 155 виртуальных таблиц references**

### Virtual table kinds

| Kind | Кол-во | Тип регистра |
|---|---:|---|
| Обороты | 666 | РегистрНакопления |
| СрезПоследних | 618 | РегистрСведений |
| Остатки | 607 | РегистрНакопления |
| ОстаткиИОбороты | 115 | РегистрНакопления |
| СрезПервых | 106 | РегистрСведений |
| **ОборотыДтКт** | **40** | **РегистрБухгалтерии** |
| ДанныеГрафика | 3 | РегистрРасчета |

### Register types — **bookkeeping-focus подтверждён**

| Тип | Кол-во |
|---|---:|
| **РегистрБухгалтерии** | **829** ← главный фокус БП |
| РегистрСведений | 705 |
| РегистрНакопления | 621 |

В КА 2.5.25.92 наоборот: РегистрНакопления 2031 > РегистрСведений 2425 > РегистрБухгалтерии 498.

## Сравнение с КА 2

| Метрика | БП 3.0.138.24 | КА 2.5.25.92 | Δ |
|---|---:|---:|---|
| Total objects | 8 525 | 15 162 | -44% |
| BSL methods | 412 539 | 652 044 | -37% |
| Queries | 17 962 | 44 564 | -60% |
| Virtual tables | 2 155 | 4 971 | -57% |
| **Регистр.Бухгалтерии refs** | **829** | 498 | **+66%** ✅ |
| Регистр.Накопления refs | 621 | 2031 | -69% |
| Pipeline time | 2.5 мин | 4:42 | -47% |

## Что подтверждено

1. ✅ **Парсеры корректно различают конфигурации.** БП фокус на двойной
   записи (ChartOfAccounts × 1 + РегистрБухгалтерии × 829 + ОборотыДтКт ×
   40 + Sequence × 5) — это финансовый учёт.
2. ✅ **Performance линейная** — БП в 2 раза меньше КА 2, pipeline в 2
   раза быстрее.
3. ✅ **0 fatal errors на 14 725 модулях** — парсеры устойчивы.
4. ✅ **CompatibilityMode Version8_3_17 не мешает** — старый формат XML
   обрабатывается так же как 8_3_27.

## Что не получилось в этой сессии

- **ARAutomation2011** (рабочая КА 2, 4.3 GB) — DESIGNER не открыл,
  нужны другие creds (не Admin / пусто). У рабочих конфигураций обычно
  свой пользователь с паролем.
- **Enterprise20** (рабочая ERP) — аналогично, не демо.
- **DemoARAutomation201** — был запущен по ошибке (вторая версия КА 2
  не нужна — у нас уже DemoARAutomation202). Остановлен в процессе
  выгрузки (25 180 файлов из ~120 000).

## Артефакты в БД (`data/pilot.db`)

```sql
SELECT channel_id, config_kind, config_version, status FROM typical_configurations;
-- _ka2_25_92    | KA_2  | 2.5.25.92    | parsed
-- _bp30_138_24  | BP_30 | 3.0.138.24   | parsed
```

Plus 6 runs в `typical_indexing_runs` (parse_metadata + parse_bsl +
parse_queries для каждой конфигурации) с полными metrics в JSON metadata.

## Следующие шаги

1. **Phase 4 (Semantic Graph Builder)** на основе двух типовых.
   Достаточно для калибровки edge extractors.
2. Когда пользователь даст оставшиеся демки (ERP, ЗУП, УСО, Документо-
   оборот) — пайплайн прогонится через `python -m scripts.typical_pilot`
   за ~5-10 минут на каждую.
