"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { Thread } from "@/components/chat/Thread";
import { ChatInput } from "@/components/chat/Input";
import { CommandPalette } from "@/components/chat/CommandPalette";
import { ConfirmExecuteDialog } from "@/components/chat/ConfirmExecuteDialog";
import { ClarifyDialog } from "@/components/chat/ClarifyDialog";
import { ConnectionStatusBanner } from "@/components/chat/ConnectionStatusBanner";
import { ExportSessionButton } from "@/components/chat/ExportSessionButton";
import { Skeleton } from "@/components/ui/Skeleton";
import { useChatStream } from "@/components/chat/useChatStream";
import { useSessionsStore } from "@/lib/sessions-store";
import { fetchSessionDetail, fetchSessionMessages, fetchConnections, fetchLLMConfig, pingConnection } from "@/lib/api";
import { getActiveChannelId, setActiveChannelId } from "@/lib/storage";
import { publishToast } from "@/lib/toast";
import { publishUndoToast } from "@/lib/undo-toast";
import type { ChatAttachment, ChatMessage, MCPConnection, SessionDetail } from "@/lib/types";

function messageRowToChat(row: {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_calls?: unknown[] | null;
  cards?: unknown[] | null;
  duration_ms?: number | null;
  created_at: string;
}): ChatMessage {
  return {
    id: row.id,
    role: row.role,
    content: row.content ?? "",
    created_at: row.created_at,
    cards: (row.cards ?? []) as ChatMessage["cards"],
    tool_calls: (row.tool_calls ?? []) as ChatMessage["tool_calls"],
    duration_ms: row.duration_ms ?? undefined,
  };
}

