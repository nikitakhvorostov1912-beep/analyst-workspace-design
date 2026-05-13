# Handoff в Claude Design (claude.ai/design)

**Что отправляем:** концепт H2 (Object-centric IDE + AI right-rail) аналитика 1С.
**Стек реализации:** Next.js 15 + shadcn/ui + Tailwind 4, тёмная тема, русский UI.
**Цель:** проработать функционал и визуальный язык до уровня Claude Code-готового handoff bundle (.zip с tokens + компонентами).

---

## Что подключить в Claude Design как контекст

В порядке важности (если квота ограничена — берём топ-3):

1. **`mockups/v1/index.html`** — текущий HTML-макет с 6 экранами. **Главный референс структуры.** Загрузить как файл или ZIP, если поддерживает
2. **`docs/00b-mcp-capability-map.md`** — паспорт 10 MCP tools, чтобы Claude Design понимал какие данные есть в системе и какие операции возможны
3. **`docs/01-personas-jtbd.md`** — P1 Никита (опытный) + P2 Антон (внедренец), для понимания density vs onboarding
4. **`docs/03-information-architecture.md`** — 7 work-modes, data model, переходы между режимами
5. **`docs/04-concepts-3-alternatives.md`** — обоснование выбора H2 (концепт + 2 альтернативы для контекста)

---

## Промпт для первой сессии (копировать целиком)

