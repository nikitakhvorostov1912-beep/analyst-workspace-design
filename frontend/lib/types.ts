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
  | "duplicate_tool_loop"
  | "unknown_channel"
  | "init_error"
  | "internal_error"
  | "user_declined"
  | "dangerous_keyword_blocked"
  | "clarify_timeout"
  // Frontend-only коды (не от backend)
  | "no_api_key"
  | "network_error"
  | "sse_parse"
  | "sse_json"
  | string;

export type ChatAttachment = {
  /** Имя файла (для UI и LLM-промпта). */
  name: string;
  /** MIME-тип, например application/pdf. Может быть пустым — backend определит по расширению. */
  mime: string;
  /** Содержимое в base64 без data:URI префикса. */
  content_base64: string;
};

export type ChatRequest = {
  message: string;
  session_id?: string | null;
  channel_id: string; // required в Phase 2
  /** Опциональные прикреплённые документы (PDF/DOCX/XLSX/TXT/CSV). Max 5, ≤25MB каждый. */
  attachments?: ChatAttachment[];
};

/**
 * Статус живого 1С:Напарника (buddy MCP) из /health.
 * Питается buddy_monitor (#40): healthcheck-пинги + телеметрия вызовов.
 */
export type BuddyHealth = {
  enabled: boolean;
  status: "up" | "down" | "unknown";
  degraded: boolean;
  consecutive_fails: number;
  endpoint: string;
  checks_total: number;
  calls_total: number;
  calls_ok: number;
  calls_fail: number;
};

export type HealthResponse = {
  status: "ok" | "degraded";
  version: string;
  db: "ok" | "error";
  /** Живой Напарник (ИТС). null/отсутствует — старый backend без поля. */
  buddy?: BuddyHealth | null;
};

/**
 * Тип подключения к 1С MCP:
 *   embedded — EPF MCP_Toolkit на машине аналитика (localhost:6010 и т.п.)
 *   proxy    — EPF на сервере, доступ через HF Spaces / Cloudflare Tunnel
 * Для аналитика это принципиально разные сценарии: embedded работает только
 * пока его 1С открыта; proxy — пока обработка запущена на удалённом сервере.
 */
export type MCPKind = "embedded" | "proxy";

export type MCPPingResponse = {
  mcp_version: string;
  tool_count: number;
  session_id: string;
  duration_ms: number;
  /** Поля, появившиеся в backend Phase MCP-stack-visibility — могут отсутствовать на старом backend. */
  kind?: MCPKind;
  server_name?: string;
  tool_names?: string[];
  last_seen_at?: string | null;
};

export type AuxMCPStatus = {
  name: string;
  configured: boolean;
  status: "ok" | "error" | "not_configured";
  tool_count: number;
  error_hint?: string | null;
};

export type AuxDiagnosticsResponse = {
  aux: AuxMCPStatus[];
};

/**
 * Sanitized снимок окружения backend для UI «Диагностика».
 * Не содержит секретов. Аналитик видит все адреса, пути и версии — чтобы
 * понимать к чему приложение подключено и куда смотреть когда не работает.
 */