export default function SessionPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [initialMessages, setInitialMessages] = useState<ChatMessage[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [activeChannelId, setLocalActiveChannelId] = useState<string | null>(null);
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  // Кешируем флаг наличия env-ключа в backend. ChatInput использует его чтобы
  // не показывать toast «введите ключ», когда backend подставит ключ из .env.
  const [hasEnvApiKey, setHasEnvApiKey] = useState(false);

  useEffect(() => {
    fetchLLMConfig()
      .then((cfg) => {
        if (cfg) setHasEnvApiKey(Boolean(cfg.has_env_api_key));
      })
      .catch(() => {
        // Тихо игнорим — флаг останется false (старое поведение)
      });
  }, []);

  // Banner state — STATE-02
  const [bannerVisible, setBannerVisible] = useState(false);
  const [bannerChannelName, setBannerChannelName] = useState<string | undefined>(undefined);
  const [bannerRetrying, setBannerRetrying] = useState(false);

  const store = useSessionsStore();

  // Активный channelId для chat-request. Используем activeChannelId
  // (он установлен в load() с fallback на первое рабочее подключение
  // если detail.channel_id битый — например «?1» от v1.2.10).
  // Раньше брался сырой detail.channel_id и backend ловил «канал не найден».
  const channelId = activeChannelId ?? detail?.channel_id ?? getActiveChannelId() ?? "default";

  useEffect(() => {
    setLocalActiveChannelId(getActiveChannelId());

    async function load() {
      try {
        const [sessionDetail, messages, connections] = await Promise.all([
          fetchSessionDetail(id),
          fetchSessionMessages(id),
          fetchConnections().catch(() => [] as MCPConnection[]),
          store.refresh(),
        ]);

        if (sessionDetail === null) {
          // Раньше тихо редиректили на /. Это маскировало BUG #2:
          // когда «+ Новый чат» создаёт сессию и push'ит сюда,
          // но backend ещё не успел закоммитить (race) — юзер
          // отскакивал на main без объяснений. Теперь показываем
          // явную ошибку с кнопкой «Открыть заново».
          setLoadError("Сессия не найдена. Попробуй открыть её из списка слева или создать новую.");
          setReady(true);
          return;
        }

        // Защита от битого channel_id (типично: «?1» от старой версии БД
        // v1.2.10, когда seed мог писать SQL placeholder вместо UUID).
        // Если канал не существует в текущих подключениях — fallback
        // на первое рабочее и явный toast, чтобы юзер не недоумевал
        // «почему написано "Выберите подключение" если у меня есть база».
        const sessionChannelId = sessionDetail.channel_id;
        const channelExists = sessionChannelId
          ? connections.some((c) => c.id === sessionChannelId)
          : false;
        let effectiveChannelId: string | null = sessionChannelId ?? null;
        // connections.length > 0 уже гарантирует connections[0], но strict TS
        // не выводит это автоматически — non-null assertion безопасен.
        if (sessionChannelId && !channelExists && connections.length > 0) {
          const fallback = connections[0]!;
          effectiveChannelId = fallback.id;
          setActiveChannelId(effectiveChannelId);
          publishToast({
            type: "warning",
            message: `Эта база больше недоступна — переключил на «${fallback.name}».`,
          });
        } else if (!sessionChannelId && connections.length > 0) {
          effectiveChannelId = getActiveChannelId() ?? connections[0]!.id;
        }

        setDetail(sessionDetail);
        setLocalActiveChannelId(effectiveChannelId);
        setInitialMessages(messages.map(messageRowToChat));
        setReady(true);
      } catch (err) {
        const reason = err instanceof Error ? err.message : "неизвестная ошибка";
        setLoadError(`Ошибка загрузки сессии: ${reason}`);
        setReady(true);
      }
    }

    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  function handleChannelChange(newId: string) {
    setActiveChannelId(newId);
    setLocalActiveChannelId(newId);
    router.push("/");
  }

  const handleBannerShow = useCallback((chId: string) => {
    // Ищем имя канала из backend (source-of-truth, Plan 5.4 UX-04)
    void fetchConnections().then((connections) => {
      const conn = connections.find((c) => c.id === chId || c.channel === chId);
      setBannerChannelName(conn?.name);
    }).catch(() => {
      // Если backend недоступен — имя канала просто не отображается
    });
    setBannerVisible(true);
  }, []);

  const handleBannerHide = useCallback(() => {
    setBannerVisible(false);
  }, []);

  async function handleRetry() {
    if (bannerRetrying) return;
    setBannerRetrying(true);
    try {
      // Получаем актуальный список подключений из backend (source-of-truth, Plan 5.4 UX-04)
      const connections = await fetchConnections();
      const conn = connections.find(
        (c) => c.id === channelId || c.channel === channelId,
      );
      if (!conn) {
        publishToast({ type: "error", message: "Подключение не найдено" });
        return;
      }
      await pingConnection(conn.id);
      setBannerVisible(false);
    } catch {
      publishToast({ type: "error", message: "База 1С пока не отвечает." });
    } finally {
      setBannerRetrying(false);
    }
  }

  const { messages, isStreaming, error, streamingStage, currentToolName, pendingConfirm, resolveConfirm, pendingClarify, resolveClarify, send, interrupt } = useChatStream({
    sessionId: id,
    channelId,
    initialMessages,
    onBannerShow: handleBannerShow,
    onBannerHide: handleBannerHide,
  });

  // BUG #5: после завершения SSE backend проставляет title сессии
  // (auto-titling из первой реплики) и обновляет счётчик сообщений.
  // Sidebar этого не видел — store.grouped не рефрешился, оставался
  // старый «Новый чат» и старый счётчик до ручного обновления страницы.
  // Слушаем переход isStreaming true→false и тянем свежий список.
  const prevStreamingRef = useRef(false);
  useEffect(() => {
    if (prevStreamingRef.current && !isStreaming) {
      // Был streaming, теперь нет → ответ собран → обновить sidebar.
      void store.refresh();
    }
    prevStreamingRef.current = isStreaming;
  }, [isStreaming, store]);

  // Sprint 03 (handoff 06 · ComposerHub): когда юзер задал первый вопрос
  // в welcome-композере, мы создали сессию + сохранили pending-message
  // в sessionStorage. Здесь подхватываем и автоматически отправляем.
  const pendingHandledRef = useRef(false);
  useEffect(() => {
    if (pendingHandledRef.current) return;
    if (typeof window === "undefined") return;
    const key = `pending-message-${id}`;
    const raw = sessionStorage.getItem(key);
    if (!raw) return;
    sessionStorage.removeItem(key);
    pendingHandledRef.current = true;
    try {
      const parsed = JSON.parse(raw) as {
        message: string;
        attachments: ChatAttachment[] | null;
      };
      if (parsed.message?.trim()) {
        void send(parsed.message, parsed.attachments ?? undefined);
      }
    } catch {
      // Битый JSON — игнорируем, юзер сам нажмёт Enter.
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleCreateNew() {
    const ch = getActiveChannelId() ?? "default";
    try {
      const newSession = await store.createNew(ch);
      router.push(`/sessions/${newSession.id}`);
    } catch (err) {
      // Раньше catch только тихо ререшил sidebar — кнопка кликалась,
      // ничего не происходило, юзер думал «зависло». Теперь явно
      // сообщаем причину (обычно backend недоступен).
      const message = err instanceof Error ? err.message : "Не удалось создать чат";
      publishToast({
        type: "error",
        message: `Не удалось создать чат: ${message}. Проверьте связь с базой 1С.`,
      });
      await store.refresh();
    }
  }

  function handleDelete(sessionId: string) {
    // Sprint 02 A · UndoToast: оптимистично удаляем сессию, через 5с —
    // реальный DELETE. Если удалили текущую сессию — переходим на главную
    // (пользователь увидит UndoToast в шапке главной).
    const allItems = [
      ...(store.grouped?.today ?? []),
      ...(store.grouped?.yesterday ?? []),
      ...(store.grouped?.this_week ?? []),
      ...(store.grouped?.earlier ?? []),
    ];
    const item = allItems.find((s) => s.id === sessionId);
    if (!item) return;

    store.removeOptimistic(sessionId);
    if (sessionId === id) {
      router.push("/");
    }
    publishUndoToast({
      id: `delete-${sessionId}`,
      title: "Чат удалён",
      subtitle: item.title ?? `#${sessionId.slice(0, 4).toUpperCase()}`,
      durationMs: 5000,
      onUndo: () => store.restoreOptimistic(sessionId),
      onCommit: () => {
        void store.commitRemove(sessionId);
      },
    });
  }

  // Global Cmd+K / Ctrl+K hotkey (должен быть до ранних return)
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdPaletteOpen((v) => !v);
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, []);

  if (!ready) {
    // Sprint 02 (handoff M01): Skeleton shimmer для loading чата.
    return (
      <div className="h-screen flex flex-col items-center justify-center gap-3 bg-[var(--bg)] px-6">
        <Skeleton className="h-6 w-56" />
        <Skeleton className="h-4 w-80" />
        <Skeleton className="h-4 w-64" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="h-screen flex flex-col items-center justify-center gap-5 bg-[var(--bg)] px-6">
        <div className="max-w-md text-center space-y-2">
          <h2 className="text-lg font-semibold text-[var(--fg-1)]">
            Не удалось открыть чат
          </h2>
          <p className="text-sm text-[var(--fg-3)] leading-relaxed">
            {loadError}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            className="text-sm text-[var(--accent)] hover:underline"
            onClick={() => router.push("/")}
          >
            На главную
          </button>
          <span className="text-[var(--fg-4)]">·</span>
          <button
            className="text-sm text-[var(--accent)] hover:underline"
            onClick={() => void handleCreateNew()}
          >
            Создать новый чат
          </button>
        </div>
      </div>
    );
  }

  const inputDisabled = isStreaming || bannerVisible;
  const inputDisabledReason = bannerVisible ? "banner" : isStreaming ? "streaming" : null;

  return (
    <>
      <CommandPalette
        open={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        channelId={channelId}
      />
      <ConfirmExecuteDialog
        open={!!pendingConfirm}
        payload={pendingConfirm}
        onResolve={resolveConfirm}
      />
      <ConnectionStatusBanner
        visible={bannerVisible}
        channelName={bannerChannelName}
        onRetry={handleRetry}
        retrying={bannerRetrying}
      />
      <AppShell
        grouped={store.grouped}
        activeId={id}
        onCreateNew={handleCreateNew}
        onDeleteSession={handleDelete}
        headerProps={{
          activeChannelId: activeChannelId ?? detail?.channel_id ?? null,
          onChannelChange: handleChannelChange,
        }}
        bottom={
          <ChatInput
            onSubmit={send}
            disabled={inputDisabled}
            disabledReason={inputDisabledReason}
            channelId={channelId}
            isStreaming={isStreaming}
            onInterrupt={interrupt}
            hasEnvApiKey={hasEnvApiKey}
          />
        }
      >
        <div className="relative h-full">
          <ExportSessionButton
            detail={detail}
            messages={messages}
            className="absolute top-3 right-4 z-10 shadow-sm"
          />
          <Thread
            messages={messages}
            streamingStage={streamingStage}
            currentToolName={currentToolName}
            sessionId={id}
          />
          {pendingClarify && (
            <div className="px-4 max-w-3xl mx-auto">
              <ClarifyDialog payload={pendingClarify} onResolve={resolveClarify} />
            </div>
          )}
          {error && (
            <div className="px-4 pb-2 text-xs text-[var(--error)]">{error}</div>
          )}
        </div>
      </AppShell>
    </>
  );
}
