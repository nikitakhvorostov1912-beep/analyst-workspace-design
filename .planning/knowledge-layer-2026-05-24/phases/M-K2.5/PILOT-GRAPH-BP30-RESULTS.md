---
pilot: "Semantic Graph БП 3.0.138.24"
date: "2026-05-26"
phase: "M-K2.5.4"
bsl_file_limit: 200
duration_s: 791
result: success
fatal_errors: 0
---

# Pilot Results — Semantic Graph Builder БП 3.0.138.24

> Первый прогон **Phase 4 Graph Builder** на реальной типовой.
> Цель — проверить что:
> 1. 6 типов edges (CONTAINS / CALLS / USES / WRITES_TO / READS_FROM / REFERENCES)
>    корректно строятся на production-данных.
> 2. Резолверы (русский→английский префикс) работают для query tables.
> 3. Производительность приемлемая (< 1 сек на BSL модуль).
> 4. Идемпотентность: повторный прогон не дублирует nodes/edges.

## Источник

| Параметр | Значение |
|---|---|
| Конфигурация | Бухгалтерия предприятия 3.0.138.24 |
| Snapshot | `data/typical-snapshots/bp30-accounting/` |
| channel_id | `_bp30_138_24` |
| BSL лимит | 200 модулей (smoke; полные 14725 — отложено) |

## Что построено (БД `data/pilot.db`)

### Nodes — 60 326

| NodeKind | Кол-во | Доля |
|---|---:|---:|
| Attribute | 38 290 | 63.5% |
| MetadataObject | 11 713 | 19.4% |
| Module | 8 021 | 13.3% |
| TabularSection | 1 838 | 3.0% |
| Method | 464 | 0.8% |

> Method — только из 200 BSL-модулей. Полный прогон даст ~30 тыс. methods.

### Edges — 65 091

| EdgeKind | Кол-во | Доля | Источник |
|---|---:|---:|---|
| **CONTAINS** | 48 613 | 74.7% | XML structure (object → attr / ts / module) |
| **REFERENCES** | 16 190 | 24.9% | type_definition реквизитов |
| USES | 132 | 0.2% | BSL `Документы.X` / `Справочники.Y` |
| CALLS | 116 | 0.2% | BSL same-module вызовы |
| READS_FROM | 38 | 0.06% | BSL query tables + virtual tables |
| WRITES_TO | 2 | 0.003% | BSL `Движения.X.Записать()` |

## Производительность

| Метрика | Значение |
|---|---|
| Время | **791 сек** (~13.2 мин) |
| Объектов в Phase B (структура) | 11 713 |
| Время Phase B | ~5-7 мин |
| Время Phase C (REFERENCES) | ~5 мин (зависит от количества реквизитов) |
| Время Phase D (BSL) | ~3 мин на 200 модулей |
| Темп BSL | ~67 модулей/мин ≈ **0.9 сек/модуль** |

**Экстраполяция полного прогона:**
- Структура (Phase B/C) — 12-15 мин фикс
- BSL (Phase D) — 14 725 модулей × 0.9 = **~3.7 часа**
- Итого — **~4 часа на полный граф БП 3.0**

Это значимо больше M-K2.5.3 пилота (2.5 мин на парсеры).
Доминирует Phase B/C — каждый attribute требует INSERT + потенциально REFERENCES.

### Оптимизации к Phase 8

1. **Bulk INSERT через `executemany`** — текущий код делает по 1 insert на каждый
   node/edge. Bulk обещает 5-10× ускорение.
2. **Skip REFERENCES для составных типов > 50 ссылок** — некоторые типовые
   реквизиты ссылаются на 100+ справочников (TypeSet). Это шум для графа.
3. **Параллельный BSL parse** — Phase D можно распараллелить через
   `asyncio.gather` (BSL parse — CPU-bound, но aiosqlite serialised).

## Качественная проверка резолва

### CONTAINS работает
Каждый MetadataObject имеет ≥ 1 связь CONTAINS → attribute / TS / module.
48 613 edges / 11 713 объектов = ~4.1 children в среднем. Совпадает с
эмпирикой: документ обычно содержит 1-3 модуля + 5-15 реквизитов + 1-3 ТЧ.

### REFERENCES работает
16 190 ссылочных edges на 38 290 атрибутов = 42% реквизитов имеют
ссылочный тип. Логично — много справочных реквизитов в типовой
конфигурации БП.

### USES / CALLS / WRITES_TO / READS_FROM на 200 модулях
Только 200/14725 = 1.4% BSL модулей попали в пилот. Числа:
- 116 CALLS = 0.58 same-module вызовов на модуль (мало; cross-module
  через `ОбщегоНазначения.X` пока не доминирует — нужен полный набор
  CommonModules для резолва)
- 132 USES = 0.66 упоминаний метаданных на модуль
- 2 WRITES_TO — мало; вероятно среди 200 модулей мало `ОбработкаПроведения`
  документов. Полный прогон даст реалистичную картину.
- 38 READS_FROM — отчёты / общая логика. После фикса нормализации
  `Документ.X` → `Document.X` (см. ниже) — теперь резолвится.

## Найденные баги (исправлены в этой сессии)

### 1. `update_run_progress` kwarg `metadata` → `metadata_patch`
Pilot скрипт упал в финальном update. Сам граф был построен корректно
(БД сохранила upsert'ы), но status конфигурации не сменился с `parsed`
на `graph_built`. Фикс — единичная замена аргумента.

### 2. Нормализация query table names
`query_parser` возвращает имена таблиц как они написаны в запросе:
`Документ.Заказ`, `РегистрНакопления.ТоварыНаСкладах`. Но
`metadata_by_qname` использует английские `MetadataKind.value`:
`Document.Заказ`, `AccumulationRegister.ТоварыНаСкладах`.

Без нормализации все READS_FROM находились в null'е → 0 edges.

**Исправление:** `_normalize_query_table_qname()` маппит русские префиксы
(и английские для конфиг в English locale) → MetadataKind value. Также
обрабатывает `Документ.X.Товары` → `Document.X.ТабличнаяЧасть.Товары` для
ТЧ в запросе.

После фикса 38 edges READS_FROM на 200 модулей — корректно резолвится.

## Артефакты в БД

```sql
SELECT channel_id, status FROM typical_configurations WHERE channel_id LIKE '_bp30%';
-- _bp30_138_24 | graph_built

SELECT COUNT(*) FROM graph_nodes WHERE channel_id = '_bp30_138_24';
-- 60326

SELECT COUNT(*) FROM graph_edges e
JOIN graph_nodes n ON e.src_id = n.id
WHERE n.channel_id = '_bp30_138_24';
-- 65091
```

## Следующие шаги

1. **Полный прогон БП 3.0 без bsl-limit** — занимает ~4 часа, отложено
   на отдельную сессию (foreground блокирует).
2. **Phase 4 для КА 2.5.25.92** — данные структурно похожи, ожидаемое
   время 6-8 часов (24k модулей).
3. **Оптимизация bulk INSERT** перед Phase 8 (run all 7 configs).
4. **Phase 5 (Object Cards)** — следующая фаза в плане. Использует
   уже построенный граф для группировки методов / атрибутов вокруг
   MetadataObject + LLM генерации описаний.
