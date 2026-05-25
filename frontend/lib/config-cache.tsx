"use client";

/**
 * ConfigCacheProvider — кэш LLM конфига и MCP подключений на уровне React Context.
 *
 * PERF-3 (M-K0.3): раньше useChatStream на КАЖДЫЙ send в чат делал 2 отдельных
 * HTTP запроса (GET /llm-config + GET /connections) перед собственно POST /chat
 * — лишние 100-300мс на каждое сообщение + нагрузка на backend. Эти данные
 * меняются только при сохранении в Settings/MCPConnectionForm, а не во время
 * стриминга.
 *
 * Решение: in-memory кэш с явным invalidate. Когда юзер сохраняет настройки
 * (LLMConfigForm.handleSave / MCPConnectionForm.handleSave) — вызывает
 * invalidateLLMConfig() / invalidateConnections(), и следующий get делает
 * fresh fetch.
 *
 * Совместимость: useConfigCache() работает БЕЗ провайдера (fallback на
 * прямой fetch) — это значит существующие vitest-ы useChatStream не
 * сломаются. Поведение кэша включается только когда Provider обёрнут в
 * app/layout.tsx.
 */

import { createContext, useCallback, useContext, useRef, type ReactNode } from "react";

import { fetchConnections, fetchLLMConfig } from "@/lib/api";
import type { LLMConfigResponse, MCPConnection } from "@/lib/types";

type LLMConfigCache = LLMConfigResponse | null;
type ConnectionsCache = MCPConnection[];

export interface ConfigCacheValue {
  /** Возвращает LLM конфиг — из кэша или fresh fetch при miss/invalidated. */
  getLLMConfig: () => Promise<LLMConfigCache>;
  /** Возвращает список подключений — из кэша или fresh fetch. */
  getConnections: () => Promise<ConnectionsCache>;
  /** Сбрасывает кэш LLM конфига — следующий get сделает fresh fetch. */
  invalidateLLMConfig: () => void;
  /** Сбрасывает кэш подключений. */
  invalidateConnections: () => void;
}

const ConfigCacheContext = createContext<ConfigCacheValue | null>(null);

interface CacheSlot<T> {
  value: T | undefined;
  /** In-flight promise — защита от одновременных запросов (request coalescing). */
  pending: Promise<T> | null;
}

export function ConfigCacheProvider({ children }: { children: ReactNode }) {
  // Используем useRef чтобы кэш не вызывал ре-рендер при обновлении.
  // Кэш — это не состояние UI; UI читает его только через async-методы.
  const llmSlot = useRef<CacheSlot<LLMConfigCache>>({ value: undefined, pending: null });
  const connSlot = useRef<CacheSlot<ConnectionsCache>>({ value: undefined, pending: null });

  const getLLMConfig = useCallback(async (): Promise<LLMConfigCache> => {
    const slot = llmSlot.current;
    if (slot.value !== undefined) return slot.value;
    if (slot.pending) return slot.pending;
    slot.pending = fetchLLMConfig()
      .then((fresh) => {
        slot.value = fresh;
        return fresh;
      })
      .finally(() => {
        slot.pending = null;
      });
    return slot.pending;
  }, []);

  const getConnections = useCallback(async (): Promise<ConnectionsCache> => {
    const slot = connSlot.current;
    if (slot.value !== undefined) return slot.value;
    if (slot.pending) return slot.pending;
    slot.pending = fetchConnections()
      .then((fresh) => {
        slot.value = fresh;
        return fresh;
      })
      .finally(() => {
        slot.pending = null;
      });
    return slot.pending;
  }, []);

  const invalidateLLMConfig = useCallback(() => {
    llmSlot.current.value = undefined;
  }, []);

  const invalidateConnections = useCallback(() => {
    connSlot.current.value = undefined;
  }, []);

  return (
    <ConfigCacheContext.Provider
      value={{ getLLMConfig, getConnections, invalidateLLMConfig, invalidateConnections }}
    >
      {children}
    </ConfigCacheContext.Provider>
  );
}

/**
 * Хук доступа к кэшу. Без провайдера возвращает no-op fallback (прямой fetch на
 * каждый вызов, без кэширования) — backward-compat для тестов и любого UI,
 * не обёрнутого в провайдер.
 */
export function useConfigCache(): ConfigCacheValue {
  const ctx = useContext(ConfigCacheContext);
  if (ctx) return ctx;
  // Fallback — поведение «как было до PERF-3».
  return {
    getLLMConfig: fetchLLMConfig,
    getConnections: fetchConnections,
    invalidateLLMConfig: () => {},
    invalidateConnections: () => {},
  };
}
