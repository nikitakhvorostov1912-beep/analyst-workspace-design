"use client";

import { useCallback, useState } from "react";
import { fetchChat, fetchLLMConfig, postChatConfirm } from "@/lib/api";
import { publishToast } from "@/lib/toast";
import { getAnonEnabled } from "@/lib/storage";
import type { CardEnvelope, ChatMessage, ConfirmRequiredPayload, ErrorCode, ToolCallRecord } from "@/lib/types";
import type { StreamingStage } from "./StreamingIndicator";

export type UseChatStreamOptions = {
  sessionId: string;
  channelId: string;
  initialMessages?: ChatMessage[];
  /** Вызывается при event:error c MCP-кодом — показать ConnectionStatusBanner */
  onBannerShow?: (channelId: string) => void;
  /** Вызывается при event:done после bannerVisible */
  onBannerHide?: () => void;
};

export type UseChatStreamReturn = {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  streamingStage: StreamingStage | null;
  currentToolName: string | null;
  /** Pending confirm payload — если backend ожидает подтверждения (SEC-01) */
  pendingConfirm: ConfirmRequiredPayload | null;
  /** Отвечает на pending confirm — POST /chat/confirm */
  resolveConfirm: (approved: boolean) => Promise<void>;
  send: (text: string) => Promise<void>;
};

/** Коды ошибок, которые маршрутизируются в ConnectionStatusBanner */
const MCP_ERROR_CODES = new Set<ErrorCode>(["mcp_disconnected", "mcp_connect_error"]);

/** Коды ошибок, которые маршрутизируются в Toaster */
const LLM_ERROR_CODES = new Set<ErrorCode>([
  "llm_rate_limit",
  "llm_invalid_key",
  "llm_network_error",
  "llm_server_error",
]);

/**
 * Hook управления SSE-стримом чата.
 *
 * Принимает initialMessages (из history) и добавляет новые по мере стриминга.
 * Обрабатывает все 7 SSE-событий + маршрутизацию ошибок (Plan 03-01).
 */