export type EnvDiagnosticsResponse = {
  app_version: string;
  environment: "dev" | "prod";
  default_llm_endpoint: string;
  default_llm_model: string;
  bsl_context_jar: string;
  bsl_context_java: string;
  bsl_context_platform_path: string;
  cors_origins: string[];
  sqlite_path: string;
  env_var_names: Record<string, string>;
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
  // P2.2 ResultSizeGate (2026-05-23): true означает что backend урезал rows
  // до MAX_ROWS_FOR_LLM=500. total_available — реальное количество строк до cap.
  // UI показывает баннер «Показаны первые N из total_available, скачайте CSV
  // для полного набора».
  truncated?: boolean;
  total_available?: number | null;
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
  | { event: "done"; data: { message_id: string; total_duration_ms: number; interrupted?: boolean } }
  | { event: "error"; data: { message: string; code: ErrorCode; retry_after_s?: number | null } }
  | { event: "confirm_required"; data: ConfirmRequiredPayload }
  | { event: "clarify_required"; data: ClarifyRequiredPayload };

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
  /** embedded (default) / proxy. Опционально для совместимости со старым backend. */
  kind?: MCPKind;
  last_seen_at?: string | null;   // ISO timestamp последнего успешного пинга
  created_at?: string;
  // === Sprint 03 (handoff 06 · Channel enrichment) ===
  // Поля заполняются backend'ом при detect-фазе. Frontend готов работать с null —
  // показывает «—» или скрывает соответствующую строку.
  /** Тип конфигурации 1С: «УТ 11.5» / «ERP 2.5» / «УСО» / «Самописная» / null. */
  config_type?: string | null;
  /** Количество объектов в метаданных (детектится при первом успешном ping'е). */
  metadata_object_count?: number | null;
  /** ISO timestamp последней синхронизации метаданных. */
  metadata_last_sync?: string | null;
  /** Количество tools, отданных MCP при ping'е (зеркалит ping.tool_count). */
  tool_count?: number | null;
  // === M-K1.6 (migration v11) · Capability-aware fields ===
  /** ChannelMode — mcp_only (default) / epf / cfe. Определяет какие cards доступны. */
  mode?: 'mcp_only' | 'epf' | 'cfe';
  /** Версия конфигурации УТ/ERP/КА — «УТ 11.5» / «ERP 2.5» / null. */
  configuration?: string | null;
  /** Версия платформы 1С — «8.3.27.1989». */
  platform?: string | null;
  /** Версия нашего расширения АналитикПлюс (для CFE канала). */
  ext_version?: string | null;
  /** Capability strings из MCP experimental.analyst-1c.features — 23 capability matrix. */
  capabilities?: string[];
  /** 12-char slug fingerprint для shared knowledge corpus. */
  fingerprint?: string | null;
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

// M-K3.17.7: Knowledge Graph card (L2). Payload = форма get_subgraph.to_dict().
export type GraphNodePayload = {
  id: number;
  node_kind: string;
  qualified_name: string;
  source_path?: string | null;
  depth: number;
  attributes?: Record<string, unknown>;
};

export type GraphEdgePayload = {
  src_id: number;
  dst_id: number;
  edge_kind: string;
};

export type GraphCardPayload = {
  center: { qualified_name: string; node_kind: string } | null;
  nodes: GraphNodePayload[];
  edges: GraphEdgePayload[];
  total_reached: number;
  truncated: boolean;
  tool_name?: string;
  card_id?: string | null;
};

// Card discriminated union — для рендеринга inline-карточек в AssistantMessage
export type CardEnvelope =
  | { type: "table"; payload: TableCardPayload }
  | { type: "object"; payload: ObjectCardPayload }
  | { type: "log"; payload: LogCardPayload }
  | { type: "metric"; payload: MetricCardPayload }
  | { type: "references"; payload: ReferencesCardPayload }
  | { type: "code"; payload: CodeCardPayload }
  | { type: "graph"; payload: GraphCardPayload };

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
  /** F-11: закреплён ли чат (всплывает наверх списка). */
  pinned?: boolean;
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

// --- LLM Config backend types (Plan 5.1) ---
// Зеркало backend Pydantic моделей. LLMConfig (выше) остаётся для legacy localStorage path.

export type LLMConfigResponse = {
  id: "default";
  endpoint: string;
  model: string;
  temperature: number;
  updated_at?: string | null;
  /**
   * True если backend получит API-ключ из env DEFAULT_LLM_API_KEY когда
   * frontend его не передаст. UI на основании этого флага не требует ввода
   * ключа в форме настроек и в /chat (один раз прописал в .env — больше
   * не возвращаешься).
   */
  has_env_api_key?: boolean;
};

export type LLMConfigCreate = {
  endpoint: string;
  model: string;
  temperature: number;
};

export type LLMConfigUpdate = {
  endpoint?: string;
  model?: string;
  temperature?: number;
};

export type LLMConfigTestResponse = {
  ok: boolean;
  error_code?: string | null;
  error_message?: string | null;
  duration_ms?: number | null;
};

// --- Sprint 1 (Hermes): Memory ---

export type MemoryNamespacePayload = {
  content: string;
  chars: number;
};

export type MemoryDocument = {
  channel_id: string;
  agent: MemoryNamespacePayload;
  user: MemoryNamespacePayload;
  safe: boolean;
};

export type MemoryUpdateRequest = {
  namespace: "agent" | "user";
  content: string;
};

export type MemoryUpdateResponse = {
  namespace: "agent" | "user";
  chars_written: number;
  threats_found: string[];
};

// Sprint 3 (Hermes A8/A9/A6/D3): Skills + Curator + Todos.

export type SkillDTO = {
  id: string;
  body: string;
  provenance: "agent" | "user";
  tags: string[];
  created_at: string;
  updated_at: string;
  pinned: boolean;
  archived: boolean;
  chars: number;
  usage_count: number;
  last_used_iso: string | null;
};

export type SkillListResponse = {
  channel_id: string;
  active: SkillDTO[];
  archived: SkillDTO[];
};

export type SkillCreateRequest = {
  id?: string;
  body: string;
  tags?: string[];
  pinned?: boolean;
};

export type CuratorReport = {
  inspected: number;
  archived: string[];
  skipped_pinned: string[];
  skipped_user: string[];
  skipped_recent: string[];
  backup_label: string | null;
};

export type TodoDTO = {
  id: string;
  text: string;
  status: "pending" | "in_progress" | "completed" | "cancelled";
  created_at: string;
  completed_at: string | null;
};

export type TodoListResponse = {
  session_id: string;
  items: TodoDTO[];
  active_count: number;
};

// Sprint 4 (Hermes D1/G8): Clarify + Insights.

export type ClarifyRequiredPayload = {
  clarify_id: string;
  question: string;
  options: string[];
  multi: boolean;
  allow_custom: boolean;
};

export type InsightsPeriod = "24h" | "7d" | "30d" | "all";

export type InsightsToolStat = {
  name: string;
  calls: number;
  errors: number;
  error_rate: number;
};

export type InsightsChannelStat = {
  channel_id: string;
  sessions: number;
  messages: number;
};

export type InsightsResponse = {
  period: string;
  generated_at: string;
  sessions: number;
  messages: number;
  tool_calls_total: number;
  tool_errors_total: number;
  avg_duration_ms: number | null;
  top_channels: InsightsChannelStat[];
  top_tools: InsightsToolStat[];
  // Sprint 5 (I4): estimated tokens + cost.
  estimated_tokens: number;
  estimated_cost_usd: number;
};

export type TrajectoryStats = {
  enabled: boolean;
  root: string;
  sample_count: number;
  failed_count: number;
};
