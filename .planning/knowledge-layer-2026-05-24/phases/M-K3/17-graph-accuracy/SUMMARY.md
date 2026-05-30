# M-K3.17 — Валидация и фиксы точности графа (killer-UC grounding)

> **Статус: УТ ✅ все 4 киллер-UC валидированы. ERP/КА/БП — pending батч-пересборка.**
> Сессии 2026-05-29/30. Ветка `feature/m-k3-relational-cfe` (НЕ запушена).
> Это SUMMARY про КОРРЕКТНОСТЬ графа. Про сборку как таковую — STATE.md (пивот).

---

## 0. TL;DR — скоркард киллер-UC (на УТ, ground-truth vs исходник)

| UC | Статус | Было → Стало |
|---|---|---|
| Цепочка вызовов / impact (CALLS) | ✅ корректно | 28% → 100% (cross-module был полностью сломан) |
| Чтение регистров (READS_FROM) | ✅ корректно | без изменений (зрелый query-парсер, 3/3 ground-truth) |
| Куда пишет движения (WRITES_TO) | ✅ корректно | флагман 0 → 44 документа; WRITES_TO 94 → 2485 |
| RLS (почему роль не видит X) | ✅ корректно | per-right 35% потери → восстановлено |

**Главный урок:** граф «выглядел готовым» (собран, 62K+ узлов, юнит-тесты зелёные), но был **бесполезен** для impact-анализа — cross-module CALLS не резолвились (2/7 на флагмане). Поймала только **сверка с живым исходником `.bsl`/`.xml`**. «Собрано + протестировано ≠ корректно».

---

## 1. Что сделано (коммиты сессии)

