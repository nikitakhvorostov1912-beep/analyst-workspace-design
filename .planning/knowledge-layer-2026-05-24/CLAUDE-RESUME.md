# CLAUDE-RESUME — Operational Protocol для Claude

> Этот файл — инструкция для меня (Claude) в любой новой сессии работы  
> по Knowledge Layer. Не для пользователя. Не марковский протокол.  
> Сначала читаю → потом действую.

---

## 0. Quick boot (первые 30 секунд новой сессии)

При запросе «продолжай Knowledge Layer» / «продолжи план» / «давай дальше по плану»:

1. **Прочитать `STATE.md`** в этой же папке — узнать active milestone + phase  
   ⚠ Текущий active — **M-K0 Stabilization** (НЕ M-K1!). Сначала закрываем  
   дыры из общего аудита, потом Knowledge Layer.
2. **Прочитать `phases/<active-milestone>/STATE.md`** если файл существует
3. **Прочитать `phases/<active-milestone>/<active-phase>/PLAN.md`** если phase активна
4. **Озвучить в ОДНОМ сообщении:**
   - На чём остановились (последний коммит / последний завершённый task)
   - Следующая задача
   - 2-3 опции что делать дальше
5. **Ждать команды.** НЕ начинать работу автономно. Кроме случая когда пользователь  
   сказал «иди до конца» или «работай без пауз» — тогда атомарными коммитами по плану.

**Sequence of milestones (важно знать порядок):**
- M-K0 Stabilization (28 findings из общего аудита) — **ПЕРВЫМ**
- M-K1 Foundation (decisions + ADR + quick wins)
- M-K2 Knowledge Foundation (indexer + RAG)
- M-K3 Relational + Behavioral (graph + diagnose — MVP «Объяснитель»)
- M-K4 Normative + Hybrid (compliance + retrieval)
- M-K5 Predictive (temporal + 8.5-Ready revenue)
- M-K6 Predictive++ (NL2SQL + enterprise)

---

## 1. Wrong-project guard

**Работаем ТОЛЬКО в** `C:\CLOUDE_PR\projects\analyst-workspace-design\`.

Knowledge Layer — внутренний модуль этого проекта. НЕ путать с:
- `C:\CLOUDE_PR\projects\analyst-tools-1c\` — заброшенный v0 концепт
- `C:\CLOUDE_PR\projects\russian-transit\` — отдельный 1С-проект пользователя
- Прочие папки `C:\CLOUDE_PR\projects\*` — отдельные проекты

Если запрос про другой проект — переспросить.

---

## 2. Что читать НЕ нужно (экономия контекста)

При работе по Knowledge Layer **НЕ читать**:
- `mockups/` и `mockups/_legacy/` — историческое
- `docs/_archive-v0-object-ide/` — мёртвый код
- `backend/dev-*.log`, `backend/smoke-*.log` — runtime логи
- `desktop/build-*.log` — build-логи
- `frontend/.next/` — build артефакты

При работе НАД Knowledge Layer **читать выборочно по триггеру**:
- `loop.py` — только когда задача про orchestrator integration
- Все 99 общих findings — только если задача про их закрытие
- Существующие phase summaries — только при оценке impact

---

## 3. Иерархия документов

```
.planning/knowledge-layer-2026-05-24/
├── README.md                ← навигация. Читается при путанице.
├── PLAN.md                  ← стратегия. Читается раз на сессию для контекста.
├── STATE.md                 ← snapshot. Читается КАЖДЫЙ раз при boot.
├── CLAUDE-RESUME.md         ← ЭТОТ ФАЙЛ. Читается КАЖДЫЙ раз при boot.
├── CHECKLIST.md             ← глобальный чек-лист (создаётся при первом kickoff).
├── RISKS.md                 ← live registry (создаётся когда появляется первый риск).
├── Knowledge_Layer_*.xlsx   ← 63 findings reference.
├── build_knowledge_layer_xlsx.py  ← source для пересборки Excel.
├── adr/
│   ├── 001-vector-db.md     ← Создаётся в M-K1.1
│   ├── 002-graph-db.md
│   └── 003-embeddings.md
└── phases/
    ├── M-K1/
    │   ├── M-K1-PLAN.md     ← Детальный план milestone.
    │   ├── STATE.md         ← Создаётся при kickoff M-K1.
    │   ├── M-K1.1-adr/      ← Создаётся при старте phase.
    │   │   ├── PLAN.md
    │   │   └── SUMMARY.md   ← Заполняется на завершении.
    │   ├── M-K1.2-open-vs-closed/
    │   └── ...
    └── M-K2/, M-K3/...
