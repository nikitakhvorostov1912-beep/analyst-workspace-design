# MCP Integration Intel

**Source:** 1С MCP Toolkit v1.7.0 docs + capability map.

## Connection

- **Transport:** Streamable HTTP (`http://localhost:6010/mcp`)
- **Protocol:** JSON-RPC 2.0 over HTTP + SSE для streaming responses
- **Session:** `Mcp-Session-Id` header после `initialize`
- **Channel multiplexing:** `?channel=<id>` query param для multi-tenant

## Initialize Flow

```
POST /mcp
Body: {"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
Response headers: Mcp-Session-Id: <uuid>
Response body: {"jsonrpc":"2.0","id":1,"result":{...}}

→ store Mcp-Session-Id для последующих вызовов
```

## Tools Discovery

```
POST /mcp (с Mcp-Session-Id header)
Body: {"jsonrpc":"2.0","id":2,"method":"tools/list"}
Response: {"jsonrpc":"2.0","id":2,"result":{"tools":[{...},...]}}

→ конвертим в OpenAI function calling schema:
{
  "type": "function",
  "function": {
    "name": "get_metadata",
    "description": "...",
    "parameters": {
      "type": "object",
      "properties": {...}
    }
  }
}
```

## Tool Invocation

```
POST /mcp (с Mcp-Session-Id header)
Body: {
  "jsonrpc":"2.0",
  "id":3,
  "method":"tools/call",
  "params": {
    "name":"execute_query",
    "arguments": {"query":"ВЫБРАТЬ ...","limit":100}
  }
}
Response: {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"<JSON>"}]}}

→ парсим content[0].text как JSON для structured result
```

## 10 Tools (overview)

| Tool | Purpose | Required Params |
|------|---------|-----------------|
| `get_metadata` | Структура базы (summary/list/detail/attribute_search) | optional `mode`, `filter`, `meta_type`, `name_mask` |
| `execute_query` | Запрос 1С (язык запросов) | `query`, optional `params`, `limit`, `include_schema` |
| `execute_code` | Произвольный BSL | `code`, optional `execution_context` (server/client) |
| `get_object_by_link` | Объект по навигационной ссылке | `link` (e1cib/data/...) |
| `get_link_of_object` | Обратное: object_description → link | `object_description` |
| `find_references_to_object` | Где используется объект | `target_object_description`, `search_scope` |
| `get_access_rights` | Права роли/юзера на объект | `metadata_object`, optional `user_name` |
| `get_event_log` | Журнал регистрации с фильтрами | optional 13 filters |
| `get_bsl_syntax_help` | Справочник BSL | `keywords`, optional `match`/`limit` |
| `submit_for_deanonymization` | Финал для разанонимизации | `text` |

## Special Considerations

### Dangerous Keywords
`execute_code` блокирует ключевые слова по умолчанию:
- Удалить / Записать / УстановитьПривилегированныйРежим / COMОбъект / ...

Можно разрешить через `ALLOW_DANGEROUS_WITH_APPROVAL=true` в MCP server config — тогда server вернёт `requires_approval=true` и ждёт user confirm в 1С UI.

В нашем UI: всегда показывать confirm dialog перед вызовом execute_code (security defence-in-depth).

### Anonymization
Опционально на стороне MCP Toolkit. Когда включено:
- Реальные значения заменяются токенами `[ORG-001]`, `[INN-001]`, `[PER-001]`
- LLM получает токенизированные данные → безопасно отправлять
- Финальный ответ можно «раскрыть» через `submit_for_deanonymization`

### TOON Format
MCP Toolkit поддерживает TOON (Token-Oriented Object Notation) для таблиц — 3-5× меньше токенов чем JSON. Опц. для будущих оптимизаций.

### Channel Isolation
Один MCP server может обслуживать несколько 1С баз через `?channel=<id>`. Для нашего UI:
- Один MCP connection record в DB = (endpoint, channel)
- Изоляция tools schemas per-channel (могут отличаться если разные конфигурации)

## References

- Full reference: `tools/1c-mcp-toolkit-proxy/skills/calling-1c-rest-api-via-curl/references/tools-full-reference.md`
- Capability map: `docs/00b-mcp-capability-map.md`
- Embedded server: `tools/1c-mcp-toolkit-proxy/README.md`
