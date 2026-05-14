# REST API — 1С Аналитик

**Интерактивная документация (Swagger UI):** http://localhost:8010/docs

**Экспорт OpenAPI JSON:**
```bash
curl http://localhost:8010/openapi.json > openapi.json
```

---

## Endpoints

### Health

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Статус backend + SQLite. Возвращает `{status, version, db}` |

### Chat (SSE)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/chat` | Отправить сообщение, получить SSE-поток событий. Требует заголовки X-LLM-API-Key, X-LLM-Endpoint, X-LLM-Model |
| POST | `/chat/confirm` | Подтвердить или отменить выполнение опасного execute_code (SEC-01). Body: `{tool_call_id, approved}` |

### Sessions

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/sessions` | Список сессий, сгруппированных по дате (today/yesterday/this_week/earlier). Query: `channel_id` |
| POST | `/sessions` | Создать новую сессию. Body: `{channel_id, title?}` |
| GET | `/sessions/{id}` | Детали сессии. 404 если не найдена |
| PATCH | `/sessions/{id}` | Переименовать сессию. Body: `{title}` |
| DELETE | `/sessions/{id}` | Удалить сессию и все её сообщения (CASCADE). 204 при успехе |
| GET | `/sessions/{id}/messages` | Все сообщения сессии в хронологическом порядке |

### Connections (MCP endpoints)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/connections` | Список MCP-подключений |
| POST | `/connections` | Создать подключение. Body: `{name, endpoint, channel?, anon_enabled?}` |
| PUT | `/connections/{id}` | Обновить подключение (полная замена). Body: `{name?, endpoint?, channel?, anon_enabled?}` |
| DELETE | `/connections/{id}` | Удалить подключение. 204 при успехе |
| POST | `/connections/{id}/ping` | Пинговать MCP endpoint, обновить last_seen_at. Возвращает `{mcp_version, tool_count, session_id, duration_ms}` |

### LogCard Load-More

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/sessions/{sid}/messages/{mid}/cards/{cid}/load-more` | Загрузить следующую страницу LogCard. Body: `{cursor}` |

### MCP Proxy (legacy)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/mcp/_/ping` | Пингует любой MCP endpoint по query-параметру `endpoint=`. Для диагностики |

---

## SSE Events Matrix

Поток POST /chat возвращает события в формате `event: <name>\ndata: <json>\n\n`.

| Event | Payload | Описание |
|-------|---------|----------|
| `status` | `{stage: "thinking" \| "calling_tool" \| "formatting"}` | Стадия обработки запроса |
| `tool_call` | `{id, name, args}` | LLM решила вызвать инструмент |
| `tool_result` | `{id, ok, result, error, duration_ms}` | Результат вызова инструмента |
| `delta` | `{content: string}` | Фрагмент текстового ответа LLM |
| `card` | `{type: "table"\|"object"\|"log", payload: {...}}` | Inline-карточка |
| `done` | `{message_id, total_duration_ms}` | Стрим завершён, message сохранён в БД |
| `error` | `{message, code: ErrorCode, retry_after_s?}` | Ошибка — стрим закрывается после этого события |
| `confirm_required` | `{tool_call_id, name, args, reason}` | Требуется подтверждение execute_code (SEC-01) |

**Итого:** 8 событий.

---

## Error Codes

| Код | Описание |
|-----|----------|
| `llm_rate_limit` | LLM вернула 429, превышен лимит запросов |
| `llm_invalid_key` | LLM вернула 401/403, неверный API ключ |
| `llm_network_error` | Сетевая ошибка при обращении к LLM |
| `llm_server_error` | LLM вернула 5xx |
| `mcp_disconnected` | MCP Toolkit недоступен или потерял соединение |
| `mcp_connect_error` | Ошибка при инициализации MCP соединения |
| `tool_loop_limit` | Превышен лимит вызовов инструментов (10) |
| `unknown_channel` | channel_id не найден в mcp_connections |
| `init_error` | Внутренняя ошибка при инициализации loop |
| `internal_error` | Непредвиденная ошибка обработки |
| `user_declined` | Пользователь отменил выполнение execute_code |
| `dangerous_keyword_blocked` | execute_code не подтверждён за таймаут |

**Итого:** 12 ErrorCode.

---

## Аутентификация

**Отсутствует (MVP single-user).** В v2 планируется OAuth / API tokens.

LLM API ключ передаётся через заголовок `X-LLM-API-Key` при каждом `/chat` запросе.
Backend форвардит его к LLM-провайдеру и не хранит.

---

## Примеры

**Отправить сообщение:**
```bash
curl -X POST http://localhost:8010/chat \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -H 'X-LLM-API-Key: sk-...' \
  -H 'X-LLM-Endpoint: https://api.openai.com/v1' \
  -H 'X-LLM-Model: gpt-4o' \
  -d '{"message": "Покажи 5 документов реализации", "channel_id": "conn-uuid-here"}'
```

**Создать подключение:**
```bash
curl -X POST http://localhost:8010/connections \
  -H 'Content-Type: application/json' \
  -d '{"name": "Транзит Local", "endpoint": "http://localhost:6010/mcp"}'
```

**Load-more LogCard:**
```bash
curl -X POST http://localhost:8010/sessions/{sid}/messages/{mid}/cards/{cid}/load-more \
  -H 'Content-Type: application/json' \
  -d '{"cursor": "eyJsaW1pdCI6NTAsIm9mZnNldCI6NTB9"}'
```