```

**Принцип:** каждый файл имеет одну ответственность.  
PLAN.md — стратегия. STATE.md — где мы. CLAUDE-RESUME.md — как продолжить.

---

## 4. Workflow одной phase

Когда пользователь говорит «делаем M-K1.3» или «дальше по плану»:

### Step 1: Setup phase (если не сделано)
```bash
mkdir -p phases/M-K1/M-K1.3-module-skeleton
```

Создать `phases/M-K1/M-K1.3-module-skeleton/PLAN.md`:
- Subject + Description (из M-K1-PLAN.md)
- Acceptance criteria
- Files to create / modify
- Tests to write
- Estimated effort

### Step 2: Implementation
- Атомарные изменения
- Каждый файл: проверить синтаксис после изменения
- TDD по возможности (test → red → impl → green)

### Step 3: Verify
- `pytest` для backend изменений
- `vitest` для frontend
- Smoke через `/awd-quality-gate` если делали integration
- Проверка нет ли регрессий в общих тестах

### Step 4: Commit
Формат:
```
feat(knowledge): M-K1.3 module skeleton — backend/app/knowledge/

- Создан __init__.py, README.md, types.py, exceptions.py
- ADR-004 о module layout
- Тесты test_knowledge_init.py (3 шт)

Refs: phases/M-K1/M-K1.3-module-skeleton/PLAN.md
```

### Step 5: Summary
Заполнить `phases/M-K1/M-K1.3-module-skeleton/SUMMARY.md`:
- Что сделано
- Что не сделано (если что-то отложено — почему)
- Файлы изменены / созданы
- Тесты добавлены
- Метрики (если применимо)
- Технический долг (если родил)

### Step 6: Update parent STATE
- Обновить `phases/M-K1/STATE.md` (отметить phase как completed)
- Обновить root `STATE.md` (% прогресса)

### Step 7: Что следующее
- Озвучить пользователю: «M-K1.3 done. Следующее — M-K1.4 Storage Layout.  
  Продолжать или сделать паузу?»

---

## 5. Когда останавливаться (НЕ делать без согласования)

Останавливаться **до согласования** в этих случаях:

### 5.1. Scope creep
Задача требует выйти за пределы текущей phase. Не делать, а спросить:
```
CONFUSION: задача M-K1.3 (module skeleton) требует <X>, который относится  
к M-K1.4 (Storage Layout). 
Options:
  A) Расширить M-K1.3 (сдвинуть оценку)
  B) Сделать <X> сразу как часть M-K1.4 (поменять порядок)
  C) Сделать stub в M-K1.3, полная реализация в M-K1.4
→ Какой выбрать?
```

### 5.2. Архитектурный выбор
Появилась необходимость в новом решении (новая lib, новый паттерн).  
→ Написать short ADR (1 страница) и спросить approval, не коммитить.

### 5.3. Технический долг основного продукта блокирует
Например, начали делать Knowledge Layer integration в orchestrator, но  
loop.py не задекомпозирован (ARCH-1) — менять рискованно.  
→ Сообщить, спросить: фиксим ARCH-1 сначала или делаем minimal-invasive workaround?

### 5.4. Тест падает на main
Перед коммитом любой phase — прогон `pytest` + `vitest`. Если падает что-то,  
что не было сломано до — НЕ коммитить, расследовать, исправить или откатить.

### 5.5. Правило 3 итераций
Если за 3 раунда уточнений с пользователем задача не закрылась → STOP,  
переформулировать в spec. Подробно: `rules/1c/1c-ai-collaboration.md`.

---

## 6. Что делать БЕЗ согласования (проактивно)

Эти действия — без вопросов:

- **`pytest` после каждой явной правки backend кода**
- **`pnpm vitest run` после каждой явной правки frontend кода**
- **Обновление phase SUMMARY.md и parent STATE.md по завершении phase**
- **Атомарные коммиты с понятным message**
- **Создание ADR при наличии техн. выбора (но НЕ применять решение без approval)**
- **Документация в коде (docstrings, README для модуля)**
- **Cleanup временных артефактов (logs, tmp files) перед коммитом**

---

## 7. Brutal honesty contract

В работе по Knowledge Layer (как везде):

- НЕ говорить «должно работать» вместо «проверил — работает»
- НЕ скрывать ошибки или регрессии
- НЕ заявлять % прогресса по форме («M-K1 50% done») без реальной верификации
- Признавать когда не помню или не знаю — НЕ выдумывать
- При несогласии с пользователем — пушить back, не молча соглашаться

См. `.claude/rules/session-contract.md` (project-local).

---

## 8. Полезные команды (одной строкой)

### Структура проекта
```bash
# Где Knowledge Layer файлы
ls C:/CLOUDE_PR/projects/analyst-workspace-design/.planning/knowledge-layer-2026-05-24/

# Где Knowledge Layer код (будет создан в M-K1.3)
ls C:/CLOUDE_PR/projects/analyst-workspace-design/backend/app/knowledge/
```

### Тесты
```bash
# Backend
cd C:/CLOUDE_PR/projects/analyst-workspace-design/backend && python -m pytest tests/knowledge/ -v

# Frontend
cd C:/CLOUDE_PR/projects/analyst-workspace-design/frontend && pnpm vitest run

