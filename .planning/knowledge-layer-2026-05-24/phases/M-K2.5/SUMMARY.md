---
milestone: M-K2.5
milestone_name: "Typical Configurations Knowledge"
status: closed
closed_at: "2026-05-26"
phases_completed: 9          # 0-8 + SUMMARY
phase_8_done: 4              # 4/7 типовых полностью загружены
phase_8_deferred: 3          # ЗУП/УСО/Документооборот — ждут снапшоты
total_commits: 9
total_tests_added: 369
---

# M-K2.5 — SUMMARY (closing)

## Что доставлено

**Полнофункциональная подсистема знаний о типовых конфигурациях 1С**
для бота-аналитика: парсеры → семантический граф → LLM-карточки →
LLM tools в orchestrator → frontend UI.

### Цифры в БД (`data/pilot.db`)

| Конфигурация | Объектов | Nodes | Edges | Карточек |
|---|---:|---:|---:|---:|
| БП 3.0.138.24 | 11 713 | 166 769 | 314 008 | 11 713 |
| КА 2.5.25.92 | 19 683 | 300 232 | 559 287 | 19 683 |
| УТ 11.5.17.226 | 11 781 | 147 868 | 276 763 | 11 781 |
| ERP 2.5.21.118 | 20 020 | 302 462 | 563 349 | 20 020 |
| **Итого 4/7** | **63 197** | **917 331** | **1 713 407** | **63 197** |

## Фазы (все закрыты)

| Phase | Subject | Commit |
|---|---|---|
| 0 | Infrastructure (migration v17 + storage + ADR-003) | `7167744` |
| 1 | BSL Parser AST (tree-sitter-bsl) | `f751d7a` |
| 2 | Query Parser (BSL Query Language) | `0019745` |
| 3 | XML Metadata Parser | `f96dde7` |
| 4 | Semantic Graph Builder (6 EdgeKind) | `40297f3` |
| 5 | Object Cards Generator (mock LLM) | `a077035` |
| 6 | LLM Tools (6 функций в orchestrator) | `44468bf` |
| 7 | Frontend UI (TypicalSelector + TypicalObjectCard) | `a07ae28` |
| perf | Bulk graph optimization (commit=False + WAL + RETURNING) | `0ca9653` |
| 8a | Phase 8 partial: БП + КА полные | `16ea8f3` |
| 8b | Phase 8 extend: УТ + ERP полные | `b882c45` |

## Тесты

- **369 новых unit-тестов** (Python pytest + TypeScript vitest)
- **55 проверок smoke** через `typical_smoke_questions.py` — все
  зелёные на production-данных
- Регрессия всех `typical/*` тестов: ~347 в узком наборе

## LLM tools (6) — что бот теперь умеет

| Tool | Use case |
|---|---|
| `list_typical_configurations` | Какие типовые загружены + готовность |
| `search_typical_objects` | Найти объект по имени/описанию в карточках |
| `explain_typical_object` | Карточка + контекст графа |
| `trace_typical_calls` | BFS по CALLS (вверх/вниз, depth≤4) |
| `trace_typical_movements` | WRITES_TO + READS_FROM регистра |
| `compare_with_typical` | заглушка v1 (требует M-K3) |

Smoke на реальных данных подтверждает:
- Поиск находит `«хозрасчетный»` (БП), `«закрытие»` (ERP),
  `«реализация»` (УТ) с правильной фильтрацией по kind
- `explain` отдаёт корректный kind + карточку + children_summary
  для всех 4 типовых на ключевых объектах
- `trace_movements` показывает 50 писателей и 50 читателей для
  БП.AccountingRegister.Хозрасчетный
- Error paths корректно отбрасывают пустой query, неизвестный tool,
  неверный direction

## Что отложено (явно)

