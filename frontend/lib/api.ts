import type {
  ChatRequest,
  HealthResponse,
  LLMConfigCreate,
  LLMConfigResponse,
  LLMConfigTestResponse,
  LLMConfigUpdate,
  LogEntry,
  MCPConnection,
  MCPPingResponse,
  MessageRow,
  MetadataSuggestResponse,
  SearchResponse,
  SessionDetail,
  SessionsGrouped,
  SSEEvent,
} from "./types";
import { getLLMApiKey } from "./api-keys";
import { parseSSEStream } from "./sse";

const BACKEND =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_BACKEND_URL) ||
  "http://localhost:8010";

/**
 * Проверяет доступность backend.
 * Возвращает HealthResponse или выбрасывает при сетевой ошибке.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${BACKEND}/health`);
  if (!response.ok) {
    throw new Error(`Сервер вернул ${response.status}`);
  }
  return response.json() as Promise<HealthResponse>;
}

/**
 * Пингует MCP endpoint через backend proxy.
 * LLM api_key не участвует — это только MCP health check.
 */
export async function fetchMCPPing(
  endpoint: string,
  signal?: AbortSignal,
): Promise<MCPPingResponse> {
  const url = `${BACKEND}/mcp/_/ping?endpoint=${encodeURIComponent(endpoint)}`;
  const response = await fetch(url, { method: "POST", signal });
  if (!response.ok) {
    throw new Error(`MCP ping вернул ${response.status}`);
  }
  return response.json() as Promise<MCPPingResponse>;
}

/**
 * Отправляет сообщение в /chat и возвращает AsyncIterable<SSEEvent>.
 * api_key читается из sessionStorage (getLLMApiKey) и передаётся ТОЛЬКО через header X-LLM-API-Key.
 * endpoint + model передаются вызывающим через llm-параметр (source-of-truth = backend, Plan 5.4 UX-04).
 * Никогда не кладём api_key в body (NFR-6, ARCHITECTURE Key Decision #1, T-01-12).
 */
export async function* fetchChat(
  req: ChatRequest,
  llm: { endpoint: string; model: string },
  signal?: AbortSignal,
  extraHeaders?: Record<string, string>,
): AsyncIterable<SSEEvent> {
  const apiKey = getLLMApiKey();
  if (!apiKey) {
    yield {
      event: "error",
      data: { message: "API ключ не задан. Откройте Настройки.", code: "no_api_key" },
    };
    return;
  }

  let response: Response;
  try {
    response = await fetch(`${BACKEND}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-LLM-API-Key": apiKey,
        "X-LLM-Endpoint": llm.endpoint,
        "X-LLM-Model": llm.model,
        ...extraHeaders,
      },
      body: JSON.stringify(req),
      signal,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Сетевая ошибка";
    yield {
      event: "error",
      data: { message, code: "network_error" },
    };
    return;
  }

  if (!response.ok) {
    yield {
      event: "error",
      data: {
        message: `Backend вернул ${response.status}`,
        code: `http_${response.status}`,
      },
    };
    return;
  }

  if (!response.body) {
    yield {
      event: "error",
      data: { message: "Пустое тело ответа", code: "empty_body" },
    };
    return;
  }

  yield* parseSSEStream(response.body);
}

// --- Connections API (Plan 02-04) ---

/**
 * Загружает список MCP-подключений с backend.
 */
export async function fetchConnections(): Promise<MCPConnection[]> {
  const response = await fetch(`${BACKEND}/connections`);
  if (!response.ok) {
    throw new Error(`Ошибка загрузки подключений: ${response.status}`);
  }
  const data = (await response.json()) as { connections: MCPConnection[] };
  return data.connections;
}

/**
 * Создаёт новое MCP-подключение.
 */
export async function createConnection(body: {
  name: string;
  endpoint: string;
  channel?: string;
  anon_enabled?: boolean;
}): Promise<MCPConnection> {
  const response = await fetch(`${BACKEND}/connections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Ошибка создания подключения: ${response.status}`);
  }
  return response.json() as Promise<MCPConnection>;
}

/**
 * Обновляет поля MCP-подключения (partial update).
 */
export async function updateConnection(
  id: string,
  patch: Partial<{ name: string; endpoint: string; channel: string; anon_enabled: boolean }>,
): Promise<MCPConnection> {
  const response = await fetch(`${BACKEND}/connections/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    throw new Error(`Ошибка обновления подключения: ${response.status}`);
  }
  return response.json() as Promise<MCPConnection>;
}

/**
 * Удаляет MCP-подключение.
 */
export async function deleteConnection(id: string): Promise<void> {
  const response = await fetch(`${BACKEND}/connections/${id}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Ошибка удаления подключения: ${response.status}`);
  }
}