# Quality gate целиком
Skill: awd-quality-gate
```

### Стек dev
```bash
# Поднять backend + frontend
Skill: awd-dev-up
```

### Excel — пересобрать
```bash
cd C:/CLOUDE_PR/projects/analyst-workspace-design/.planning/knowledge-layer-2026-05-24/
python build_knowledge_layer_xlsx.py
```

### Git
```bash
# Создать branch для нового милстоуна
cd C:/CLOUDE_PR/projects/analyst-workspace-design
git checkout -b feature/m-k1-foundation main

# Атомарный коммит
git add <files> && git commit -m "feat(knowledge): M-K1.X subject — details"
```

---

## 9. Tools доступные для Knowledge Layer

### Готовые локально

| Tool | Где | Когда использовать |
|------|-----|--------------------|
| `bsl-language-server-0.29.0-exec.jar` | `tools/` | Валидация BSL, диагностики (L5-3 antipattern detector) |
| `mcp-1c-windows-amd64.v1.6.9.exe` | `tools/` | Read-only MCP к live базе 1С (L1, L2 source data) |
| `mcp-bsl-context-0.3.2.jar` | `tools/` | MCP для API платформы (L1 Structural reference) |
| `ssl_3_2/src/`, `ssl_3_1/src/` | `tools/` | БСП исходники (L5-2 RAG корпус), grep-able |
| `OnesTemplates/` | `tools/` | Production BSL сниппеты (L5 patterns) |
| `bsl-atlas/` | `tools/` | Vector RAG прототип (если получится Docker запустить) |
| `1c-templates-mcp/` | `tools/` | Шаблоны кода |
| `mdclasses/` | `tools/` | Java парсер метаданных (L1 Structural builder) |

### Внешние (нужны)

- **v8std-for-humans** (sfaqer на GitHub) — для L5-1 ИТС RAG (клонировать в `tools/`)
- **tree-sitter-bsl** — для L2-2 BSL parser (npm/pip package)
- **FastEmbed** — для L3-2 embeddings (pip install)
- **sqlite-vec** — для L3-1 vector store (pip install)

---

## 10. Memory маршруты (когда смотреть)

Память Claude (`~/.claude/projects/C--CLOUDE-PR/memory/`):

| Триггер | Файл |
|---------|------|
| Работа с типовыми УТ/ERP/БП/УСО | `memory/1c-business-processes-data-structures-2026-05-24.md` |
| Поиск инструментов экосистемы 1С | `memory/1c-ecosystem-deep-research-2026-05-24.md` |
| Подбор vector store / RAG / embeddings | `memory/MEMORY.md` → research/ecosystem-deep-revision-2026-05-17/ |
| Reference на 1С-стандарты | `rules/1c/1c-anti-patterns.md`, `1c-core-standards.md`, etc. |

Индекс: `~/.claude/projects/C--CLOUDE-PR/memory/MEMORY.md`.

---

## 11. Что делать, если что-то непонятно

В порядке убывания «уверенности что найду ответ»:

1. **`STATE.md`** этой папки
2. **`PLAN.md`** этой папки — секции с конкретными milestones
3. **`Knowledge_Layer_*.xlsx`** — конкретный finding
4. **`phases/<active>/M-Kx-PLAN.md`** — детали активной фазы
5. **CLAUDE.md** в корне проекта — общие правила
6. **`.claude/rules/*.md`** project-local — operational rules
7. **CHANGELOG.md** проекта — что было сделано раньше
8. **Спросить пользователя** — если 1-7 не дали ответа

---

## 12. Anti-patterns моей работы (НЕ повторять)

Из практики:

- ❌ Запускать 5+ агентов с длинными промптами — они падают по `prompt is too long`.  
  → Делать промпт ≤ 1500 слов, дробить на маленькие задачи.
- ❌ Читать огромные файлы целиком (loop.py 1506 строк) — забивает контекст.  
  → Сначала `wc -l`, потом по 200 строк, head + tail.
- ❌ Молча менять scope phase.  
  → CONFUSION block, спросить.
- ❌ Заявлять «готово» без `pytest`.  
  → Всегда verify.
- ❌ Создавать .md файлы которые пользователь не просил.  
  → Только при явной задаче.
- ❌ Параллельные изменения в одних и тех же файлах разных агентов.  
  → Sequence dependencies, не параллелить overlap.

---

## 13. Связь с основным проектом — границы

Knowledge Layer **дополняет** существующий продукт v1.4.5, **не заменяет**.

- Существующие `loop.py`, `orchestrator/`, MCP tools — **не трогать без явной причины**
- Добавляем **новые** internal tools в orchestrator (`knowledge_*`)
- Добавляем **новые** routes (`/knowledge/*`)
- Добавляем **новый** модуль `backend/app/knowledge/`
- Добавляем **новые** карточки во frontend (GraphCard etc.)
- Расширяем существующие миграции SQLite (новые таблицы, не замена)

**Когда меняем existing файлы:**
- Только если задача явно требует
- Минимальный diff (Surgical Changes из CLAUDE.md)
- Тесты на старый функционал должны остаться зелёными
- Описать «зачем» в commit message
