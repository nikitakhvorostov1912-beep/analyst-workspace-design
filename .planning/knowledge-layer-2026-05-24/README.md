# Knowledge Layer — точка входа

> Внутренний модуль `1С Аналитик` для глубокого понимания клиентской  
> конфигурации 1С. Отдельный план развития на 6 милстоунов (Q3 2026 — Q1 2027).

---

## 30 секунд понимания

**Что:** Knowledge Layer = слой над приложением, который умеет отвечать  
на вопросы «почему» (RLS, пустые отчёты, медленные запросы, impact-анализ)  
с привязкой к конкретным `file:line` и стандартам ИТС.

**Где:** новый модуль `backend/app/knowledge/` + новые карточки во frontend  
(GraphCard, DiagnoseCard, etc.) + новый внутренний MCP-сервер (порт 7070).

**Почему сейчас:** конкуренты (1С:Напарник, MetaVision, Aether) покрывают  
L0-L3 (lexical → semantic). L4-L6 (behavioral → predictive) — пусто.  
Окно до 01.10.2026 (конец free-периода Напарника).

---

## Файлы в этой папке

### Стратегические

| Файл | Что | Когда читать |
|------|-----|--------------|
| **[PLAN.md](./PLAN.md)** | Стратегия, 6 milestones, принципы | Раз на сессию |
| **[STATE.md](./STATE.md)** | Текущий snapshot прогресса | КАЖДЫЙ раз перед работой |
| **[CLAUDE-RESUME.md](./CLAUDE-RESUME.md)** | Operational protocol для Claude | КАЖДЫЙ раз перед работой |

### Excel-реестр

| Файл | Что |
|------|-----|
| **[Knowledge_Layer_1С_Аналитик_2026-05-24.xlsx](./Knowledge_Layer_1С_Аналитик_2026-05-24.xlsx)** | 63 findings × 16 колонок + 25 use cases + tech stack + pricing + roadmap |
| `build_knowledge_layer_xlsx.py` | Source для пересборки Excel |

### По фазам

| Папка | Что |
|-------|-----|
| **`phases/M-K0-stabilization/`** | **M-K0 Stabilization — закрытие 28 critical+high findings ПЕРЕД Knowledge Layer** |
| `phases/M-K1/` | M-K1 Foundation — детальный план + state + summary |
| `phases/M-K2/` | M-K2 Knowledge Foundation (создаётся при kickoff) |
| `phases/M-K3/` | M-K3 Relational + Behavioral (плюс M-K3.0 ARCH-1 decompose loop.py) |
| `phases/M-K4/` | M-K4 Normative + Hybrid Retrieval |
| `phases/M-K5/` | M-K5 Predictive — 8.5-Ready revenue trigger |
| `phases/M-K6/` | M-K6 Predictive++ — NL2SQL + Enterprise |

### Architecture Decision Records

`adr/` — формальные записи архитектурных решений. Создаются в M-K1.1:
- `001-vector-db.md` — sqlite-vec / LanceDB
- `002-graph-db.md` — SQLite + recursive CTE
- `003-embeddings-runtime.md` — FastEmbed ONNX in-process
- (далее по мере появления решений)

### Прочее

| Файл | Что | Создаётся когда |
|------|-----|-----------------|
| `OPEN-VS-CLOSED.md` | Boundary open-source vs proprietary | M-K1.2 |
| `RISKS.md` | Live registry рисков | При появлении первого риска |
| `CHECKLIST.md` | Глобальный чек-лист | M-K1 kickoff |

---

## Как читать этот план — три сценария

### Сценарий 1: «Я новый человек, хочу понять что вы делаете»

1. Прочитать **этот README** (вы здесь)
2. Прочитать **PLAN.md** секции 1-3 (North Star + уровни + принципы)
3. Открыть **Excel** лист «Use Cases» — 25 конкретных сценариев
4. Открыть **Excel** лист «Roadmap» — milestones и сроки

**Время:** ~20-30 минут.

### Сценарий 2: «Я возвращаюсь к работе, что дальше?»

1. Прочитать **STATE.md** (где мы сейчас)
2. Прочитать **CLAUDE-RESUME.md** (если ты — Claude)
3. Открыть активный milestone — `phases/M-K<active>/M-K<active>-PLAN.md`
4. Открыть активную phase — `phases/M-K<active>/M-K<active>.<N>/PLAN.md`

**Время:** ~5 минут.

### Сценарий 3: «Я хочу понять конкретный finding из Excel»

1. Открыть **Excel** лист «Findings»
2. Найти по ID (например `L4-2 RLS-tracer`)
3. Колонки: что строить, зависимости, в каком milestone
4. Подробнее по milestone — в `phases/M-K<N>/M-K<N>-PLAN.md`

