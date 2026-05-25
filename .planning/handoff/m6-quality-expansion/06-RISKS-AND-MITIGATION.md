# 06 — Risks + Mitigation

## Топ-12 рисков по убыванию вероятности × урон

### 🔴 R1: MetaVision CLI fork — большая Java работа

**Вероятность:** 50% | **Урон:** 4 недели задержки

**Что:** MetaVision сейчас — GUI-only. Чтобы добавить CLI режим, нужен рефакторинг Java кода. Я не Java-разработчик. Автор `AndreyHhh` может не принять PR.

**Митигация:**
- **Plan A** — собственный fork с CLI, без зависимости от upstream
- **Plan B** — wrapper над GUI через xvfb (headless X11) на Linux, для Windows — Selenium-style automation
- **Plan C (fallback)** — отказаться от inline graph в чате, оставить кнопку "Открыть в MetaVision GUI" (запускает desktop app)
- **Trigger:** если за 1 неделю Phase 16.1 нет рабочего CLI — переходим на Plan B/C

### 🔴 R2: .hbk парсер сложный

**Вероятность:** 70% | **Урон:** 5 дней задержки

**Что:** .hbk — закрытый бинарный формат 1С. `onec_dtools` (Python) заброшен с 2017. Своя реализация рискована.

**Митигация:**
- **Plan A** — попытаться через `onec_dtools` (1-2 дня effort, если работает — отлично)
- **Plan B** — wrapper над BSL Language Server (он умеет читать .hbk внутри для type info)
- **Plan C (fallback)** — пропустить platform_hbk, оставить только v8std + ssl_api в RAG
- **Trigger:** если за 3 дня нет результата — Plan C

### 🟠 R3: CFE конфликтует с типовой УТ 11.5 / ERP 2.5

**Вероятность:** 40% | **Урон:** 1 неделя на каждый конфликт

**Что:** Расширение перехватывает методы типовых документов. На разных версиях УТ методы могут отличаться.

**Митигация:**
- Тестировать на 3 типовых конфигурациях с самого начала (Phase 13b.5)
- Минимизировать заимствование методов (только `ОбработкаПроведения` для трассировки)
- Использовать `&Перед` / `&После` вместо `&ИзменениеИКонтроль` (меньше риска)
- Список перехватываемых документов — **configurable** в настройках расширения (если ломается на ERP — отключаем для ERP)

### 🟠 R4: Multi-MCP routing запутывает LLM

**Вероятность:** 50% | **Урон:** деградация качества ответов

**Что:** LLM может неправильно выбирать MCP. Например, вопрос про ИТС → пытается вызвать `toolkit.execute_query` вместо `buddy.search_its`.

**Митигация:**
- Чёткие descriptions для каждого tool с примерами
- System prompt с явными правилами маршрутизации:
  > "Для вопросов по ИТС используй buddy.search_its. Для синтаксиса BSL — context.search. Для данных живой базы — toolkit.execute_query."
- A/B тестирование разных формулировок
- Логирование выбора tools — анализ паттернов ошибок

### 🟠 R5: RAG embeddings cost > $250

**Вероятность:** 20% | **Урон:** $200-500 дополнительно

**Что:** ssl_api может иметь не 3000 а 5000 методов (если парсер найдёт больше). .hbk может иметь не 5000 а 15000 entries.

**Митигация:**
- Дешёвая модель: `text-embedding-3-small` ($0.02/1M)
- Альтернативно: локальная модель `BAAI/bge-m3` (бесплатно, но требует GPU)
- Calibration на маленькой выборке (50 методов) → экстраполяция
- Cost monitoring per source

### 🟡 R6: BSL LS streaming через WebSocket — сложная реализация

**Вероятность:** 40% | **Урон:** 3 дня задержки

**Что:** Реактивная подсветка ошибок по мере stream от LLM — сложная синхронизация.

**Митигация:**
- **Plan A** — WebSocket + debounce 500ms
- **Plan B (fallback)** — диагностика после завершения stream (не live, но проще)
- **Plan C (минимум)** — диагностика по кнопке "Проверить код"