```text
Создай design system + 6 ключевых экранов для b2b-инструмента
"Аналитик 1С" — рабочее место бизнес-аналитика 1С на десктоп.

КОНТЕКСТ ПРОДУКТА
Пользователь — бизнес-аналитик 1С с 4+ годами опыта, работает над 4-6
проектами параллельно (разные клиенты, разные конфигурации УТ/КА/ERP).
Не пишет код руками — читает, проектирует, ставит задачи AI и
разработчикам. Работает 6-7 часов в день, тёмная тема обязательна,
русский UI, плотная информация (density-first, как Linear/Hex).

Под капотом — MCP Toolkit, прямой канал к живой базе 1С (10 операций:
get_metadata, execute_query, get_event_log, find_references_to_object,
get_object_by_link, execute_code, get_access_rights, get_bsl_syntax_help,
get_link_of_object, submit_for_deanonymization).

СТЕК
Next.js 15 + shadcn/ui + Tailwind 4. Тёмная тема by default.
Шрифты: подбери НЕ Inter — например, IBM Plex Sans + IBM Plex Mono,
или Geist Sans + Geist Mono, или Söhne (если есть аналог). Русский язык,
кириллица обязательна, шрифт должен её корректно поддерживать.

АРХИТЕКТУРА ИНТЕРФЕЙСА (концепт H2: Object-centric IDE + AI right-rail)

Persistent shell:
— Top bar (48px): project switcher с pulse-индикатором подключения MCP,
  channel selector (prod/dev/staging — для multi-tenant), статус MCP-соединения,
  toggle анонимизации данных (для безопасной отправки в LLM), Cmd-K
— Left rail (узкая, 56px): иконки 6 work-modes + bookmark / history внизу
— Main area: меняется по mode
— AI right-rail (320px): контекстный AI-чат, видит текущий объект/экран
— Bottom strip (24px): live journal tail с последней значимой ошибкой

6 РЕЖИМОВ РАБОТЫ (КАЖДЫЙ — ОТДЕЛЬНЫЙ ЭКРАН)

1. DISCOVERY — карта незнакомой базы клиента
   • 4 summary-cards (Справочники 265, Документы 27, Регистры 150, Расширения 5)
   • Heatmap активности за 30 дней (топ-10 типов документов по числу созданий)
   • Auto-check ловушек конфигурации (например для УТ 11.5: дубли ГТД,
     перехваты ПередЗаписью без проверки IsNew)
   • Карточка "что я делал недавно" (timeline 4 последних сессий)

2. OBJECT WORKSPACE — карточка одного объекта (Документ / Справочник / Регистр)
   • Header с типом + признаком расширения + бейджем проблем
   • Tabs: Реквизиты / Табличные части / Где используется / Журнал /
     Права / Код модулей
   • Таблица реквизитов с метриками "заполнено N/M" и подсветкой проблем
     (type-mismatch, опечатки в именах, низкое покрытие)
   • Активность за 30 дней (sparkline) + связанные объекты (find_references)

3. TRIAGE — расследование инцидента
   • Список инцидентов слева (CRITICAL / HIGH / MEDIUM)
   • Главный экран: confidence bar (95% / 85% / ...) + цепочка доказательств
     (4 шага: Симптом → Журнал → Код → Repro), каждый шаг в карточке
   • Готовая handoff-карточка для разработчика (markdown + Telegram + KB)

4. INVESTIGATE — drill-down notebook
   • Левая панель: список ноутбуков (один = одно расследование цифры)
   • Главный: ячейки (Question → Query → Result/Chart → AI Explain TL;DR)
   • Drill-down: click на ячейку результата → новая ячейка с фильтром

5. MAPPING — wizard загрузки CSV/Excel/API → документы 1С
   • Stepper из 3 шагов: Файл → Маппинг → Dry-run & Apply
   • Mapping table с подсветкой type-mismatch (КРИТИЧНО: type-mismatch
     должен блокировать Apply и предупреждать о повторении прошлых багов)
   • Dry-run prediction: 4 метрики (создано / обновлено / конфликтов / ошибок)

6. KNOWLEDGE — база заметок и ловушек
   • Левая панель: фильтры по конфигурациям / темам / проектам
   • Главный: grid карточек заметок (P-007, P-012, REF, METH, TPL — категории)
   • Каждая карточка: бейдж типа + теги + краткое описание + cross-references
   • Cross-project AI-insight внизу: "ты сейчас работаешь над X, аналогичный
     случай был в проекте Y"

ОСОБЫЕ МОМЕНТЫ

• Cmd-K palette — глобальный поиск: объекты / действия / проекты. Открывается
  по ⌘K, закрывается ESC. Show keyboard shortcuts (⌘1-6 для work-modes).

• AI right-rail должен МЕНЯТЬСЯ в зависимости от контекста:
  — Discovery → инсайты по базе ("32 ОПП без шапки — расследовать?")
  — Object → подсказки по объекту ("найти где код заполняет реквизит X")
  — Triage → co-pilot расследования ("похожий инцидент был 2 недели назад")

• Состояния: MCP disconnected (красный pulse + retry), Loading skeletons
  для metadata cache, Empty state для нового проекта без подключения,
  Error при type-mismatch в Mapping.

• Микро-взаимодействия: hover на строке таблицы → подсветка + tooltip с
  быстрыми действиями (open / find references / copy link). Click на цифру
  в Investigate → expansion в новую ячейку.

REFERENCE (двойной, для anti-slop)
Linear × Cursor × Hex — technical, dense, dark, monospace-heavy where data.
НЕ Stripe, НЕ Vercel landing, НЕ generic SaaS dashboard.

AVOID
— Inter font (overused)
— Purple-to-cyan gradients (текущая итерация использует это, нужно уйти)
— Glass morphism / blur effects
— Centered hero с 64pt heading и двумя CTA
— Light theme как опция (только тёмная)
— Generic "AI-powered" labels везде
— Decorative emoji в кнопках (✨ 🚀 ⚡) — это инструмент для работы, не для эмоций
— Mobile-first вёрстка (это инструмент аналитика, минимум 1280px ширина)

PRIORITY DELIVERABLES
1. Design tokens (colors / typography / spacing / radius / shadows)
2. AppShell с persistent shell (top bar + left rail + right rail + bottom strip)
3. 6 экранов работы (Discovery / Object / Triage / Investigate / Mapping / Knowledge)
4. Cmd-K palette
5. 3-4 ключевых состояния (MCP disconnected, Loading, Empty, Error)

Целевое разрешение: 1440×900 минимум. Тёмная тема. Русский UI.
```

---

## После handoff из Claude Design

Когда Claude Design отдаст bundle (ссылка `api.anthropic.com/v1/design/h/<hash>` или ZIP):

```bash
/from-design <ссылка-или-путь-к-zip>
```

Этот скилл (`design:design-handoff`) распакует tokens, компоненты, ассеты и применит к проекту. После — `frontend-design` + `nextjs-patterns` для реализации.

---

## Если квота Claude Design кончится

Не теряем сессию впустую — **Tweaks panel НЕ ест chat-токены**. Используем для тонкой настройки (цвета, типографика, spacing) после получения первой версии.

Если структура нужна радикально другая — лучше "Save and try completely different" reset, чем длинная цепочка правок.

---

## Что я (Claude Code) сделаю, когда вернётся handoff bundle

1. Применить tokens (colors / typography) в `tailwind.config` или `app/globals.css`
2. Перенести структуру компонентов в `app/components/`
3. Прокинуть данные из MCP Toolkit через FastAPI proxy → Next.js Server Components
4. Реализовать NL→query подсказчик (Claude API + контекст metadata)
5. Подключить SQLite для кэша metadata + заметок + incidents
