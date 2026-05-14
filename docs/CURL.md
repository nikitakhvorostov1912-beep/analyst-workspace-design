# Скопировать как curl — формат и использование

## Что делает эта кнопка

В панели trace (разворачивается кликом на «N инструментов, X мс»)
рядом с каждым вызовом инструмента есть кнопка **Скопировать как curl**.

Нажатие формирует HTTP-команду для прямого вызова того же инструмента
через MCP-протокол и копирует её в буфер обмена.

---

## Формат команды

```bash
curl -X POST '<mcp_endpoint>' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"<tool_name>","arguments":{...}}}'
```

Если активное MCP-подключение определено, `<mcp_endpoint>` заменяется
реальным URL (например `http://localhost:6010/mcp`).
Если нет — подставляется плейсхолдер `<MCP_ENDPOINT>` — замените его вручную.

---

## Пример

Для вызова инструмента `execute_query` с аргументом `{"query":"ВЫБРАТЬ ПЕРВЫЕ 5 Ссылка ИЗ Документ.РеализацияТоваровУслуг"}`:

```bash
curl -X POST 'http://localhost:6010/mcp' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"execute_query","arguments":{"query":"ВЫБРАТЬ ПЕРВЫЕ 5 Ссылка ИЗ Документ.РеализацияТоваровУслуг"}}}'
```

---

## Как использовать

1. Нажать кнопку **Скопировать как curl** в строке нужного tool call
2. Вставить в терминал (Ctrl+V / Cmd+V)
3. Если в команде `<MCP_ENDPOINT>` — заменить на реальный URL вашего MCP Toolkit
4. Перед вызовом `tools/call` MCP требует инициализацию сессии:

```bash
# Шаг 1: инициализация (один раз, получаем Mcp-Session-Id)
curl -X POST 'http://localhost:6010/mcp' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}' \
  -i  # выводим заголовки

# Из заголовка ответа забираем Mcp-Session-Id: <id>

# Шаг 2: вызов tool с сессионным id
curl -X POST 'http://localhost:6010/mcp' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: <id-из-шага-1>' \
  -d '...'
```

---

## Известное ограничение

Кнопка **не включает** `Mcp-Session-Id` в curl-команду.

Причина: MCP-сессия создаётся внутри backend при каждом `/chat` запросе
и не передаётся на фронтенд. Фронтенд видит только аргументы tool call,
но не сессионный id MCP.

Для воспроизведения вызова вручную — сначала выполните `initialize`
(шаг 1 выше) чтобы получить свой `Mcp-Session-Id`.
