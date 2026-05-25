import type {
  AuxDiagnosticsResponse,
  EnvDiagnosticsResponse,
  ChatRequest,
  HealthResponse,
  LLMConfigCreate,
  LLMConfigResponse,
  LLMConfigTestResponse,
  LLMConfigUpdate,
  LogEntry,
  MCPConnection,
  MCPKind,
  MCPPingResponse,
  MemoryDocument,
  MemoryUpdateRequest,
  MemoryUpdateResponse,
  MessageRow,
  MetadataSuggestResponse,
  SearchResponse,
  SessionDetail,
  SessionsGrouped,
  SSEEvent,
  SkillCreateRequest,
  SkillDTO,
  SkillListResponse,
  CuratorReport,
  TodoListResponse,
  TrajectoryStats,
  InsightsResponse,
  InsightsPeriod,
} from "./types";
import { getLLMApiKey } from "./api-keys";
import { parseSSEStream } from "./sse";
// 2026-05-25 HOTFIX v1.4.7: getBackend вынесен в backend-url.ts чтобы
// разорвать circular dependency с api-keys.ts. Раньше getBackend жил здесь,
// api-keys.ts его импортировал, при этом api.ts импортировал getLLMApiKey
// из api-keys.ts → cycle. В dev/vitest было OK, в Next 15 production build
// один из re-exports становился undefined → TypeError → blank screen в
// Electron-сборке v1.4.6. Re-export ниже сохраняет обратную совместимость
// для модулей которые делали `import { getBackend } from "@/lib/api"`.
import { getBackend } from "./backend-url";

export { getBackend };

/**
 * Проверяет доступность backend.
 * Возвращает HealthResponse или выбрасывает при сетевой ошибке.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${getBackend()}/health`);
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
  const url = `${getBackend()}/mcp/_/ping?endpoint=${encodeURIComponent(endpoint)}`;
  const response = await fetch(url, { method: "POST", signal });
  if (!response.ok) {
    throw new Error(`MCP ping вернул ${response.status}`);
  }
  return response.json() as Promise<MCPPingResponse>;
}

/**
 * Отправляет сообщение в /chat и возвращает AsyncIterable<SSEEvent>.
 * api_key читается из localStorage (getLLMApiKey) и передаётся ТОЛЬКО через header X-LLM-API-Key.
 * endpoint + model передаются вызывающим через llm-параметр (source-of-truth = backend, Plan 5.4 UX-04).
 * Никогда не кладём api_key в body (NFR-6, ARCHITECTURE Key Decision #1, T-01-12).
 *
 * llm.hasEnvKey=true → backend получит ключ из env DEFAULT_LLM_API_KEY если
 * локального ключа нет. Это даёт «прописал один раз в .env — забыл навсегда».
 */