| Что | Где | Когда нужно |
|---|---|---|
| Real LLM adapter (mock → OpenAI/NVIDIA) | M-K2.5.5 stub Protocol готов | Когда захотим production-карточки (~$13 за 4 типовых v1, ~$220 за v2) |
| `compare_with_typical` реальная реализация | M-K2.5.6 заглушка | После M-K3 (граф клиентской базы) |
| TypicalObjectCard wiring в CardRenderer | M-K2.5.7 компонент готов | Когда определимся с shape tool_result в orchestrator |
| ЗУП 3.1 / УСО 2.5 / Документооборот 3 | M-K2.5.8 phase_8_pending | После получения demo `.dt` от пользователя |
| Semantic search через embedding карточек | — | После real LLM adapter (карточки нужно эмбедить) |
| **Cards v2 — production-готовые карточки** | **`CARDS-V2-PLAN.md`** | **6-8 сессий, $220 на rebuild, отдельная мини-фаза M-K2.5.9** |

## Cards v1 → v2 — известные ограничения

v1 карточки (текущие 63k mock + готовые к real LLM) — **MVP**, для серьёзных
сложных запросов **недостаточны**. Полный список гэпов + production-план
в **[CARDS-V2-PLAN.md](./CARDS-V2-PLAN.md)**:

1. Одна generic-схема на 30+ типов объектов (нужны 9 специализаций)
2. Линейный `posting_flow` без условной логики (нужны conditional steps)
3. `its_links: []` всегда (нужна mention-extraction через M-K2.7/2.8 RAG)
4. Нет cross-config diff между УТ/БП/КА/ERP
5. Нет версионной меты (introduced_in / breaking_changes)
6. Нет нормативки (M-K4 hook отсутствует)
7. LLM-hallucination не отлавливается (нужен LLM-judge + cross-check vs граф)
8. Нет ролей/RLS и подсистем
9. `embedding_text` неполный (теряет attributes / scenarios / related)
10. Form-handlers вне карточки (есть в графе, но не в card)
11. Нет hard limits на размер полей
12. Schema migration для существующих 63k v1 карточек требует backward compat

v2-план фазирован (v2.A-H), каждая фаза с явными acceptance criteria,
метриками качества (numerical targets), golden dataset для validation,
оценкой cost. Минимум для production: v2.A + v2.C + v2.E + v2.G + v2.H
(~20 часов работы).

## Handoff в M-K3

M-K3 «Relational + Behavioral» — главный USP проекта по `PLAN.md`.
Это **5 killer use cases** на L2 (графы) + L4 (диагноза) для
**клиентских баз** (не только типовых).

### Готовые блоки для M-K3

1. **`graph_storage`** (M-K3.17.1a) — общий слой для типовых и клиентских
   графов. На M-K2.5 проверен на 917k узлов / 1.7M рёбер. Bulk
   оптимизация (commit=False + WAL) даёт 30-50× ускорение.
2. **6 EdgeKind** + reusable extractors (CALLS/USES/WRITES_TO/READS_FROM)
   — те же extractors применимы к BSL коду клиентских баз.
3. **`compare_with_typical`** ждёт client graph — это первая большая
   фича M-K3 которая разблокирует core use case «что доработано
   относительно типовой».
4. **Channel-namespace scheme** установлен: типовые на `_<kind>_*`,
   клиентские на UUID v4. Single graph_storage обслуживает оба
   домена через JOIN.

### Рекомендуемая следующая фаза

`M-K3.0 Preparatory` — `ARCH-1 decompose loop.py` (из PLAN.md):
loop.py разросся до 2000+ строк, его декомпозиция — предусловие
для добавления M-K3 функций без копипасты.

После M-K3.0 — `M-K3.1 BSL parser применить к клиентской базе`
(переиспользуем `graph_builder` из M-K2.5.4 без изменений, только
другой namespace channel'а).

## Метрики милстоуна

| Метрика | Значение |
|---|---:|
| Длительность | 1 интенсивная сессия (~10 часов с перерывами) |
| Lines of code (Python prod) | ~5 500 |
| Lines of code (тесты) | ~3 500 |
| Lines of code (TypeScript) | ~700 |
| Коммитов в main | 9 |
| Объём данных в БД (`pilot.db`) | ~280 MB |
| Конфигураций загружено полностью | 4 / 7 (57%) |
| Snapshot времени pipeline (с DESIGNER) | ~25-35 минут на конфигурацию |
| Стоимость production LLM-карточек (4 типовых) | ~$13.20 (GPT-4o-mini) |

## Закрывающий коммит

`pending — M-K2.5 SUMMARY + closing commit`
