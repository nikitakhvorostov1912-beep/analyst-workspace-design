# 08 · Copy Glossary

Единая терминологическая таблица. Используй при любых правках текста. Все термины слева — **запрещены** в пользовательском UI (исключение — раздел «Технические подробности» в Status и Guide).

---

## Главное правило

> **Пользователь — бизнес-аналитик 1С.** Он знает «базу», «контрагента», «документ», «склад», «регистр», «номенклатуру». Он **не знает** «endpoint», «channel», «tool call», «MCP», «BSL», «JSON».

---

## Таблица замен

| Технический термин | Контекст | Заменить на | Где применять |
|---|---|---|---|
| **MCP** | везде в UI | «обработка 1С» / «обработка-обработчик» | tooltips, labels, descriptions |
| **MCP_Toolkit** | в инструкциях | «обработка 1С» (если контекст общий) или **сохранить как имя файла** `MCP_Toolkit_v1.7.0.epf` (это конкретный поисковый запрос для аналитика, который кладёт файл в 1С) | Guide section |
| **MCP endpoint** | label | «адрес базы 1С» | Settings, Status |
| **endpoint** | label | «адрес» | везде |
| **channel** (UI label) | dropdown, label | «база 1С» (для conn) или «профиль» (для proxy) | UI labels |
| **channel** (поле API) | модель данных | **не менять** — это backend API контракт | TypeScript types, API calls |
| **tool / инструмент** | metric label, list label | «операция» / «обращение» / «запрос» | Insights labels |
| **tool calls** | KPI | «обращений к 1С» | Insights |
| **tool_call** | metric | «запрос» / «обращение» | Insights table |
| **Errors / Rate** | таблица | «Ошибок / % ошибок» | Insights |
| **endpoint URL** | технический | в expert-блок | Status |
| **BSL** | язык 1С | оставить как есть — это конкретное имя языка платформы | Guide (опционально) |
| **session** | UI | «чат» | везде |
| **обработка-обработчик** | существующее | оставить как есть | Settings, Guide |
| **embedded server** | технический | «встроенный сервер» | существующее, ok |
| **proxy** | технический | «прокси-шлюз» | существующее |

---

## Контекстные паттерны

### Insights labels

| До | После |
|---|---|
| Tool calls | Запросов к 1С |
| Average tool call time | Среднее время обращения к 1С |
| Top tools | Что чаще всего спрашивают |
| Top channels | Топ баз 1С |
| Calls (column) | Запросов |
| Errors (column) | Ошибок |
| Rate (column) | % ошибок |
| Channel (column) | База |

### Status labels

| До | После |
|---|---|
| Канал | (убрать в expert-блок) |
| Версия MCP | (убрать в expert-блок) |
| Сервер MCP | (убрать в expert-блок) |
| обработка MCP_Toolkit | обработка-обработчик |
| канал «X» | профиль «X» (только в expert) |

### Settings labels

| До | После |
|---|---|
| Канал (label поля) | Профиль (для прокси) |
| Имя канала | Идентификатор профиля |
| Тот же номер, что введён в MCP_Toolkit | Тот же номер, что в обработке 1С |
| MCP_Toolkit_v1.7.0.epf | сохранить как есть (имя файла) |

### Toast / Error messages

| До | После |
|---|---|
| «Сначала сохраните, потом тестируйте» | «Сохраните подключение, чтобы можно было его проверить» (через tooltip, не toast) |
| «Запустите docker compose up» | «Серверная часть не отвечает. Попробуйте перезагрузить страницу или открыть Диагностику.» |
| «инструменты MCP» | «инструменты в 1С» / «операции в 1С» |
| «10 инструментов MCP Toolkit» | «10 операций над базой 1С» |
| «обычно 10 у MCP Toolkit» | «обычно 10 операций» |

### Streaming stage labels

Уже **частично сделано** в `StreamingStages.tsx:53-78` (`TOOL_LABELS`). Сверь, что ВСЕ tool_name из `frontend/lib/mcp-tool-descriptions.ts` имеют русские лейблы. Если что-то осталось — добавь.

### Onboarding labels

| До | После |
|---|---|
| Обучение (step label) | Память |
| Обучение на ваших чатах | Память по этой базе |
| Когда функция будет готова... | Опция сохранена. Когда обучение запустится... |

### Channel selector

| До | После |
|---|---|
| Выбор канала (aria) | Выбор базы 1С |
| Канал (DropdownMenuLabel) | Базы 1С |
| Канал: tranzit-prod | (убрать) |

---

## Полный grep-checklist

Когда правишь — прогоняй:

```bash
# Поиск оставшейся технической терминологии
rg -i 'tool[_ ]?call' frontend/app frontend/components --type tsx
rg -i 'mcp[_ ]toolkit' frontend/app frontend/components --type tsx | grep -v '.epf'
rg -i 'endpoint' frontend/app frontend/components --type tsx
rg 'Канал' frontend/app frontend/components --type tsx
rg 'channels' frontend/app frontend/components --type tsx --type ts
```

Каждое попадание — должно быть либо:
1. Заменено на термин из таблицы выше
2. Перемещено в expert-блок (`<details>` с лейблом «Для разработчика»)
3. Является именем поля API/модели — **не трогать**

---

## Что точно оставить как есть

- Имена файлов: `MCP_Toolkit_v1.7.0.epf` — это конкретный артефакт, аналитик его ищет в проводнике
- Имена полей в TS interfaces: `channel`, `endpoint`, `tool_calls` — это API контракт
- Тесты в `e2e/` — могут содержать технические термины (это не пользовательский UI)
- `frontend/lib/mcp-tool-descriptions.ts` — внутренняя документация для разработчика
- Внутренние комментарии в коде
- `.brand/`, `.planning/`, `.claude/` — служебные файлы

---

## Acceptance

После прогона — на видимых страницах (welcome, chat, settings, status, insights, about, guide) **не должно встречаться слов**: `MCP`, `endpoint`, `tool call`, `Канал` (как label), `channel`. Кроме разделов:
- `<details>Технические подробности (для разработчика)</details>` в Status
- В Guide — отдельная секция «Для системного администратора»
- About — может остаться 1 упоминание в перечне технологий
