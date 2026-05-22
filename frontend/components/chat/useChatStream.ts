"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchChat, fetchLLMConfig, interruptChat, postChatClarify, postChatConfirm } from "@/lib/api";
import { publishToast } from "@/lib/toast";
import { getAnonEnabled } from "@/lib/storage";
import type {
  CardEnvelope,
  ChatAttachment,
  ChatMessage,
  ClarifyRequiredPayload,
  ConfirmRequiredPayload,
  ErrorCode,
  ToolCallRecord,
} from "@/lib/types";
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
  /** Sprint 4 (D1): Pending clarify — backend ждёт ответ на clarify_question. */
  pendingClarify: ClarifyRequiredPayload | null;
  /** Отвечает на pending clarify — POST /chat/clarify. */
  resolveClarify: (answer: string | string[]) => Promise<void>;
  send: (text: string, attachments?: ChatAttachment[]) => Promise<void>;
  /** Sprint 2 (Hermes C9): прерывает текущий стрим. Backend сохранит частичный ответ. */
  interrupt: () => Promise<void>;
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
  const [pendingClarify, setPendingClarify] = useState<ClarifyRequiredPayload | null>(null);

  // W1.7 (2026-05-22): AbortController для отмены SSE-стрима при unmount/
  // навигации. Раньше async generator продолжал работу после размонтирования
  // компонента и вызывал setState на убитом инстансе — утечка памяти +
  // spurious re-renders + потенциальный crash.
  // mountedRef блокирует setState ПОСЛЕ unmount (вторая защита).
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef<boolean>(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // Отменяем активный стрим на размонтировании / закрытии вкладки
      abortRef.current?.abort();
    };
  }, []);

  // Сброс state при смене сессии. Без этого Next.js не размонтирует страницу
  // [id] при навигации между /sessions/A → /sessions/B — useChatStream
  // остаётся тот же инстанс и держит messages предыдущей сессии.
  // Также подхватываем initialMessages когда они приходят асинхронно (после
  // fetchSessionMessages родитель setInitialMessages).
  const lastSessionIdRef = useRef<string>(sessionId);
  useEffect(() => {
    if (lastSessionIdRef.current !== sessionId) {
      // Новая сессия — полный сброс. W1.7: отменяем активный стрим
      // предыдущей сессии перед сбросом state, чтобы поздние SSE-события
      // не сбивали историю новой сессии.
      abortRef.current?.abort();
      abortRef.current = null;
      lastSessionIdRef.current = sessionId;
      setMessages(initialMessages);
      setIsStreaming(false);
      setError(null);
      setStreamingStage(null);
      setCurrentToolName(null);
      setPendingConfirm(null);
      return;
    }
    // Та же сессия — обновляем messages если initialMessages пришли позже
    // (родитель загружает их асинхронно, при первом рендере пустой массив).
    if (initialMessages.length > 0 && messages.length === 0) {
      setMessages(initialMessages);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, initialMessages]);

  const send = useCallback(
    async (text: string, attachments?: ChatAttachment[]): Promise<void> => {
      if (isStreaming) return;

      setError(null);

      const now = new Date().toISOString();

      // 1. Добавляем user message. Для UI рендерим оригинальный текст +
      // компактный список прикреплённых файлов в конце (LLM получает полный
      // извлечённый текст на backend — там содержимое склеивается).
      const attachmentNote =
        attachments && attachments.length > 0
          ? "\n\n" +
            attachments
              .map((a) => `📎 ${a.name}`)
              .join("\n")
          : "";
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: text + attachmentNote,
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

      // W1.7: создаём fresh AbortController для этого стрима. Если предыдущий
      // ещё активен (defensive) — отменяем его.
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;

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
            attachments: attachments && attachments.length > 0 ? attachments : undefined,
          },
          {
            endpoint: llmConfig.endpoint,
            model: llmConfig.model,
            // Если backend получит ключ из env — фронт не должен ругаться при
            // пустом localStorage и должен слать запрос без X-LLM-API-Key.
            hasEnvKey: Boolean(llmConfig.has_env_api_key),
          },
          ac.signal,  // W1.7: signal от AbortController — fetch отменяется при unmount
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
          } else if (event.event === "clarify_required") {
            // Sprint 4 (D1): LLM попросила уточнение
            setPendingClarify(event.data);
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
        // W1.7: AbortError при unmount/navigation — не ошибка, не показываем
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        // Также игнорируем setState на размонтированном компоненте
        if (!mountedRef.current) {
          return;
        }
        const msg = err instanceof Error ? err.message : "Неизвестная ошибка";
        setError(msg);
      } finally {
        // W1.7: setState только если ещё mounted (после await loop'а компонент
        // мог размонтироваться)
        if (mountedRef.current) {
          setIsStreaming(false);
          setStreamingStage(null);
        }
        // Очищаем AbortController если это был наш текущий
        if (abortRef.current === ac) {
          abortRef.current = null;
        }
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

  const resolveClarify = useCallback(
    async (answer: string | string[]): Promise<void> => {
      if (!pendingClarify) return;
      const { clarify_id } = pendingClarify;
      try {
        await postChatClarify({ clarify_id, answer });
      } finally {
        setPendingClarify(null);
      }
    },
    [pendingClarify],
  );

  const interrupt = useCallback(async (): Promise<void> => {
    if (!sessionId || !isStreaming) return;
    try {
      await interruptChat(sessionId);
    } catch (err) {
      // Не падаем визуально — backend уже мог завершить loop сам.
      publishToast({
        type: "warning",
        message: err instanceof Error ? err.message : "Не удалось остановить запрос",
      });
    }
  }, [sessionId, isStreaming]);

  return {
    messages,
    isStreaming,
    error,
    streamingStage,
    currentToolName,
    pendingConfirm,
    resolveConfirm,
    pendingClarify,
    resolveClarify,
    send,
    interrupt,
  };
}
