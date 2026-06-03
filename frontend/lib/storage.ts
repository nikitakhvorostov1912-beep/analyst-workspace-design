import type { Environment, LLMConfig, MCPConnection } from "./types";

const KEY_LLM = "analyst.llm";
const KEY_MCP = "analyst.mcp_connections";
const KEY_ACTIVE_CHANNEL = "analyst.active_channel";
const KEY_ACTIVE_TYPICAL = "analyst.active_typical";

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
  // 2026-05-24: уведомляем подписчиков (AnonymizationStatus, …) что
  // активная база сменилась. Без этого header'овые chips оставались
  // с данными предыдущего канала пока юзер не перезагрузит страницу.
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("active-channel-changed", { detail: { id } }),
    );
  }
}

// --- M-K2.5.7: активная типовая конфигурация для compare/explain ---

/** Возвращает channel_id выбранной типовой (`_bp30_138_24` и т.п.) или null. */
export function getActiveTypicalChannelId(): string | null {
  const ls = safeLocalStorage();
  if (!ls) return null;
  return ls.getItem(KEY_ACTIVE_TYPICAL);
}

/** Сохраняет активную типовую. null → удаляет ключ. */
export function setActiveTypicalChannelId(id: string | null): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  if (id === null) {
    ls.removeItem(KEY_ACTIVE_TYPICAL);
  } else {
    ls.setItem(KEY_ACTIVE_TYPICAL, id);
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("active-typical-changed", { detail: { id } }),
    );
  }
}

// --- Окружение подключений (shell v3 §5, Вариант B) ---
//
// Backend не отдаёт environment (нет надёжного сигнала prod/test — обе базы
// на localhost:6010). Пользователь помечает базу в форме подключения; храним
// map { connectionId -> "prod"|"test"|"demo" } в localStorage и мёржим при
// чтении connections. Снятие метки удаляет ключ из map.

const KEY_CONNECTION_ENV = "analyst.connection_env";

function readEnvMap(): Record<string, Environment> {
  const ls = safeLocalStorage();
  if (!ls) return {};
  try {
    const raw = ls.getItem(KEY_CONNECTION_ENV);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

/** Окружение подключения из localStorage. null если не помечено. */
export function getConnectionEnvironment(id: string): Environment | null {
  const map = readEnvMap();
  const v = map[id];
  return v === "prod" || v === "test" || v === "demo" ? v : null;
}

/** Помечает/снимает окружение подключения. null → удаляет метку. */
export function setConnectionEnvironment(id: string, env: Environment | null): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  const map = readEnvMap();
  if (env === null) {
    delete map[id];
  } else {
    map[id] = env;
  }
  ls.setItem(KEY_CONNECTION_ENV, JSON.stringify(map));
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("connections-updated", { detail: { id, env } }),
    );
  }
}

// --- Anonymization toggle (Plan 04-01) — DEPRECATED 2026-05-24 ---
//
// Источник истины — `MCPConnection.anon_enabled` (приходит из обработки 1С
// через backend ping). UI больше не имеет toggle. Legacy helper'ы оставлены
// чтобы не сломать тесты `useChatStream.test.tsx` (mock'ает имена) —
// при следующей чистке убрать вместе с моками.

const KEY_ANON_ENABLED = "analyst.anon_enabled";

/** @deprecated Используй `MCPConnection.anon_enabled`. */
export function getAnonEnabled(): boolean {
  const ls = safeLocalStorage();
  if (!ls) return false;
  return ls.getItem(KEY_ANON_ENABLED) === "true";
}

/** @deprecated Заданно в обработке 1С, UI не имеет права менять. */
export function setAnonEnabled(enabled: boolean): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  ls.setItem(KEY_ANON_ENABLED, enabled ? "true" : "false");
}
