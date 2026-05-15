// Зеркало Pydantic моделей backend (Plan 02-01, 02-03, 03-01)

/**
 * Легитимные коды ошибок SSE — зеркало backend ErrorCode Literal.
 * Plan 3.2 добавляет user_declined/dangerous_keyword_blocked — они уже здесь.
 */
export type ErrorCode =
  | "llm_rate_limit"
  | "llm_invalid_key"
  | "llm_network_error"
  | "llm_server_error"
  | "mcp_disconnected"
  | "mcp_connect_error"
  | "tool_loop_limit"
  | "unknown_channel"
  | "init_error"
  | "internal_error"
  | "user_declined"
  | "dangerous_keyword_blocked"
  // Frontend-only коды (не от backend)
  | "no_api_key"
  | "network_error"
  | "sse_parse"
  | "sse_json"
  | string;

export type ChatRequest = {
  message: string;
  session_id?: string | null;
  channel_id: string; // required в Phase 2
};

export type HealthResponse = {
  status: "ok" | "degraded";
  version: string;
  db: "ok" | "error";
};

export type MCPPingResponse = {
  mcp_version: string;
  tool_count: number;
  session_id: string;
  duration_ms: number;
};

// Card payload schemas — зеркало backend orchestrator/cards.py

export type ColumnSchema = {
  name: string;
  type: string;
};

export type TableCardPayload = {
  columns: ColumnSchema[];
  rows: unknown[][];
  total: number;
  meta: { query?: string | null; duration_ms?: number | null };
  card_id?: string | null;  // UUID4 для deanonymize endpoint (Plan 04-01)
};

export type ObjectCardPayload = {
  header: { name: string; type: string; path: string };
  attributes: Array<{ name: string; type: string; value?: unknown }>;
  tabular_sections: Array<{ name: string; columns: string[]; rows_preview?: unknown[][] }>;
  forms: Array<{ name: string; type: string }>;
  templates: Array<{ name: string; type: string }>;
  card_id?: string | null;  // UUID4 для deanonymize endpoint (Plan 04-01)
};

export type LogEntry = {
  time: string;
  level: "Info" | "Warning" | "Error" | "Critical";
  user?: string | null;
  event: string;
  comment?: string | null;
};

export type LogCardPayload = {
  entries: LogEntry[];
  next_cursor: string | null;
  card_id?: string | null;  // UUID4 для load-more endpoint (Plan 03-04)
};

/** Контекст карточки для load-more и curl-copy (Plan 03-04) */
export type CardContext = {
  sessionId: string;
  messageId: string;
  mcpEndpoint?: string;
  mcpSessionId?: string;
};

/** Payload события confirm_required (SEC-01 Plan 3.2) */
export type ConfirmRequiredPayload = {
  tool_call_id: string;
  name: string;
  args: Record<string, unknown>;
  reason: string;
};

// SSE event discriminated union — совпадает с backend IR (Plan 02-01, 03-02)
export type SSEEvent =
  | { event: "status"; data: { stage: "thinking" | "calling_tool" | "formatting" } }
  | { event: "delta"; data: { content: string } }
  | { event: "tool_call"; data: { id: string; name: string; args: Record<string, unknown> } }
  | { event: "tool_result"; data: { id: string; ok: boolean; result: unknown; error: string | null; duration_ms: number } }
  | { event: "card"; data: CardEnvelope }
  | { event: "done"; data: { message_id: string; total_duration_ms: number } }
  | { event: "error"; data: { message: string; code: ErrorCode; retry_after_s?: number | null } }
  | { event: "confirm_required"; data: ConfirmRequiredPayload };

// LLM config — только в localStorage, никогда на backend
export type LLMConfig = {
  endpoint: string;     // "https://api.openai.com/v1"
  api_key: string;      // sk-...
  model: string;        // "mimo-32b"
  temperature: number;  // 0.3
};

// MCP connection — зеркало backend mcp_connections row
export type MCPConnection = {
  id: string;
  name: string;
  endpoint: string;        // "http://localhost:6010/mcp"
  channel: string | null;
  anon_enabled: boolean;
  last_seen_at?: string | null;   // ISO timestamp последнего успешного пинга
  created_at?: string;
};

// --- Advanced card types (Plan 04-02) ---

export type SparklinePoint = { label: string; value: number };

export type MetricCardPayload = {
  value: number;
  label: string;
  unit?: string | null;
  sparkline?: SparklinePoint[] | null;
  delta?: { value: number; direction: "up" | "down"; percent: boolean; percent_value?: number } | null;
  card_id?: string | null;
};

export type ReferenceItem = {
  object_type: string;
  name: string;
  navigation_link?: string | null;
  full_path: string;
};

export type ReferenceGroup = {
  kind: string;
  items: ReferenceItem[];
};

export type ReferencesCardPayload = {
  groups: ReferenceGroup[];
  total: number;
  card_id?: string | null;
};

export type CodeCardPayload = {
  language: "bsl" | "sql" | "json" | "text";
  code: string;
  executable: boolean;
  result?: object | null;
  card_id?: string | null;
};

// Card discriminated union — для рендеринга inline-карточек в AssistantMessage
export type CardEnvelope =
  | { type: "table"; payload: TableCardPayload }
  | { type: "object"; payload: ObjectCardPayload }
  | { type: "log"; payload: LogCardPayload }
  | { type: "metric"; payload: MetricCardPayload }
  | { type: "references"; payload: ReferencesCardPayload }
  | { type: "code"; payload: CodeCardPayload };

// Запись об одном tool call — для Trace panel (Plan 2.5)
export type ToolCallRecord = {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: unknown;
  ok?: boolean;
  duration_ms?: number;
  error?: string | null;
};

// Сообщение чата
export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  created_at: string;
  cards?: CardEnvelope[];
  tool_calls?: ToolCallRecord[];
  duration_ms?: number;
  /** Inline error — если LLM/MCP вернул ошибку во время стриминга */
  error?: { message: string; code: ErrorCode } | null;
};

// --- Sessions types (Plan 02-03) ---

export type SessionListItem = {
  id: string;
  title: string | null;
  channel_id: string;
  updated_at: string;
  message_count: number;
};

export type SessionsGrouped = {
  today: SessionListItem[];
  yesterday: SessionListItem[];
  this_week: SessionListItem[];
  earlier: SessionListItem[];
};

export type SessionDetail = {
  id: string;
  title: string | null;
  channel_id: string;
  created_at: string;
  updated_at: string;
};

export type MessageRow = {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_calls: ToolCallRecord[] | null;
  cards: CardEnvelope[] | null;
  duration_ms: number | null;
  created_at: string;
};

// --- Deanonymize types (Plan 04-01) ---

export type DeanonymizeRequest = { tokens: string[] };
export type DeanonymizeResponse = { mapping: Record<string, string> };

// --- Search types (Plan 04-03) ---

export type SearchResultItem = {
  session_id: string;
  session_title: string | null;
  message_id: string;
  snippet: string;
  created_at: string;
  channel_id: string;
};

export type SearchResponse = {
  results: SearchResultItem[];
  total: number;
  query: string;
};

// --- Metadata suggest types (Plan 04-03) ---

export type MetadataSuggestItem = {
  object_type: string;
  name: string;
  full_path: string;
  presentation: string | null;
};

export type MetadataSuggestResponse = {
  items: MetadataSuggestItem[];
  cached: boolean;
  stale: boolean;
};