### 🟡 R7: Installer 250 MB — большой размер

**Вероятность:** 80% | **Урон:** UX неудобно качать

**Что:** Bundled JRE 17 (~80 MB) + Electron (~150 MB) + dependencies = 250+ MB.

**Митигация:**
- Postinstall download для BSL LS jar (113 MB) и MetaVision (50 MB)
- Минимальный installer ~250 MB (vs полный ~410 MB)
- Auto-update только delta (не полная переустановка)

### 🟡 R8: Capability spoofing

**Вероятность:** 5% | **Урон:** security incident

**Что:** Злонамеренное MCP может заявить capabilities которых нет, обмануть UI.

**Митигация:**
- Backend проверяет соответствие функциональности (`cfe.persistent_http` → реально HTTP сервис?)
- Логирование расхождений
- Warning badge в UI при подозрении
- Не критично т.к. всё локально

### 🟡 R9: D3 не тянет 5000+ узлов

**Вероятность:** 30% | **Урон:** UX лагает

**Что:** На больших конфигурациях (ERP 2.5 = 18k+ объектов) граф может быть огромным.

**Митигация:**
- WebGL renderer через sigma.js или react-force-graph
- Pagination/virtualization
- Фильтры по умолчанию (показывать только "интересные" узлы)
- Force simulation в Web Worker

### 🟡 R10: Параллельная разработка — мерж-конфликты

**Вероятность:** 40% | **Урон:** 1-2 дня на конфликт

**Что:** Phase 13b + Phase 14 параллельно — могут трогать общие файлы.

**Митигация:**
- Чёткое разделение по directories (`backend/app/services/cfe/` vs `backend/app/services/rag/`)
- Frontend code split (`components/cfe/` vs `components/rag/`)
- Daily sync если работают разные люди
- Feature branches с rebase разработка

### 🔵 R11: SmartScreen warning на installer без code-signing

**Вероятность:** 90% (без сертификата) | **Урон:** UX неудобно

**Что:** Windows покажет "Защитник Windows предотвратил запуск".

**Митигация:**
- Купить code-signing сертификат (~$300/год)
- Без сертификата — README с инструкцией "Подробнее → Выполнить в любом случае"

### 🔵 R12: Backend tests coverage < 80%

**Вероятность:** 30% | **Урон:** quality debt

**Что:** Множество новых сервисов — тяжело покрыть тестами полностью.

**Митигация:**
- Coverage gate в CI (`pytest --cov-fail-under=80`)
- Test pyramid: больше unit, меньше integration
- Mocking для MCP, BSL LS, MetaVision

## Контингенс-планы (Plan B для каждой фазы)

### Phase 12 Plan B
- Если Multi-MCP сложно — оставить single MCP с capability discovery (часть value)
- Sub-issue: Phase 12.3 (Orchestrator) — самая сложная

### Phase 13a Plan B
- Если EPF не запускается на старых платформах — minimum version 8.3.27

### Phase 13b Plan B
- Если CFE на ERP падает — выпустить только для УТ 11.5 первым
- ERP/КА в следующем релизе v2.0.5

### Phase 14 Plan B
- Если .hbk не получился — только v8std + ssl_api
- 60% от запланированного value

### Phase 15 Plan B
- Streaming WebSocket не работает → batch mode (после stream)
- 70% от запланированного UX

### Phase 16 Plan B
- MetaVision CLI не получился → GUI integration через "Открыть в MetaVision" кнопку
- 40% от запланированного value

### Phase 17/17b Plan B
- Если cards слишком сложны — упростить дизайн до minimal viable
- Активити стрим без детальной diff карточки

### Phase 18 Plan B
- Без auto-update — manual download
- Без code-signing — README

## Мониторинг рисков

В `.planning/STATE.md` ведём блок:

```markdown
## Active Risks

| ID | Status | Trigger | Plan B activated? |
|----|--------|---------|-------------------|
| R1 | Watching | Phase 16.1 > 7 days | No |
| R2 | Watching | Phase 14.4.2 > 3 days | No |
| R3 | Mitigating | Test on 3 typical | In progress |
| ... |
```

Обновляется еженедельно.
