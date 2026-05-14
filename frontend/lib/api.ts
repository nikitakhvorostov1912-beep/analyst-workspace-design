import type {
  ChatRequest,
  HealthResponse,
  MCPConnection,
  MCPPingResponse,
  MessageRow,
  SessionDetail,
  SessionsGrouped,
  SSEEvent,
} from "./types";
import { getLLMConfig } from "./storage";
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
 * api_key читается из localStorage и передаётся ТОЛЬКО через header X-LLM-API-Key.
 * Никогда не кладём api_key в body (NFR-6, ARCHITECTURE Key Decision #1, T-01-12).
 */
export async function* fetchChat(
  req: ChatRequest,
  signal?: AbortSignal,
): AsyncIterable<SSEEvent> {
  const cfg = getLLMConfig();
  if (!cfg || !cfg.api_key) {
    yield {
      event: "error",
      data: { message: "API ключ не задан. Настройте LLM в разделе Настройки.", code: "no_api_key" },
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
        "X-LLM-API-Key": cfg.api_key,
        "X-LLM-Endpoint": cfg.endpoint,
        "X-LLM-Model": cfg.model,
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