export async function* fetchChat(
  req: ChatRequest,
  llm: { endpoint: string; model: string; hasEnvKey?: boolean },
  signal?: AbortSignal,
  extraHeaders?: Record<string, string>,
): AsyncIterable<SSEEvent> {
  const apiKey = getLLMApiKey();
  // Если ключа нет в браузере И backend не пометил env-ключ — фронт сразу
  // ругается. Иначе отправляем запрос, и backend подставит env-ключ сам.
  if (!apiKey && !llm.hasEnvKey) {
    yield {
      event: "error",
      data: { message: "API ключ не задан. Откройте Настройки.", code: "no_api_key" },
    };
    return;
  }

  const requestHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    "Accept": "text/event-stream",
    "X-LLM-Endpoint": llm.endpoint,
    "X-LLM-Model": llm.model,
    ...extraHeaders,
  };
  // Header отправляем ТОЛЬКО если есть локальный ключ — иначе пусть backend
  // решает env-fallback'ом (chat.py использует settings.default_llm_api_key).
  if (apiKey) {
    requestHeaders["X-LLM-API-Key"] = apiKey;
  }

  let response: Response;
  try {
    response = await fetch(`${getBackend()}/chat`, {
      method: "POST",
      headers: requestHeaders,
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
  const response = await fetch(`${getBackend()}/connections`);
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
  kind?: MCPKind;
}): Promise<MCPConnection> {
  const response = await fetch(`${getBackend()}/connections`, {
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
  patch: Partial<{ name: string; endpoint: string; channel: string; anon_enabled: boolean; kind: MCPKind }>,
): Promise<MCPConnection> {
  const response = await fetch(`${getBackend()}/connections/${id}`, {
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
  const response = await fetch(`${getBackend()}/connections/${id}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Ошибка удаления подключения: ${response.status}`);
  }
}

/**
 * Структурированная ошибка ping подключения. Бросается из pingConnection
 * когда backend вернул новый формат detail (с error_code/hint/diagnostics).
 *
 * UI ловит её, чтобы:
 *   - показать `hint` с конкретной подсказкой (вместо обрезка исключения);
 *   - подсветить кнопку «Собрать диагностику»;
 *   - распознать error_code (`tcp_refused` / `dns_failed` / ...) для иконки.
 */
export class MCPPingError extends Error {
  constructor(
    message: string,
    public readonly errorCode: string,
    public readonly hint: string,
    public readonly diagnostics: Record<string, unknown> | null,
  ) {
    super(message);
    this.name = "MCPPingError";
  }
}

/**
 * Пингует MCP-подключение по его id в backend.
 * Обновляет last_seen_at при успехе.
 *
 * При 502 backend (с 2026-05-25) возвращает объект:
 *   { error_code, message, hint, diagnostics }
 * — бросаем `MCPPingError` чтобы UI мог взять hint без regex-парсинга.
 * Legacy формат (строка) тоже поддерживаем для обратной совместимости.
 */
export async function pingConnection(
  id: string,
  signal?: AbortSignal,
): Promise<MCPPingResponse> {
  const response = await fetch(`${getBackend()}/connections/${id}/ping`, {
    method: "POST",
    signal,
  });
  if (!response.ok) {
    let detail: unknown = "";
    try {
      const body = await response.json();
      detail = body?.detail;
    } catch {
      /* not json */
    }
    if (detail && typeof detail === "object") {
      const d = detail as {
        error_code?: string;
        message?: string;
        hint?: string;
        diagnostics?: Record<string, unknown>;
      };
      throw new MCPPingError(
        d.message || `Сервер ответил ${response.status}`,
        d.error_code ?? "unknown",
        d.hint ?? "",
        d.diagnostics ?? null,
      );
    }
    const detailStr = typeof detail === "string" ? detail : "";
    throw new Error(detailStr || `Сервер ответил ${response.status}`);
  }
  return response.json() as Promise<MCPPingResponse>;
}

/**
 * Запрашивает полный диагностический отчёт по подключению.
 * В отличие от ping — endpoint ВСЕГДА отвечает 200, даже если ping упал
 * внутри (детали ошибки уезжают в поля error_class/hint/exception_*).
 *
 * Используется кнопкой «Собрать диагностику» в MCPConnectionForm — фронт
 * парсит JSON и скачивает его как файл `diagnostics-<name>-<ts>.json`.
 */
export async function getConnectionDiagnostics(
  id: string,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  const response = await fetch(`${getBackend()}/diagnostics/connection/${id}`, {
    method: "POST",
    signal,
  });
  if (!response.ok) {
    throw new Error(`Диагностика недоступна: HTTP ${response.status}`);
  }
  return response.json() as Promise<Record<string, unknown>>;
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

  const response = await fetch(`${getBackend()}/sessions`, {
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
    ? `${getBackend()}/sessions?channel_id=${encodeURIComponent(channel_id)}`
    : `${getBackend()}/sessions`;

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
  const response = await fetch(`${getBackend()}/sessions/${id}`);
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
  const response = await fetch(`${getBackend()}/sessions/${id}/messages`);
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
  const response = await fetch(`${getBackend()}/sessions/${id}`, {
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
  const response = await fetch(`${getBackend()}/chat/confirm`, {
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
 * Sprint 2 (Hermes C9): запрашивает прерывание активного tool-calling loop сессии.
 * Backend ставит флаг — loop проверит между LLM-вызовами и завершится gracefully
 * с done(interrupted=true).
 *
 * Идемпотентен: повторный вызов на ту же сессию = no-op.
 */
export async function interruptChat(sessionId: string): Promise<void> {
  if (!sessionId.trim()) return;
  const response = await fetch(
    `${getBackend()}/chat/${encodeURIComponent(sessionId)}/interrupt`,
    { method: "POST" },
  );
  if (response.status === 202) return;
  if (response.status === 400) {
    throw new Error("session_id обязателен");
  }
  if (!response.ok) {
    throw new Error(`Ошибка запроса прерывания: ${response.status}`);
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
    `${getBackend()}/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/cards/${encodeURIComponent(cardId)}/load-more`,
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
    `${getBackend()}/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/cards/${encodeURIComponent(cardId)}/deanonymize`,
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
  const response = await fetch(`${getBackend()}/search?${params.toString()}`);
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
    `${getBackend()}/connections/${encodeURIComponent(channelId)}/metadata-suggest?${params.toString()}`,
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
  const response = await fetch(`${getBackend()}/sessions/${id}`, {
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
  const response = await fetch(`${getBackend()}/llm-config`);
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
  const response = await fetch(`${getBackend()}/llm-config`, {
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
  const response = await fetch(`${getBackend()}/llm-config/default`, {
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
  const response = await fetch(`${getBackend()}/llm-config/default`, {
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
  const response = await fetch(`${getBackend()}/llm-config/test`, {
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

/**
 * Запрашивает статус вспомогательных MCP-серверов (bsl-context и др.).
 * Возвращает пустой aux=[] на старом backend, который ещё не имеет этого endpoint.
 */
export async function fetchAuxDiagnostics(): Promise<AuxDiagnosticsResponse> {
  try {
    const response = await fetch(`${getBackend()}/diagnostics/aux`);
    if (!response.ok) {
      // 404 на старом backend — норма, просто скрываем секцию aux в /status
      return { aux: [] };
    }
    return response.json() as Promise<AuxDiagnosticsResponse>;
  } catch {
    return { aux: [] };
  }
}

/**
 * Запрашивает sanitized снимок окружения backend.
 * На старом backend возвращает null — UI просто не показывает блок «Окружение».
 */
export async function fetchEnvDiagnostics(): Promise<EnvDiagnosticsResponse | null> {
  try {
    const response = await fetch(`${getBackend()}/diagnostics/env`);
    if (!response.ok) return null;
    return response.json() as Promise<EnvDiagnosticsResponse>;
  } catch {
    return null;
  }
}

/** URL backend для UI — пригодится в блоке «Окружение» на /status. */
export function getBackendUrl(): string {
  return getBackend();
}

export interface LogPathResponse {
  log_dir: string;
  log_file: string;
  exists: boolean;
}

/**
 * Путь к логам backend. Используется в /status для кнопки «Открыть папку
 * с логами» — чтобы коллеги при репорте бага могли быстро приложить
 * файл. На старом backend (< v1.2.13) endpoint отсутствует → null.
 */
export async function fetchLogPath(): Promise<LogPathResponse | null> {
  try {
    const response = await fetch(`${getBackend()}/diagnostics/log-path`);
    if (!response.ok) return null;
    return response.json() as Promise<LogPathResponse>;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Admin (Phase 9.1) — privacy escape hatches
// ---------------------------------------------------------------------------

export interface ResetLocalDbResult {
  ok: boolean;
  cleared?: string[];
  error?: string;
}

/**
 * Сбрасывает локальную БД (sessions + messages + card_states + metadata_cache).
 * Настройки MCP-подключений и LLM сохраняются.
 *
 * Требует header X-Confirm-Reset: true — защита от случайного вызова.
 */
export async function resetLocalDb(): Promise<ResetLocalDbResult> {
  try {
    const response = await fetch(`${getBackend()}/admin/reset-local-db`, {
      method: "POST",
      headers: { "X-Confirm-Reset": "true" },
    });
    if (!response.ok) {
      return { ok: false, error: `HTTP ${response.status}` };
    }
    const data = (await response.json()) as { status: string; cleared: string[] };
    return { ok: data.status === "ok", cleared: data.cleared };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Network error",
    };
  }
}

// --- Sprint 1 (Hermes): Memory API ---

/** Получить snapshot MEMORY.md + USER.md для канала. */
export async function fetchMemory(channelId: string): Promise<MemoryDocument> {
  const response = await fetch(
    `${getBackend()}/memory/${encodeURIComponent(channelId)}`,
  );
  if (!response.ok) {
    throw new Error(`fetchMemory: HTTP ${response.status}`);
  }
  return response.json() as Promise<MemoryDocument>;
}

/** Перезаписать один namespace целиком. */
export async function updateMemory(
  channelId: string,
  body: MemoryUpdateRequest,
): Promise<MemoryUpdateResponse> {
  const response = await fetch(
    `${getBackend()}/memory/${encodeURIComponent(channelId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new Error(`updateMemory: HTTP ${response.status}`);
  }
  return response.json() as Promise<MemoryUpdateResponse>;
}

/** Trajectory stats — кол-во JSONL записей для будущего fine-tuning. */
export async function fetchTrajectoryStats(): Promise<TrajectoryStats> {
  const response = await fetch(`${getBackend()}/diagnostics/trajectory`);
  if (!response.ok) {
    throw new Error(`fetchTrajectoryStats: HTTP ${response.status}`);
  }
  return response.json() as Promise<TrajectoryStats>;
}

// --- Sprint 3 (Hermes A8/A9/A6/D3): Skills + Curator + Todos ---

/** Список skills для канала (активные + архив). */
export async function fetchSkills(channelId: string): Promise<SkillListResponse> {
  const response = await fetch(
    `${getBackend()}/skills/${encodeURIComponent(channelId)}`,
  );
  if (!response.ok) {
    throw new Error(`fetchSkills: HTTP ${response.status}`);
  }
  return response.json() as Promise<SkillListResponse>;
}

/** Создать пользовательский skill. */
export async function createSkill(
  channelId: string,
  body: SkillCreateRequest,
): Promise<SkillDTO> {
  const response = await fetch(
    `${getBackend()}/skills/${encodeURIComponent(channelId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (response.status === 201) {
    return response.json() as Promise<SkillDTO>;
  }
  if (response.status === 400) {
    const data = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(data.detail || "Невалидный skill");
  }
  throw new Error(`createSkill: HTTP ${response.status}`);
}

/** Архивировать skill (не удаляется, можно вернуть). */
export async function archiveSkill(channelId: string, skillId: string): Promise<void> {
  const response = await fetch(
    `${getBackend()}/skills/${encodeURIComponent(channelId)}/${encodeURIComponent(skillId)}/archive`,
    { method: "POST" },
  );
  if (response.status === 204) return;
  if (response.status === 409) {
    throw new Error("Pinned skill нельзя архивировать");
  }
  if (response.status === 404) {
    throw new Error("Skill не найден");
  }
  throw new Error(`archiveSkill: HTTP ${response.status}`);
}

/** Вернуть skill из архива. */
export async function unarchiveSkill(channelId: string, skillId: string): Promise<void> {
  const response = await fetch(
    `${getBackend()}/skills/${encodeURIComponent(channelId)}/${encodeURIComponent(skillId)}/unarchive`,
    { method: "POST" },
  );
  if (response.status === 204) return;
  if (response.status === 404) {
    throw new Error("Skill в архиве не найден");
  }
  throw new Error(`unarchiveSkill: HTTP ${response.status}`);
}

/** Удалить skill безвозвратно. */
export async function deleteSkill(channelId: string, skillId: string): Promise<void> {
  const response = await fetch(
    `${getBackend()}/skills/${encodeURIComponent(channelId)}/${encodeURIComponent(skillId)}`,
    { method: "DELETE" },
  );
  if (response.status === 204) return;
  if (response.status === 409) {
    throw new Error("Pinned skill нельзя удалить");
  }
  if (response.status === 404) {
    throw new Error("Skill не найден");
  }
  throw new Error(`deleteSkill: HTTP ${response.status}`);
}

/** Запустить Curator (auto-archive). dry_run=true — только показать кандидатов. */
export async function runCurator(
  channelId: string,
  dryRun: boolean = false,
): Promise<CuratorReport> {
  const response = await fetch(
    `${getBackend()}/skills/${encodeURIComponent(channelId)}/curator/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dry_run: dryRun }),
    },
  );
  if (!response.ok) {
    throw new Error(`runCurator: HTTP ${response.status}`);
  }
  return response.json() as Promise<CuratorReport>;
}

/** Список todo задач сессии. */
export async function fetchTodos(sessionId: string): Promise<TodoListResponse> {
  const response = await fetch(
    `${getBackend()}/todos/${encodeURIComponent(sessionId)}`,
  );
  if (!response.ok) {
    throw new Error(`fetchTodos: HTTP ${response.status}`);
  }
  return response.json() as Promise<TodoListResponse>;
}

// Sprint 4 (Hermes D1/G8): Clarify + Insights API.

/** Отправляет ответ пользователя на clarify_question (Hermes D1). */
export async function postChatClarify(body: {
  clarify_id: string;
  answer: string | string[];
}): Promise<void> {
  const response = await fetch(`${getBackend()}/chat/clarify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (response.status === 204) return;
  if (response.status === 404) {
    throw new Error("clarify_id не найден или истёк");
  }
  if (!response.ok) {
    throw new Error(`postChatClarify: HTTP ${response.status}`);
  }
}

/** Получает агрегированную аналитику сессий за период. */
export async function fetchInsights(
  period: InsightsPeriod = "7d",
  topN: number = 10,
): Promise<InsightsResponse> {
  const response = await fetch(
    `${getBackend()}/insights?period=${period}&top_n=${topN}`,
  );
  if (!response.ok) {
    throw new Error(`fetchInsights: HTTP ${response.status}`);
  }
  return response.json() as Promise<InsightsResponse>;
}