export function useChatStream({
  sessionId,
  channelId,
  initialMessages = [],
  onBannerShow,
  onBannerHide,
}: UseChatStreamOptions): UseChatStreamReturn {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingStage, setStreamingStage] = useState<StreamingStage | null>(null);
  const [currentToolName, setCurrentToolName] = useState<string | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<ConfirmRequiredPayload | null>(null);

  const send = useCallback(
    async (text: string): Promise<void> => {
      if (isStreaming) return;

      setError(null);

      const now = new Date().toISOString();

      // 1. Добавляем user message
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        created_at: now,
      };

      // 2. Добавляем placeholder для assistant
      const tempAssistantId = crypto.randomUUID();
      const placeholderAssistant: ChatMessage = {
        id: tempAssistantId,
        role: "assistant",
        content: "",
        created_at: now,
        cards: [],
        tool_calls: [],
      };

      setMessages((prev) => [...prev, userMsg, placeholderAssistant]);
      setIsStreaming(true);
      setStreamingStage(null);
      setCurrentToolName(null);

      try {
        // Получаем LLM конфиг из backend (source-of-truth, Plan 5.4 UX-04)
        // Один дополнительный round-trip при отправке — приемлемо (T-05-14 accept)
        const llmConfig = await fetchLLMConfig();
        if (!llmConfig) {
          setError("LLM не настроен. Откройте Настройки.");
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (!last || last.role !== "assistant") return prev;
            return [
              ...prev.slice(0, -1),
              { ...last, error: { message: "LLM не настроен. Откройте Настройки.", code: "no_api_key" } },
            ];
          });
          setIsStreaming(false);
          return;
        }

        // Читаем флаг анонимизации в момент отправки (не кешируем — toggle мог измениться)
        const anonHeaders: Record<string, string> = getAnonEnabled()
          ? { "X-Anon-Enabled": "true" }
          : {};

        const stream = fetchChat(
          {
            message: text,
            session_id: sessionId,
            channel_id: channelId,
          },
          { endpoint: llmConfig.endpoint, model: llmConfig.model },
          undefined,
          anonHeaders,
        );

        for await (const event of stream) {
          if (event.event === "status") {
            setStreamingStage(event.data.stage);
          } else if (event.event === "delta") {
            const content = event.data.content;
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== "assistant") return prev;
              return [
                ...prev.slice(0, -1),
                { ...last, content: last.content + content },
              ];
            });
          } else if (event.event === "tool_call") {
            setCurrentToolName(event.data.name);
            const tc: ToolCallRecord = {
              id: event.data.id,
              name: event.data.name,
              args: event.data.args,
            };
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== "assistant") return prev;
              const existingCalls = last.tool_calls ?? [];
              return [
                ...prev.slice(0, -1),
                { ...last, tool_calls: [...existingCalls, tc] },
              ];
            });
          } else if (event.event === "tool_result") {
            const { id, ok, result, error: toolError, duration_ms } = event.data;
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== "assistant") return prev;
              const calls = (last.tool_calls ?? []).map((tc) =>
                tc.id === id
                  ? { ...tc, result, ok, duration_ms, error: toolError }
                  : tc,
              );
              return [...prev.slice(0, -1), { ...last, tool_calls: calls }];
            });
          } else if (event.event === "card") {
            const card = event.data as CardEnvelope;
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== "assistant") return prev;
              const existingCards = last.cards ?? [];
              return [
                ...prev.slice(0, -1),
                { ...last, cards: [...existingCards, card] },
              ];
            });
          } else if (event.event === "confirm_required") {
            // SEC-01: backend ждёт подтверждения опасного execute_code
            setPendingConfirm(event.data);
            // Цикл продолжается — SSE-стрим живёт, backend ждёт POST /chat/confirm
          } else if (event.event === "done") {
            const { message_id, total_duration_ms } = event.data;
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== "assistant") return prev;
              return [
                ...prev.slice(0, -1),
                { ...last, id: message_id, duration_ms: total_duration_ms },
              ];
            });
            setStreamingStage(null);
            setCurrentToolName(null);
            setIsStreaming(false);
            onBannerHide?.();
          } else if (event.event === "error") {
            const { code, message } = event.data;
            const retryAfterS = event.data.retry_after_s;

            if (MCP_ERROR_CODES.has(code)) {
              // MCP ошибка → ConnectionStatusBanner
              onBannerShow?.(channelId);
              setIsStreaming(false);
              setStreamingStage(null);
              break;
            } else if (LLM_ERROR_CODES.has(code)) {
              // LLM ошибка → Toaster + inline error на placeholder
              publishToast({
                type: code === "llm_rate_limit" ? "warning" : "error",
                message,
                countdownSeconds:
                  retryAfterS != null ? retryAfterS : undefined,
              });
              // Записываем inline error в assistant placeholder
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (!last || last.role !== "assistant") return prev;
                return [
                  ...prev.slice(0, -1),
                  { ...last, error: { message, code } },
                ];
              });
              setIsStreaming(false);
              setStreamingStage(null);
              break;
            } else {
              // Прочие ошибки → inline в setError + inline на placeholder
              setError(message);
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (!last || last.role !== "assistant") return prev;
                return [
                  ...prev.slice(0, -1),
                  { ...last, error: { message, code } },
                ];
              });
              setIsStreaming(false);
              setStreamingStage(null);
              break;
            }
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Неизвестная ошибка";
        setError(msg);
      } finally {
        setIsStreaming(false);
        setStreamingStage(null);
      }
    },
    [isStreaming, sessionId, channelId, onBannerShow, onBannerHide],
  );

  const resolveConfirm = useCallback(
    async (approved: boolean): Promise<void> => {
      if (!pendingConfirm) return;
      const { tool_call_id } = pendingConfirm;
      try {
        await postChatConfirm({ tool_call_id, approved });
      } finally {
        // Очищаем pending независимо от результата
        setPendingConfirm(null);
      }
    },
    [pendingConfirm],
  );

  return { messages, isStreaming, error, streamingStage, currentToolName, pendingConfirm, resolveConfirm, send };
}
