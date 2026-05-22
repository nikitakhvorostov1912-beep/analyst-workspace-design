# Идеи для развития — 1С Аналитик

> Папка со всеми наработками на будущее. Накапливается, не удаляется. Каждый файл — фотография мысли на конкретную дату.

## Что внутри

### `IDEAS-FROM-STACK-2026-05-21.md` (≈25 KB)

**Тема:** что взять в проект из общего стека `C:/CLOUDE_PR/` после deep research'а 1С-AI экосистемы.

**Главное:**
- БСП исходники (`tools/ssl_3_2/`, `ssl_3_1/`, CC-BY-4.0) как corpus для Phase 10 RAG
- 25 готовых промпт-шаблонов из `.claude/skills/1c-prompt-library/`
- Read-only MCP канал через feenlace/mcp-1c v1.6.6 для prod-баз
- Configuration detector УТ/ERP/КА/БГУ → tailored system prompts
- 5 новых типов карточек: Citation / Workflow (Mermaid) / Graph / Schema / Comparison
- Bundled offline knowledge (БСП subset, prompts, cheatsheets)

**Карта приоритетов:** M6 → M7 → M8 → M9+

### `IDEAS-ADDENDUM-2026-05-21.md` (≈55 KB)

**Тема:** что первый файл пропустил — failure modes, 152-ФЗ, технический долг, конкретные библиотеки.

**Главное:**
- **4 P0 failure modes** до v1.3.0: infinite loop ($16-50k/ночь риск), API key в localStorage (XSS), 100k+ rows crash, prompt-to-SQL injection
- **152-ФЗ Compliance** (с 1 июля 2025): pivot MiMo → Cloud.ru Qwen3-Coder-480B (БЕСПЛАТНО, РФ-ДЦ), Presidio PII Shield, регистрация в реестре операторов ПД
- **5 BLOCKER текущего тех. долга** из UI-REVIEW-2026-05-21.md (47/100)
- **5 фич конкурентов** для копирования: Plan→Execute→Validate, Cells + Reactive Graph (Hex.tech), `/команды`, RAG-индексация при подключении, Telegram secondary UI
- **9 конкретных Python библиотек** + 6 frontend: Instructor, LiteLLM, Presidio, sqlparse, DeepEval, Langfuse, TanStack Virtual, Vercel AI SDK 6, Mermaid
- **Granular roadmap M7→M12+** (6 фаз вместо одного «M6+»)
- **Pricing с конкретными цифрами:** Соло 1 990₽ / Команда 3 900₽/seat / Enterprise custom
- **7 Open Questions** для решения пользователем

## Порядок чтения

1. Прочитай **IDEAS-FROM-STACK-2026-05-21.md** — общая картина «что есть в стеке»
2. Затем **IDEAS-ADDENDUM-2026-05-21.md** — критичные failure modes, 152-ФЗ, конкретные библиотеки
3. Прими решения по **7 Open Questions** в §15 ADDENDUM
4. Запусти `/gsd:new-milestone M7` (Production readiness P0 fixes) или другой milestone по решению

## Что нужно решить (Open Questions из ADDENDUM §15)

| # | Вопрос | Опции |
|---|---|---|
| 1 | Pivot MiMo → Cloud.ru Qwen3-Coder-480B как default LLM? | Pros: бесплатно + лучше на BSL + РФ-ДЦ. Cons: invasive migration |
| 2 | Cells + Reactive Graph (Hex-style) vs текущая линейная история? | Cells = уникальная фича. Линейная = проще |
| 3 | 152-ФЗ регистрация когда? | Сейчас (до v1.3.0) vs после первого PoC |
| 4 | Telegram bot как secondary UI? | Дополнительный канал vs фокус на Web |
| 5 | Plan→Execute→Validate видимый план — default или opt-in? | Безопаснее vs больше кликов |
| 6 | Eval golden pairs из Транзит-memory или синтетика? | Реальные кейсы vs контролируемая среда |
| 7 | Read-only MCP канал (feenlace/mcp-1c) добавить когда? | v1.3.x default vs M9+ |

## Правила работы с папкой

1. **Не удалять** старые файлы — это snapshot мысли на дату. История ценнее последней версии
2. **Новый файл = новая дата в имени** — `IDEAS-<тема>-YYYY-MM-DD.md`
3. **Обновлять этот README** при добавлении нового файла
4. **Связь с другими местами:**
   - GSD milestones в `.planning/ROADMAP.md` — куда переезжает идея после принятия
   - Hermes backlog в `.planning/phases/06-hermes/SPRINT-SUMMARY.md` — наши уже-принятые фичи
   - Memory `.claude/memory/open-questions.md` — синхронизировать с §15 ADDENDUM

## Связь с общим стеком Cloude_PR

Наши идеи опираются на research из общего workspace:

- `C:/CLOUDE_PR/.claude/research/1c-knowledge-roadmap-2026-05-21/` — общий 1С knowledge roadmap (БСП, OnesTemplates, RAG)
- `C:/CLOUDE_PR/.claude/research/ecosystem-deep-revision-2026-05-21/` — Phase 2 ecosystem revision (obra v5.1, mcp-1c v1.6.6)
- `C:/CLOUDE_PR/tools/` — склонированные репо для возможного использования (ssl_3_2, OnesTemplates, bsl-atlas, mdclasses, bsl-graph, rat)
- `C:/CLOUDE_PR/.claude/skills/1c-prompt-library/SKILL.md` — 25 промпт-шаблонов

## История папки

| Дата | Файл | Изменение |
|---|---|---|
| 2026-05-21 | `IDEAS-FROM-STACK-2026-05-21.md` | Создан — 10 категорий идей из общего стека |
| 2026-05-21 | `IDEAS-ADDENDUM-2026-05-21.md` | Создан — критичные пропуски: P0 failures, 152-ФЗ, тех. долг, библиотеки |
| 2026-05-21 | `README.md` (этот файл) | Создан — навигатор папки |