| Коммит | Что |
|---|---|
| `cefeb41` | CALLS cross-module CommonModule фикс. Резолв через `method_by_qname` + отложенная резолюция после Phase D. 28% → 86%. CALLS 480K→691K. |
| `8a5b4cd` | docs: архитектурный пивот (граф = backend grounding, GraphCard заморожен, #30 отменён). |
| `86bfa77` | CALLS manager-вызовы: `Документы/Регистры.X.Метод()` → `*.ManagerModule.Метод`. 86% → 100%. CALLS 691K→704K. |
| `32bb949` | Proof слоя инструментов: `dispatch_typical_tool` на исправленном графе. impact = 46 документов. + регрессия `test_trace_calls_surfaces_cross_module_edge`. |
| `afd3fbd` | **Движения (Phase F)** из метаданных `RegisterRecords` + **RLS per-right**. WRITES_TO 94→2485. 6 тестов. |
| `docs(state)` | Скоркард в STATE.md. |

### 1.1. CALLS (цепочка/impact) — `graph_builder.py`
- `_ConfigIndex.method_by_qname: dict[str,int]` — глобальный индекс qname метода→node_id, **полон только после Phase D всех модулей** → cross-module CALLS резолвятся отложенно.
- 3 формы вызова: same-module (bareword), cross-module CommonModule (`Модуль.Метод()`), **менеджеры** (`Документы.X.Метод()` → `Document.X.ManagerModule.Метод`, `РегистрыНакопления.X.ОтразитьДвижения` → `AccumulationRegister.X.ManagerModule.ОтразитьДвижения`).
- `_emit_method_behavior_edges(..., cross_calls=[])` собирает кандидатов; резолв в `_build_bsl_edges` после `commit` Phase D.
- **Остаток (не сделано, low pri):** `Объект.Метод()` на типизированной переменной — нужен type-inference. В проведениях редко.

### 1.2. Движения (WRITES_TO) — Phase F, `afd3fbd`
- **Корень проблемы:** старый WRITES_TO = единственный regex `Движения.X` (legacy direct-add). Современная УТ 11.5 проводит через запрос + `НаборЗаписей.Загрузить(ТаблицаДвижений)` (12 399 вхождений в исходнике!) — этот паттерн regex НЕ ловит. Флагман `ТоварыНаСкладах` = 0 писателей.
- **Решение (подтверждено веб-ресёрчем):** канонический источник — метаданные документа `<RegisterRecords>` (вкладка «Регистраторы» платформы). Платформа гарантирует полноту.
- `parse_register_records(path)` в `xml_parser.py` — `iter()` по XML, `<RegisterRecords>/<Item>`, тексты уже в форме `AccumulationRegister.X`.
- `_build_register_records_edges` (Phase F) в `graph_builder.py` — Document→Register WRITES_TO, attrs `{resolution: "register_records"}`. Гейт `o.kind == "Document"`, путь `snapshot_root/Documents/<name>.xml`.
- **Granularity mixed:** WRITES_TO теперь = method-level (BSL `Движения.X`, src=Method node) + object-level (Phase F, src=`Document.X` MetadataObject node). Инструмент `trace_typical_movements` возвращает оба как writers; doc-level имеют qname `Document.X`, module_kind=None.

### 1.3. RLS per-right — `afd3fbd`
- **Корень:** `insert_edge` дедуплицирует на (src,dst,kind). Билдер слал ребро на каждое право → схлопывалось в одно (роль,объект), теряя вторичные. 419 пар (35%) имели РАЗНЫЕ условия для Read/Update/Insert → терялись.
- **Решение:** группировка по объекту, список `[{right,condition}]` в attrs ОДНОГО ребра роль→объект (`graph_builder._build_role_rls_edges`).
- Инструмент `tool._handle_explain_rls` разворачивает список обратно. **Бэк-совместимость:** если `restrictions` нет — fallback на старые одиночные `right`/`condition`.
- **Изменён output инструмента:** теперь `roles_total` (число рёбер/ролей) + `total` (развёрнутые per-right записи). Раньше `total` = число рёбер.
- Объектный резолв был и остаётся 100% (1188 пар роль↔объект).

---

## 2. ⚠️ НЮАНСЫ / ГОЧИ (не забыть)

1. **`ut115.db` канал = `_bench`** (НЕ `_ut115_18_193`). Лежит `data/graph-index/ut115.db`. Скрипты-валидаторы читают отсюда. Channel `_bench` зашит в `graph_bench.py`.
2. **ERP/КА/БП ГРАФЫ УСТАРЕЛИ НА 3 ФИКСА.** `erp25.db`/`ka2_25.db`/`bp30.db` имеют только CommonModule-CALLS (пересборка 2026-05-29). Аудит подтвердил: `RLS_v2=False` у всех трёх, WRITES_TO малы (BSL-only). НЕТ: manager-CALLS (`86bfa77`), Phase F движений, RLS-v2 (оба `afd3fbd`). **Только УТ полный.**
3. **pilot.db (3.3 ГБ) ЗАБЛОКИРОВАН NIM** (фоновый rebuild карточек пишет `pilot.db-wal`). Прод-консолидация графа (1 БД / 4 channel_id) — ТОЛЬКО после NIM. НЕ трогать pilot.db.
4. **NIM-track файлы — НЕ коммитить:** `scripts/nvidia_nim_rebuild.py`, `response-nim-*.json`, `batch-compact-wave4-*.json`, `samples.json`, `benchmark_nim.sh`. Они меняются в фоне. Всегда `git add <явные пути>`, НЕ `-A`/`.`.
5. **bench traverse depth-5 > 300 ms** (1097 ms) — предсуществующий стресс-замер (рос с масштабом графа 62K→259K при добавлении Phase D, не от моих правок). **UC-путь** (`traverse_bfs` edge_kind=CALLS, depth≤4) = **222 ms** — норма. DoD `traversal_le_300ms` был false и до фиксов.
6. **GraphCard заморожен** (backend-only grounding). Emit graph-card в `loop.py` ещё активен — **отключить** при рефакторинге grounding (pending).
7. **Cyrillic в коммитах** — через `git commit -F <tmpfile>` (UTF-8). Console-вывод Python в cp1251 → писать валидацию в UTF-8 файлы, читать Read'ом.
8. **Снапшоты неоднозначны:** несколько на конфу (`ka2-ar2011`/`ka2-demo201`/`ka2-2.5.25.92`; `erp-enterprise20`/`erp25-demoent206`). Использованы: **ut115-demotrd, erp25-demoent206, ka2-2.5.25.92, bp30-accounting** (из build.log).

---

## 3. PENDING (упорядочено)

### 3.1. Батч-пересборка ERP/КА/БП (×3, после NIM) — ЧЕКЛИСТ
Текущий билдер уже содержит все фиксы. Команда (из `backend/`, NIM-safe, отдельные БД):
```
python -m scripts.graph_bench --snapshot <ABS_snapshot> --db <ABS_db>
```
| Конфа | snapshot | db | время (без контеншена) |
|---|---|---|---|
| ERP 2.5 | `data/typical-snapshots/erp25-demoent206` | `data/graph-index/erp25.db` | ~11 мин |
| КА 2.5 | `data/typical-snapshots/ka2-2.5.25.92` | `data/graph-index/ka2_25.db` | ~12 мин |
| БП 3.0 | `data/typical-snapshots/bp30-accounting` | `data/graph-index/bp30.db` | ~6 мин |

После каждой — **ре-валидировать** (раздел 4). Признак успеха: `RLS_v2=True`, WRITES_TO doc-level в тысячах, флагман-регистр конфы имеет писателей.

### 3.2. Прочее
- **Прод-консолидация в `pilot.db`** (1 БД / 4 channel_id `_ut/_erp/_ka/_bp`) — после NIM.
- **Grounding в чате** — LLM (MiMo) дёргает `trace_typical_calls`/`trace_typical_movements`/`explain_rls` → ответ с пруфами. **НЕ начат.** Это финальное доказательство ценности.
- **Per-config паки** — экспорт пруненых графов для desktop-доустановки (вариант A lossless ~217 МБ/конфа). После grounding.
- **Отключить graph-card emit в `loop.py`** (GraphCard freeze).
- **Type-inference `Объект.Метод()`** — остаток CALLS, low pri.

---

## 4. Скрипты-валидаторы (закоммичены, переиспользовать после пересборки)

| Скрипт | Что проверяет | Вывод |
|---|---|---|
| `scripts/graph_tool_proof.py` | CALLS/impact через реальный `dispatch_typical_tool` | `data/graph-index/_toolproof.txt` |
| `scripts/graph_movements_rls_proof.py` | движения (RegisterRecords) + RLS per-right | `_mov_rls_proof.txt` |
| `scripts/graph_validate_methods.py` | CALLS vs исходник `.bsl` (line_start/end) для 4 методов | `_validate.txt` |
| `scripts/graph_calls_probe.py` | наличие конкретных cross-module CALLS | `_probe.txt` |

Каждый: запуск из `backend/`, читает `../data/graph-index/ut115.db` (поправить путь на нужную конфу). Channel `_bench`.

---

## 5. Тесты (регрессии, 132 passed в typical/graph-сабсете)

- `test_typical_tool.py::test_trace_calls_surfaces_cross_module_edge` — cross-module CALLS всплывает через инструмент (out + impact in).
- `test_typical_graph_builder.py` — `test_emit_collects_cross_module_calls`, `test_emit_collects_manager_calls`.
- `test_typical_xml_parser.py` — `parse_register_records` ×3 (уникальность, нет блока, нет файла).
- `test_typical_register_records_edges.py` — Phase F ×3 (эмиссия, пропуск вне индекса, нет XML).
- `test_typical_rls_edges.py` — `test_build_role_rls_edges_groups_per_right_in_one_edge` (+обновлён ассерт старого формата на `restrictions`).
- `test_typical_rls_tool.py::test_explain_rls_expands_per_right_restrictions`.
