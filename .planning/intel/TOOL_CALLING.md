# LLM Tool Calling Intel

**Source:** OpenAI Chat Completions API spec + Xiaomi MiMo docs (assumed OpenAI-compatible).

## Function Calling Flow

```
Request:
  POST /v1/chat/completions
  Body: {
    "model": "mimo-32b",
    "messages": [
      {"role":"system","content":"Ты — помощник 1С аналитика..."},
      {"role":"user","content":"покажи документы ОПП за вчера"}
    ],
    "tools": [
      {"type":"function","function":{"name":"execute_query","description":"...","parameters":{...}}},
      {"type":"function","function":{"name":"get_metadata","description":"...","parameters":{...}}},
      ...
    ],
    "stream": true,
    "temperature": 0.3
  }

Response (streaming):
  data: {"choices":[{"delta":{"role":"assistant"}}]}
  data: {"choices":[{"delta":{"tool_calls":[{"id":"call_1","type":"function","function":{"name":"execute_query","arguments":""}}]}}]}
  data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"qu"}}]}}]}
  ...
  data: {"choices":[{"finish_reason":"tool_calls"}]}
  data: [DONE]
```

## Orchestrator Loop

```python
messages = [system, user_msg]
while True:
    response = await llm.chat.completions.create(
        model=settings.model,
        messages=messages,
        tools=mcp_tools_schema,
        stream=True,
    )
    
    accumulated_tool_calls = []
    accumulated_content = ""
    
    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta.content:
            yield SSE("delta", {"content": delta.content})
            accumulated_content += delta.content
        if delta.tool_calls:
            # merge into accumulated_tool_calls by index
            ...
        if chunk.choices[0].finish_reason == "stop":
            yield SSE("done", {})
            break
        if chunk.choices[0].finish_reason == "tool_calls":
            messages.append({"role":"assistant","tool_calls": accumulated_tool_calls})
            for tc in accumulated_tool_calls:
                yield SSE("tool_call", {"name": tc.function.name, "args": json.loads(tc.function.arguments)})
                result = await mcp.call_tool(tc.function.name, json.loads(tc.function.arguments))
                yield SSE("tool_result", {"call_id": tc.id, "result": result})
                messages.append({"role":"tool","tool_call_id":tc.id,"content":json.dumps(result)})
            break  # break inner async for, outer while loop will re-invoke LLM
    
    if not accumulated_tool_calls:
        break  # natural completion
```

## Card Detection

После завершения LLM-цикла, парсер ищет в финальном ответе блоки структурированных данных. Два подхода:

### Approach A: Markdown code blocks
```markdown
Нашёл 32 документа:

\`\`\`card-table
{
  "title": "ОПП без шапки за 30.04",
  "columns": ["Ссылка","Дата","Декларант","ОсновноеТС"],
  "rows": [...]
}
\`\`\`
```

LLM учится этот формат через system prompt + few-shot examples.

### Approach B: Из tool_result автоматически
- `execute_query` result → TableCard auto-генерация
- `get_event_log` result → LogCard auto-генерация
- `get_metadata(filter, sections)` result → ObjectCard auto-генерация
- `find_references_to_object` result → ReferencesCard auto-генерация

**Recommended:** Approach B как primary (детерминированно), Approach A как fallback для случаев когда LLM хочет кастомное представление.

## System Prompt (draft)

```
Ты — экспертный AI-ассистент для бизнес-аналитика 1С. Аналитик работает с базой 1С через MCP Toolkit. У тебя есть доступ к 10 операциям 1С (см. tools).

Правила:
1. Отвечай на русском.
2. Когда видишь вопрос про данные 1С — вызывай нужные tools. Не выдумывай.
3. Перед сложными запросами execute_query — сначала get_metadata чтобы узнать структуру.
4. Дай TL;DR в 1-2 абзаца + раскрой детали при необходимости.
5. Опасные операции (execute_code с записью/удалением) — НИКОГДА без явного запроса пользователя.
6. При ошибке tool — объясни читаемо, предложи альтернативу.

Контекст текущей базы: {channel_name}
Имя конфигурации: {config_name}
Активные расширения: {extensions_list}
```

## Compatibility Notes

| LLM | Function Calling | Streaming | Notes |
|-----|------------------|-----------|-------|
| Xiaomi MiMo | TBD (нужно проверить) | TBD | OpenAI-совместимый формат `sk-...` ключа |
| DeepSeek V3 | Yes (OpenAI format) | Yes | Хорошо работает с tools |
| OpenAI GPT-4o/4.1 | Yes (native) | Yes | Reference implementation |
| Local llama.cpp | Yes (`--chat-template`) | Yes | Нужны определённые templates |

При несовместимости — fallback на ReAct-style prompting (LLM выдаёт JSON action / observation вместо native tool_calls).

## Token Budget

- System prompt: ~500 tokens
- Tools schema: ~2000 tokens (10 tools)
- User message: ~100 tokens
- Tool result (table): 1000-5000 tokens
- Final assistant response: 500-2000 tokens
- **Total per turn:** 4000-10000 tokens

Для длинных сессий — sliding window последних N сообщений + summary старых.
