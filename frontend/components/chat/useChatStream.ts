"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchChat,
  interruptChat,
  postChatClarify,
  postChatConfirm,
} from "@/lib/api";
import { useConfigCache } from "@/lib/config-cache";
import { publishToast } from "@/lib/toast";
import type {
  CardEnvelope,
  ChatAttachment,
  ChatMessage,
  ClarifyRequiredPayload,
  ConfirmRequiredPayload,
  ErrorCode,
  ToolCallRecord,
} from "@/lib/types";
import type { StreamingStage } from "@/lib/streaming-stages";

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
  /** Время старта текущего стрима (Date.now()) для живого таймера; null если не стримим. */
  streamStartedAt: number | null;
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
  "llm_region_blocked",
]);

/**
 * PERF: пауза между сбросами буфера дельт во время стрима (мс). setMessages на
 * КАЖДЫЙ SSE-токен заставлял ReactMarkdown пере-парсить весь растущий ответ
 * десятки раз в секунду → O(N²) на main-thread → UI «зависает», скролл мёртв.
 * Копим дельты и применяем пачкой не чаще раза в DELTA_FLUSH_MS (~15 ре-парсов/с).
 */
const DELTA_FLUSH_MS = 64;

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
  // PERF-3 (M-K0.3): кэш llm-config и connections через React Context —
  // раньше каждый send делал 2 лишних HTTP roundtrip.
  const configCache = useConfigCache();
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingStage, setStreamingStage] = useState<StreamingStage | null>(null);
  const [currentToolName, setCurrentToolName] = useState<string | null>(null);
  const [streamStartedAt, setStreamStartedAt] = useState<number | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<ConfirmRequiredPayload | null>(null);
  const [pendingClarify, setPendingClarify] = useState<ClarifyRequiredPayload | null>(null);

  // W1.7 (2026-05-22): AbortController для отмены SSE-стрима при unmount/
  // навигации. Раньше async generator продолжал работу после размонтирования
  // компонента и вызывал setState на убитом инстансе — утечка памяти +
  // spurious re-renders + потенциальный crash.
  // mountedRef блокирует setState ПОСЛЕ unmount (вторая защита).
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef<boolean>(true);

  // PERF: буфер дельт + таймер сброса (throttle ре-рендера разметки во время стрима)
  const pendingDeltaRef = useRef<string>("");
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // Отменяем активный стрим на размонтировании / закрытии вкладки
      abortRef.current?.abort();
      if (flushTimerRef.current !== null) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
    };
  }, []);

  // PERF: применяет накопленные дельты одним setMessages и гасит таймер.
  // Вызывается по таймеру (DELTA_FLUSH_MS) и принудительно на терминальных
  // событиях (done/error/обрыв стрима), чтобы не потерять хвост ответа.
  const flushPendingDelta = useCallback(() => {
    if (flushTimerRef.current !== null) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    const pending = pendingDeltaRef.current;
    if (!pending) return;
    pendingDeltaRef.current = "";
    if (!mountedRef.current) return;
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (!last || last.role !== "assistant") return prev;
      return [...prev.slice(0, -1), { ...last, content: last.content + pending }];
    });
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
      // Сбрасываем throttle-буфер прошлой сессии
      pendingDeltaRef.current = "";
      if (flushTimerRef.current !== null) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
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
      setStreamStartedAt(Date.now());

      // W1.7: создаём fresh AbortController для этого стрима. Если предыдущий
      // ещё активен (defensive) — отменяем его.
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;

      try {
        // PERF-3 (M-K0.3): через configCache — кэш в провайдере, fallback на
        // прямой fetch когда провайдер не подключён (тесты, isolated render).
        const llmConfig = await configCache.getLLMConfig();
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

        // 2026-05-24: источник истины для анонимизации — поле `anon_enabled`
        // активного MCPConnection (задаётся в обработке 1С, синхронизируется
        // через backend). Раньше читали из localStorage `analyst.anon_enabled`
        // (user toggle) — это была некорректная модель, UI не должен решать.
        let anonHeaders: Record<string, string> = {};
        try {
          const conns = await configCache.getConnections();
          const active = conns.find((c) => c.id === channelId);
          if (active?.anon_enabled) {
            anonHeaders = { "X-Anon-Enabled": "true" };
          }
        } catch {
          // backend недоступен — отправляем без anon-header (default behavior)
        }

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
            // PERF: НЕ setMessages на каждый токен — копим в буфер, сбрасываем
            // пачкой по таймеру. Иначе разметка пере-парсится на каждый токен.
            pendingDeltaRef.current += event.data.content;
            if (flushTimerRef.current === null) {
              flushTimerRef.current = setTimeout(flushPendingDelta, DELTA_FLUSH_MS);
            }
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
            flushPendingDelta(); // добиваем буфер дельт перед финализацией
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
            flushPendingDelta(); // сохраняем частичный ответ рядом с ошибкой
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
        flushPendingDelta(); // сохраняем частичный ответ перед показом ошибки
        const msg = err instanceof Error ? err.message : "Неизвестная ошибка";
        // Отличаем баги рендера/программные ошибки React от реальных сетевых
        // сбоев. React-ошибки («Maximum update depth» и т.п.) НЕ показываем
        // аналитику сырым текстом — это пугает и бесполезно; даём понятное
        // сообщение, а сырое пишем в console для диагностики (там же стек).
        const isRenderBug =
          /Maximum update depth|Minified React error|Rendered (more|fewer) hooks|Should have a queue|while rendering a different component/i.test(
            msg,
          );
        if (isRenderBug) {
          console.error(
            "[useChatStream] неожиданная ошибка рендера во время стрима:",
            err,
          );
        }
        const userMessage = isRenderBug
          ? "Не удалось отобразить ответ. Обновите страницу."
          : msg;
        const errorCode = isRenderBug ? "internal_error" : "llm_network_error";
        setError(userMessage);
        // Громкий сигнал в пузыре: транспорт/SSL-падение легко пропустить в
        // крошечной строке у композера — дублируем в message.error.
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (!last || last.role !== "assistant") return prev;
          return [
            ...prev.slice(0, -1),
            { ...last, error: { message: userMessage, code: errorCode } },
          ];
        });
      } finally {
        // PERF: на любом завершении стрима (в т.ч. обрыв без done) добиваем
        // буфер дельт, иначе хвост ответа потеряется.
        flushPendingDelta();
        // W1.7: setState только если ещё mounted (после await loop'а компонент
        // мог размонтироваться)
        if (mountedRef.current) {
          setIsStreaming(false);
          setStreamingStage(null);
          setStreamStartedAt(null);
        }
        // Очищаем AbortController если это был наш текущий
        if (abortRef.current === ac) {
          abortRef.current = null;
        }
      }
    },
    [isStreaming, sessionId, channelId, onBannerShow, onBannerHide, configCache, flushPendingDelta],
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
    streamStartedAt,
    currentToolName,
    pendingConfirm,
    resolveConfirm,
    pendingClarify,
    resolveClarify,
    send,
    interrupt,
  };
}
