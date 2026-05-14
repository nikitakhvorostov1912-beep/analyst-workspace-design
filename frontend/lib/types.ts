// Зеркало Pydantic моделей backend (Plan 02-01, 02-03)

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
};

export type ObjectCardPayload = {
  header: { name: string; type: string; path: string };
  attributes: Array<{ name: string; type: string; value?: unknown }>;
  tabular_sections: Array<{ name: string; columns: string[]; rows_preview?: unknown[][] }>;
  forms: Array<{ name: string; type: string }>;
  templates: Array<{ name: string; type: string }>;
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
};

// SSE event discriminated union — совпадает с backend IR (Plan 02-01)
export type SSEEvent =
  | { event: "status"; data: { stage: "thinking" | "calling_tool" | "formatting" } }
  | { event: "delta"; data: { content: string } }
  | { event: "tool_call"; data: { id: string; name: string; args: Record<string, unknown> } }
  | { event: "tool_result"; data: { id: string; ok: boolean; result: unknown; error: string | null; duration_ms: number } }
  | { event: "card"; data: { type: "table"; payload: TableCardPayload } | { type: "object"; payload: ObjectCardPayload } | { type: "log"; payload: LogCardPayload } }
  | { event: "done"; data: { message_id: string; total_duration_ms: number } }
  | { event: "error"; data: { message: string; code: string } };

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

// Card discriminated union — для рендеринга inline-карточек в AssistantMessage
export type CardEnvelope =
  | { type: "table"; payload: TableCardPayload }
  | { type: "object"; payload: ObjectCardPayload }
  | { type: "log"; payload: LogCardPayload };

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