/**
 * Пингует MCP-подключение по его id в backend.
 * Обновляет last_seen_at при успехе.
 */
export async function pingConnection(
  id: string,
  signal?: AbortSignal,
): Promise<MCPPingResponse> {
  const response = await fetch(`${BACKEND}/connections/${id}/ping`, {
    method: "POST",
    signal,
  });
  if (!response.ok) {
    throw new Error(`MCP ping вернул ${response.status}`);
  }
  return response.json() as Promise<MCPPingResponse>;
}

// --- Sessions API (Plan 02-03) ---

/**
 * Создаёт новую сессию в backend.
 */
export async function createSession(
  channel_id: string,
  title?: string,
): Promise<SessionDetail> {
  const body: { channel_id: string; title?: string } = { channel_id };
  if (title) body.title = title;

  const response = await fetch(`${BACKEND}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Ошибка создания сессии: ${response.status}`);
  }
  return response.json() as Promise<SessionDetail>;
}

/**
 * Загружает список сессий, сгруппированных по дате.
 */
export async function fetchSessions(channel_id?: string): Promise<SessionsGrouped> {
  const url = channel_id
    ? `${BACKEND}/sessions?channel_id=${encodeURIComponent(channel_id)}`
    : `${BACKEND}/sessions`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Ошибка загрузки сессий: ${response.status}`);
  }
  return response.json() as Promise<SessionsGrouped>;
}

/**
 * Загружает детали одной сессии. Возвращает null при 404.
 */
export async function fetchSessionDetail(id: string): Promise<SessionDetail | null> {
  const response = await fetch(`${BACKEND}/sessions/${id}`);
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Ошибка загрузки сессии: ${response.status}`);
  }
  return response.json() as Promise<SessionDetail>;
}

/**
 * Загружает все сообщения сессии в хронологическом порядке.
 */
export async function fetchSessionMessages(id: string): Promise<MessageRow[]> {
  const response = await fetch(`${BACKEND}/sessions/${id}/messages`);
  if (!response.ok) {
    throw new Error(`Ошибка загрузки сообщений: ${response.status}`);
  }
  const data = (await response.json()) as { messages: MessageRow[] };
  return data.messages;
}

/**
 * Удаляет сессию и все её сообщения.
 */
export async function deleteSession(id: string): Promise<void> {
  const response = await fetch(`${BACKEND}/sessions/${id}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Ошибка удаления сессии: ${response.status}`);
  }
}

/**
 * Подтверждает или отклоняет выполнение опасного execute_code (SEC-01).
 * 204 при успехе, 404 если tool_call_id истёк.
 */
