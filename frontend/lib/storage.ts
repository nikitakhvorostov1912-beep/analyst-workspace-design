import type { LLMConfig, MCPConnection } from "./types";

const KEY_LLM = "analyst.llm";
const KEY_MCP = "analyst.mcp_connections";
const KEY_ACTIVE_CHANNEL = "analyst.active_channel";

// SSR-safe helper: возвращает null если не в браузере
function safeLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

/**
 * @deprecated Используйте fetchLLMConfig() из lib/api.ts (Plan 5.4 UX-04).
 * Оставлено для обратной совместимости с тестами Phase 1-4.
 * localStorage держит только: active_channel, anon_enabled, onboarding_completed.
 */
export function getLLMConfig(): LLMConfig | null {
  const ls = safeLocalStorage();
  if (!ls) return null;
  try {
    const raw = ls.getItem(KEY_LLM);
    if (!raw) return null;
    return JSON.parse(raw) as LLMConfig;
  } catch {
    return null;
  }
}

/**
 * @deprecated Используйте saveLLMConfig() из lib/api.ts (Plan 5.4 UX-04).
 * Оставлено для обратной совместимости с тестами Phase 1-4.
 */
export function setLLMConfig(cfg: LLMConfig): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  ls.setItem(KEY_LLM, JSON.stringify(cfg));
}

/**
 * @deprecated Используйте fetchConnections() из lib/api.ts (Plan 5.4 UX-04).
 * Оставлено для offline-fallback в ChannelSelector и backward compat с тестами Phase 1-4.
 */
export function getMCPConnections(): MCPConnection[] {
  const ls = safeLocalStorage();
  if (!ls) return [];
  try {
    const raw = ls.getItem(KEY_MCP);
    if (!raw) return [];
    return JSON.parse(raw) as MCPConnection[];
  } catch {
    return [];
  }
}

/**
 * @deprecated Используйте createConnection()/updateConnection() из lib/api.ts (Plan 5.4 UX-04).
 * Оставлено для syncMCPConnections (offline-cache) и backward compat с тестами Phase 1-4.
 */
export function setMCPConnections(conns: MCPConnection[]): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  ls.setItem(KEY_MCP, JSON.stringify(conns));
}

/**
 * Синхронизирует localStorage-кеш после успешного backend CRUD.
 * Используется как offline-fallback: если backend недоступен, показываем последний известный список.
 */
export function syncMCPConnections(conns: MCPConnection[]): void {
  setMCPConnections(conns);
}

export function getActiveChannelId(): string | null {
  const ls = safeLocalStorage();
  if (!ls) return null;
  return ls.getItem(KEY_ACTIVE_CHANNEL);
}

export function setActiveChannelId(id: string | null): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  if (id === null) {
    ls.removeItem(KEY_ACTIVE_CHANNEL);
  } else {
    ls.setItem(KEY_ACTIVE_CHANNEL, id);
  }
}

// --- Anonymization toggle (Plan 04-01) ---

const KEY_ANON_ENABLED = "analyst.anon_enabled";

/**
 * Читает флаг анонимизации из localStorage.
 * Возвращает false если не установлен или в SSR-контексте.
 */
export function getAnonEnabled(): boolean {
  const ls = safeLocalStorage();
  if (!ls) return false;
  return ls.getItem(KEY_ANON_ENABLED) === "true";
}

/**
 * Записывает флаг анонимизации в localStorage.
 */
export function setAnonEnabled(enabled: boolean): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  ls.setItem(KEY_ANON_ENABLED, enabled ? "true" : "false");
}
