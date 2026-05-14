import type { ChatRequest, HealthResponse, MCPPingResponse, SSEEvent } from "./types";
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
