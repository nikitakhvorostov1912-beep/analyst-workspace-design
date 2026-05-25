# 00 — Overview: что такое M6

## Одна фраза

Превращаем чат-консоль для аналитика 1С в платформу с двумя режимами интеграции (EPF/CFE), пятью MCP-серверами, тройным RAG-источником, автоматической проверкой BSL и графом вызовов функций.

## Зачем

Сейчас (v1.4.5):
- Один MCP — наш MCP Toolkit
- LLM работает только с тем, что отдаёт Toolkit
- Чат-первый UX отлично, но **глубины 1С** не хватает
- Нет автопроверки кода
- Нет визуализации архитектуры
- Нет цитирования стандартов

После M6 (v2.0):
- 5 MCP параллельно (Toolkit, 1c-buddy, mcp-bsl-context, METR, EDT-MCP)
- 2 режима 1С-интеграции:
  - **EPF** — quick start без доработки конфигурации
  - **CFE** — постоянный сервис + подписки на события + регламентные задания + HMAC SSO
- LLM **сама** выбирает нужный MCP под вопрос
- Цитаты из ИТС + БСП + справки платформы в каждом ответе с кодом
- BSL LS подсвечивает ошибки в коде LLM в реальном времени
- Графы вызовов через MetaVision для понимания архитектуры

## Что для пользователя меняется

**Раньше:**
> Аналитик: «Найди медленные запросы»
> LLM: запрос → таблица. **Конец.**

**После M6:**
> Аналитик: «Найди медленные запросы»
> LLM: вызов `toolkit.get_event_log` → 12 запросов > 1 сек
> + RAG: цитирование СтРД-145 («запросы в виртуальных таблицах») и `ОбщегоНазначения.ЗначенияРеквизитовОбъекта` (БСП-метод)
> + BSL LS: на одной из найденных функций — 3 warnings
> + 1c-buddy: ссылка на статью ИТС «Производительность виртуальных таблиц»
> + кнопка «Граф вызовов» → MetaVision рисует кто вызывает эту функцию
> + если CFE — Activity Stream показывает что эта функция вызывалась 47 раз за последний час

## Что НЕ меняется

- Chat-first UX (никаких work-modes)
- Inline cards в потоке сообщений
- Stencil/Mono brand (Signal #FF6A3D)
- Multi-tenant через channel selector
- SSE streaming с stage indicators
- Backend API (zero breaking changes для существующих сессий)

## 8 фаз M6 (за 16 недель)

| Phase | Что | Срок |
|-------|-----|------|
| 12 | Multi-MCP Orchestration + Capability Discovery | 2 нед |
| 13a | Аналитик Lite (EPF) | 2 нед |
| 13b | АналитикПлюс (CFE) | 3 нед |
| 14 | Тройной RAG (v8std + БСП + .hbk) | 3 нед |
| 15 | BSL LS + streaming diagnostics | 2 нед |
| 16 | MetaVision граф (форк + CLI + D3) | 4 нед |
| 17 | Cards + UX + feature gates | 2 нед |
| 17b | Activity Stream + Posting Trace (CFE-only) | 1 нед |
| 18 | Distribution v2.0 (Electron + EPF + CFE installers) | 1.5 нед |

С параллелизацией 13b+14, 16+17, итого **16 недель**.

## Ключевые архитектурные решения

1. **Capability-based UI** — все модули frontend регистрируются под capabilities, MCP сам сообщает свои возможности через `experimental.analyst-1c.features` в `initialize`.
2. **23 capabilities** — 8 базовых (EPF), +15 расширенных (CFE).
3. **MCP Orchestrator** — backend паттерн с unified tool registry (`toolkit.X`, `buddy.Y`, ...).
4. **Тройной RAG** — sqlite-vec для v8std (317 стандартов) + ssl_api (~3000 БСП методов) + platform_hbk (.hbk файл с локальной платформы).
5. **Streaming BSL LS** — параллельный subprocess к LLM stream, WebSocket для live diagnostics.
6. **MetaVision fork** — собственный fork с CLI режимом для headless анализа.

## Что готово локально к старту (не надо ставить)

- 1c-buddy запущен на :6002, токен ИТС сохранён
- v8std, tools_ui_1c, Connector, MetaVision, BSL LS jar — в `tools/`
- БСП 3.1.12 + 3.2.1 исходники для индексации
- JDK 17 + 21 для BSL LS и MetaVision

См. [09-CURRENT-STATE.md](./09-CURRENT-STATE.md).

## Артефакты M6 для пользователя

Конечный пользователь получает **3 файла + 1 опцию**:

1. `analyst-setup-v2.0.0.exe` — Electron installer (~250 MB)
2. `АналитикLite.epf` — внешняя обработка для quick start (~3 MB)
3. `АналитикПлюс.cfe` — расширение конфигурации (~8 MB)
4. `Install-АналитикПлюс.ps1` — installer-скрипт для CFE

Аналитик выбирает: EPF для одноразового аудита **ИЛИ** CFE для постоянного использования. **Может переключаться без потери истории сессий.**
