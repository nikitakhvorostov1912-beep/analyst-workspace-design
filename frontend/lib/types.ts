// Зеркало Pydantic моделей backend (Plan 01-01)

export type ChatRequest = {
  message: string;
  session_id?: string | null;
  channel_id?: string | null;
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

// SSE event discriminated union — совпадает с backend IR-6
export type SSEEvent =
  | { event: "status"; data: { stage: "thinking" | "calling_tool" | "responding" } }
  | { event: "delta"; data: { content: string } }
  | { event: "tool_call"; data: { name: string; args: Record<string, unknown>; call_id: string } }
  | { event: "tool_result"; data: { call_id: string; result: unknown; duration_ms: number } }
  | { event: "card"; data: { type: "table" | "object" | "log"; payload: unknown } }
  | { event: "done"; data: Record<string, never> }
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
};

// Сообщение чата (Phase 1: только для dummy данных)
export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  created_at: string;
};
