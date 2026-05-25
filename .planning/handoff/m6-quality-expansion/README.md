# M6: Quality Expansion — Handoff Package

> Пакет проектирования milestone M6 для проекта **1С Аналитик** (`analyst-workspace-design`).
> Создан 2026-05-25 для передачи в другую сессию планирования.
> Цель: согласовать архитектуру + детали фаз + корректировки → запуск выполнения.

## TL;DR

**Цель M6:** превратить чат-консоль для аналитика 1С в полноценную аналитическую платформу с:

1. **5 MCP-серверов** одновременно (Multi-MCP Orchestration)
2. **2 режима работы с 1С**:
   - 🪶 **EPF Lite** — внешняя обработка (быстрый старт)
   - ⚡ **CFE Full** — расширение конфигурации (полный функционал)
3. **Capability-based UI** — модули автоматически активируются под доступные фичи
4. **Тройной RAG** — стандарты ИТС + БСП API + справка платформы
5. **BSL Language Server** в реальном времени для автопроверки кода
6. **MetaVision** граф вызовов функций
7. **Activity Stream + Posting Trace** карточки для CFE-режима

**Сроки:** 16 недель с параллелизацией (4 месяца), 19-22 без.
**Артефакты:** Electron installer + EPF + CFE расширение.

## 📂 Структура пакета

Читать в порядке:

| # | Файл | Что внутри | Время чтения |
|---|------|------------|---------------|
| 1 | [00-OVERVIEW.md](./00-OVERVIEW.md) | Что такое M6 в одну страницу | 3 мин |
| 2 | [01-ARCHITECTURE.md](./01-ARCHITECTURE.md) | Архитектурное решение + диаграммы + capability matrix | 10 мин |
| 3 | [02-PROTOCOL-AND-FLAGS.md](./02-PROTOCOL-AND-FLAGS.md) | MCP capability discovery + frontend feature flags | 8 мин |
| 4 | [03-DELIVERY-MODES.md](./03-DELIVERY-MODES.md) | EPF vs CFE детально + миграция + onboarding | 10 мин |
| 5 | [04-PHASES-PLAN.md](./04-PHASES-PLAN.md) | Все 8 фаз с декомпозицией | 25 мин |
| 6 | [05-TIMELINE-AND-PARALLELISM.md](./05-TIMELINE-AND-PARALLELISM.md) | Недели, параллелизация, критический путь | 5 мин |
| 7 | [06-RISKS-AND-MITIGATION.md](./06-RISKS-AND-MITIGATION.md) | 12 рисков с митигацией | 7 мин |
| 8 | [07-CODE-SKELETONS.md](./07-CODE-SKELETONS.md) | Backend + frontend код-скелеты для старта | 10 мин |
| 9 | [08-OPEN-QUESTIONS.md](./08-OPEN-QUESTIONS.md) | 7 вопросов требующих решения | 5 мин |
| 10 | [09-CURRENT-STATE.md](./09-CURRENT-STATE.md) | Что уже установлено локально и готово к использованию | 5 мин |

**Полное чтение:** ~80 минут.
**Critical path** (если время в обрез): README → 00 → 01 → 04 → 08 = ~45 минут.

## 🎯 Что от другой сессии

1. **Прочитать пакет** (или critical path)
2. **Дать корректировки** по архитектуре / фазам / приоритетам
3. **Ответить на 7 вопросов** из [08-OPEN-QUESTIONS.md](./08-OPEN-QUESTIONS.md)
4. **Согласовать timeline** — реалистичный для команды
5. **Дать "go"** — после чего я начинаю Phase 12

## 🔧 Что уже готово (не надо ставить заново)

В workspace `C:/CLOUDE_PR/`:

- ✅ **1c-buddy** запущен на :6002 (Python venv в `tools/1c-buddy/.venv/`)
  - Токен `ONEC_AI_TOKEN` сохранён в User env Windows
  - 8 MCP tools работают (ask_1c_ai, search_its, fetch_its, ...)
- ✅ **v8std** склонирован в `tools/v8std/` (317 стандартов в Markdown)
- ✅ **tools_ui_1c** склонирован в `tools/tools_ui_1c/` (1000⭐, 40+ tools, v25.2.1)
- ✅ **Connector** склонирован в `tools/Connector/` (v2.6.1, MIT)
- ✅ **MetaVision** склонирован + собран `tools/MetaVision/build/libs/MetaVisionFor1C-1.0.jar` (28.6 MB)
- ✅ **BSL LS 0.30.0-rc.2** jar скачан в `tools/bsl-language-server-0.30.0-rc.2-exec.jar` (113.7 MB)
- ✅ **БСП SSL 3.1.12.205 + 3.2.1.412** в `tools/ssl_3_1/`, `tools/ssl_3_2/`
- ✅ **JDK 17.0.19 + 21.0.11** в `tools/jdk-17/`, `tools/jdk-21/`
- ✅ **MCP Toolkit v1.7.0** EPF в `tools/MCP_Toolkit_v1.7.0.epf`
- ✅ **YAxUnit 25.12 + Vanessa 1.2.043.19** в `tools/yaxunit/`, `tools/vanessa-automation/`

См. [09-CURRENT-STATE.md](./09-CURRENT-STATE.md) для деталей.

## 📍 Контекст проекта

**Проект:** `analyst-workspace-design`
**GitHub:** https://github.com/nikitakhvorostov1912-beep/analyst-workspace-design (private)
**Локально:** `C:/CLOUDE_PR/projects/analyst-workspace-design/`
**Текущий milestone:** M5 — Post-v1.1 Expansion (~69% complete)
**Текущий релиз:** v1.4.5 (Electron installer)
**Стек:** Next.js 15 + React 19 + Tailwind 4 + FastAPI + Pydantic v2 + SQLite + Electron

## 🚦 Ключевые архитектурные запреты (НЕ нарушать)

Из `CLAUDE.md` и `.claude/rules/design-bans.md`:

- ❌ Никаких "work-modes" Discovery/Triage/Investigate/Mapping/Knowledge
- ❌ Никакого Object-IDE с tree метаданных слева
- ❌ Никакого AI right-rail с "инсайтами"
- ❌ Inter font, purple-cyan gradients, glass morphism — запрет
- ❌ Mobile-first — запрет (desktop only, ≥ 1280px)
- ❌ 8 экранов wizard (max 4)

✅ **Можно:** chat-first layout, inline cards, collapsible trace, channel selector, anonymization toggle, streaming stages.

## 📞 Контакт

После проработки в другой сессии — вернуться сюда с:
- Список корректировок к фазам
- Ответы на 7 open questions
- Финальный timeline
- "Go" — начинаем Phase 12

---

**Авторство:** собрано Claude Code в сессии 2026-05-25 на основе:
- 33 deep-researcher агентов (3 волны ресерча 2026-05-24)
- Существующих документов проекта (CLAUDE.md, ARCHITECTURE.md, REQUIREMENTS.md, ROADMAP.md, .planning/STATE.md)
- Локально установленных инструментов (см. CURRENT-STATE)
- Архитектурных запретов из .claude/rules/design-bans.md
