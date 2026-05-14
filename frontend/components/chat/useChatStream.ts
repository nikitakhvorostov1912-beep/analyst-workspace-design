"use client";

import { useCallback, useState } from "react";
import { fetchChat } from "@/lib/api";
import type { CardEnvelope, ChatMessage, ToolCallRecord } from "@/lib/types";

export type UseChatStreamOptions = {
  sessionId: string;
  channelId: string;
  initialMessages?: ChatMessage[];
};

export type UseChatStreamReturn = {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  send: (text: string) => Promise<void>;
};

/**
 * Hook управления SSE-стримом чата.
 *
 * Принимает initialMessages (из history) и добавляет новые по мере стриминга.
 * Обрабатывает все 7 SSE-событий: status/delta/tool_call/tool_result/card/done/error.
 */
export function useChatStream({
  sessionId,
  channelId,
  initialMessages = [],
}: UseChatStreamOptions): UseChatStreamReturn {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

      try {
        const stream = fetchChat({
          message: text,
          session_id: sessionId,
          channel_id: channelId,
        });

        for await (const event of stream) {
          if (event.event === "delta") {
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
            setIsStreaming(false);
          } else if (event.event === "error") {
            setError(event.data.message);
            setIsStreaming(false);
            break;
          }
          // status events — пропускаем (нет UI для них в Phase 2)
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Неизвестная ошибка";
        setError(msg);
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming, sessionId, channelId],
  );

  return { messages, isStreaming, error, send };
}
