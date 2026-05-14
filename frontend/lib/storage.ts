import type { LLMConfig, MCPConnection } from "./types";

const KEY_LLM = "analyst.llm";
const KEY_MCP = "analyst.mcp_connections";
const KEY_ACTIVE_CHANNEL = "analyst.active_channel";

// SSR-safe helper: возвращает null если не в браузере
function safeLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

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

export function setLLMConfig(cfg: LLMConfig): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  ls.setItem(KEY_LLM, JSON.stringify(cfg));
}

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

export function setMCPConnections(conns: MCPConnection[]): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  ls.setItem(KEY_MCP, JSON.stringify(conns));
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