export async function postChatConfirm(body: {
  tool_call_id: string;
  approved: boolean;
}): Promise<void> {
  const response = await fetch(`${BACKEND}/chat/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (response.status === 204) return;
  if (response.status === 404) {
    throw new Error("tool_call_id не найден или истёк");
  }
  if (!response.ok) {
    throw new Error(`Ошибка подтверждения: ${response.status}`);
  }
}

// --- LogCard load-more API (Plan 03-04) ---

/**
 * Загружает следующую страницу записей LogCard.
 * Вызывает POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more.
 */
export async function loadMoreLogEntries(
  sessionId: string,
  messageId: string,
  cardId: string,
  cursor: string,
): Promise<{ entries: LogEntry[]; next_cursor: string | null }> {
  const response = await fetch(
    `${BACKEND}/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/cards/${encodeURIComponent(cardId)}/load-more`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cursor }),
    },
  );
  if (!response.ok) {
    throw new Error(`Ошибка загрузки следующей страницы: ${response.status}`);
  }
  return response.json() as Promise<{ entries: LogEntry[]; next_cursor: string | null }>;
}

// --- Deanonymize API (Plan 04-01) ---

/**
 * Раскрывает anon-токены для карточки через backend /deanonymize endpoint.
 * Возвращает mapping {"[ORG-001]": "ООО Ромашка", ...}.
 * Cache-Control: no-store устанавливается backend-ом.
 */
export async function deanonymizeCard(
  sessionId: string,
  messageId: string,
  cardId: string,
  tokens: string[],
): Promise<Record<string, string>> {
  const response = await fetch(
    `${BACKEND}/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/cards/${encodeURIComponent(cardId)}/deanonymize`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tokens }),
    },
  );
  if (!response.ok) {
    throw new Error(`Ошибка раскрытия токенов: ${response.status}`);
  }
  const data = (await response.json()) as { mapping: Record<string, string> };
  return data.mapping;
}

// --- Search API (Plan 04-03) ---

/**
 * Полнотекстовый поиск по сессиям и сообщениям.
 * Требует q ≥ 2 символа. Возвращает results с HTML snippet (теги <mark>).
 */
export async function searchMessages(
  q: string,
  channel?: string,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q });
  if (channel) params.set("channel", channel);
  const response = await fetch(`${BACKEND}/search?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Ошибка поиска: ${response.status}`);
  }
  return response.json() as Promise<SearchResponse>;
}

/**
 * Загружает предложения объектов метаданных 1С из кеша.
 * При cache miss — backend обновляет через MCP.
 */
export async function metadataSuggest(
  channelId: string,
  q: string,
): Promise<MetadataSuggestResponse> {
  const params = new URLSearchParams({ q });
  const response = await fetch(
    `${BACKEND}/connections/${encodeURIComponent(channelId)}/metadata-suggest?${params.toString()}`,
  );
  if (!response.ok) {
    throw new Error(`Ошибка metadata suggest: ${response.status}`);
  }
  return response.json() as Promise<MetadataSuggestResponse>;
}

/**
 * Переименовывает сессию.
 */
export async function patchSessionTitle(
  id: string,
  title: string,
): Promise<SessionDetail> {
  const response = await fetch(`${BACKEND}/sessions/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error(`Ошибка переименования сессии: ${response.status}`);
  }
  return response.json() as Promise<SessionDetail>;
}

// --- LLM Config API (Plan 5.1) ---

/**
 * Загружает сохранённый LLM-конфиг с backend.
 * Возвращает null если конфиг не задан. API ключ не хранится на backend.
 */
export async function fetchLLMConfig(): Promise<LLMConfigResponse | null> {
  const response = await fetch(`${BACKEND}/llm-config`);
  if (!response.ok) {
    throw new Error(`Ошибка загрузки LLM-конфига: ${response.status}`);
  }
  const data = await response.json() as LLMConfigResponse | null;
  return data;
}

/**
 * Сохраняет (UPSERT) LLM-конфиг на backend. API ключ передаётся отдельно через header.
 */
export async function saveLLMConfig(body: LLMConfigCreate): Promise<LLMConfigResponse> {
  const response = await fetch(`${BACKEND}/llm-config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Ошибка сохранения LLM: ${response.status}`);
  }
  return response.json() as Promise<LLMConfigResponse>;
}

/**
 * Частично обновляет LLM-конфиг (PATCH /llm-config/default).
 */
export async function updateLLMConfig(patch: LLMConfigUpdate): Promise<LLMConfigResponse> {
  const response = await fetch(`${BACKEND}/llm-config/default`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    throw new Error(`Ошибка обновления LLM-конфига: ${response.status}`);
  }
  return response.json() as Promise<LLMConfigResponse>;
}

/**
 * Удаляет LLM-конфиг (DELETE /llm-config/default). 204 = успех.
 */
export async function deleteLLMConfig(): Promise<void> {
  const response = await fetch(`${BACKEND}/llm-config/default`, {
    method: "DELETE",
  });
  if (response.status === 204) return;
  if (!response.ok) {
    throw new Error(`Ошибка удаления LLM-конфига: ${response.status}`);
  }
}

/**
 * Тестирует LLM endpoint + model через 1-token completion.
 * API ключ передаётся через header X-LLM-API-Key (T-05-04), не в теле.
 * Backend всегда возвращает 200; ok=false при ошибках провайдера.
 */
export async function testLLMConfig(
  body: LLMConfigCreate,
  apiKey: string,
): Promise<LLMConfigTestResponse> {
  const response = await fetch(`${BACKEND}/llm-config/test`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-LLM-API-Key": apiKey,
    },
    body: JSON.stringify({ endpoint: body.endpoint, model: body.model }),
  });
  if (!response.ok) {
    throw new Error(`Ошибка test endpoint: ${response.status}`);
  }
  return response.json() as Promise<LLMConfigTestResponse>;
}