---

## Связь с основным проектом

Этот план — **расширение**, не замена основного roadmap проекта  
`analyst-workspace-design/`.

| Документ основного проекта | Связь с Knowledge Layer |
|---------------------------|-------------------------|
| `ROADMAP.md` (M1-M7) | Knowledge Layer = M-K series ПАРАЛЛЕЛЬНО или ПОСЛЕ M7 |
| `.planning/STATE.md` | Не пересекается — независимое state |
| `CHANGELOG.md` | Knowledge Layer добавляет записи под секцией «Knowledge Layer» |
| `.planning/development-plan-2026-05-24/` | 99 общих findings основного аудита — некоторые критичные блокируют M-K3 (см. STATE.md) |

---

## Связь с обширной 1С-экосистемой

Knowledge Layer не строится с нуля. Используем:

### Готовое локально (`C:/CLOUDE_PR/tools/`)
- `bsl-language-server-0.29.0-exec.jar` — диагностики, L5-3
- `mcp-1c-windows-amd64.v1.6.9.exe` — MCP к live базе
- `ssl_3_2/src/`, `ssl_3_1/src/` — БСП исходники для L5-2 RAG корпус
- `OnesTemplates/` — production BSL сниппеты
- `bsl-atlas/`, `1c-templates-mcp/`, `mdclasses/` — Docker tools для индексации

### Готовое в research (memory)
- 10 бизнес-процессов УТ/ERP end-to-end с движениями
- Карта типовых УТ 11.5 / ERP 2.5 / БП 3.0 / УСО 2.5
- Tier-list MCP-серверов, RAG-источников, code intelligence tools

### Внешнее (нужно подключить)
- `v8std-for-humans` (sfaqer) — markdown 317 ИТС-стандартов
- `tree-sitter-bsl` — для AST парсинга
- `BAAI/bge-m3` — multilingual embeddings (1024-dim, 8192-context)
- `FastEmbed` — ONNX runtime для embeddings (in-process, не Docker)

---

## Прогресс (live snapshot)

См. **STATE.md** для актуального состояния. Тут — статика на момент создания  
плана:

```
M-K0 Stabilization          [          ]   0%   (0/28)   ← ПЕРВЫМ
M-K1 Foundation             [          ]   0%   (0/9)
M-K2 Knowledge Foundation   [          ]   0%   (0/11)
M-K3 Relational + Behavioral[          ]   0%   (0/16)
M-K4 Normative + Hybrid     [          ]   0%   (0/10)
M-K5 Predictive             [          ]   0%   (0/10)
M-K6 Predictive++           [          ]   0%   (0/7)
────────────────────────────────────────────────
TOTAL (Stabilization + KL)  [          ]   0%   (0/91)
```

## Календарь (после M-K0 kickoff)

```
2026-05-25  ─ план готов, ждём kickoff
2026-06-20  ─ M-K0 done (Stabilization)         ←  фундамент стабилен
2026-07-05  ─ M-K1 done (Foundation)
2026-08-05  ─ M-K2 done (Knowledge Foundation)
2026-09-20  ─ M-K3 done                         →  MVP «Объяснитель»
2026-10-25  ─ M-K4 done                         →  INFOSTART A&PM EVENT
2026-12-20  ─ M-K5 done (8.5-Ready)             →  revenue trigger
2027-02-28  ─ M-K6 done (Enterprise)
```

---

## Точка следующего действия

**Сейчас:** план составлен, ждём kickoff **M-K0 Stabilization** от Никиты.

**Когда дашь сигнал** («погнали M-K0»):
1. Создаю branch `feature/m-k0-stabilization`
2. Создаю `phases/M-K0-stabilization/STATE.md`
3. Параллельно стартую 2 sub-branches:
   - `feature/m-k0-wave0-security` — M-K0.1 (SEC-1 SSRF + SEC-2..7, SEC-12)
   - `feature/m-k0-wave1-backend` — M-K0.2 (BE-1..6)
4. Затем waves 2-6 по плану

См. `phases/M-K0-stabilization/M-K0-PLAN.md` для детального плана.

**После M-K0 closed** — переход к M-K1 (см. `phases/M-K1/M-K1-PLAN.md`).

---

## История изменений README

- **2026-05-25** (v1.1): Добавлен **M-K0 Stabilization** как первый милстоун.  
  Точка следующего действия — kickoff M-K0 (не M-K1).
- **2026-05-25** (v1.0): Создан вместе с PLAN.md + STATE.md + CLAUDE-RESUME.md +  
  M-K1-PLAN.md.
