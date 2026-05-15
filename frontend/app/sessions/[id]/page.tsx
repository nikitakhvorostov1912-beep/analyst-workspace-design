"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { Thread } from "@/components/chat/Thread";
import { ChatInput } from "@/components/chat/Input";
import { CommandPalette } from "@/components/chat/CommandPalette";
import { ConfirmExecuteDialog } from "@/components/chat/ConfirmExecuteDialog";
import { ConnectionStatusBanner } from "@/components/chat/ConnectionStatusBanner";
import { useChatStream } from "@/components/chat/useChatStream";
import { useSessionsStore } from "@/lib/sessions-store";
import { fetchSessionDetail, fetchSessionMessages, fetchConnections, pingConnection } from "@/lib/api";
import { getActiveChannelId, setActiveChannelId } from "@/lib/storage";
import { publishToast } from "@/lib/toast";
import type { ChatMessage, SessionDetail } from "@/lib/types";

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

  // Banner state — STATE-02
  const [bannerVisible, setBannerVisible] = useState(false);
  const [bannerChannelName, setBannerChannelName] = useState<string | undefined>(undefined);
  const [bannerRetrying, setBannerRetrying] = useState(false);

  const store = useSessionsStore();

  // Активный channelId — из сессии или из localStorage
  const channelId = detail?.channel_id ?? getActiveChannelId() ?? "default";

  useEffect(() => {
    setLocalActiveChannelId(getActiveChannelId());

    async function load() {
      try {
        const [sessionDetail, messages] = await Promise.all([
          fetchSessionDetail(id),
          fetchSessionMessages(id),
          store.refresh(),
        ]);

        if (sessionDetail === null) {
          router.replace("/");
          return;
        }

        setDetail(sessionDetail);
        setLocalActiveChannelId(sessionDetail.channel_id ?? getActiveChannelId());
        setInitialMessages(messages.map(messageRowToChat));
        setReady(true);
      } catch {
        setLoadError("Ошибка загрузки сессии");
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
      publishToast({ type: "error", message: "База всё ещё недоступна" });
    } finally {
      setBannerRetrying(false);
    }
  }

  const { messages, isStreaming, error, streamingStage, currentToolName, pendingConfirm, resolveConfirm, send } = useChatStream({
    sessionId: id,
    channelId,
    initialMessages,
    onBannerShow: handleBannerShow,
    onBannerHide: handleBannerHide,
  });

  async function handleCreateNew() {
    const ch = getActiveChannelId() ?? "default";
    try {
      const newSession = await store.createNew(ch);
      router.push(`/sessions/${newSession.id}`);
    } catch {
      await store.refresh();
    }
  }

  async function handleDelete(sessionId: string) {
    await store.remove(sessionId);
    if (sessionId === id) {
      router.push("/");
    }
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
    return (
      <div className="h-screen flex items-center justify-center bg-[var(--bg)]">
        <div className="text-sm text-[var(--fg-muted)]">Загрузка...</div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="h-screen flex flex-col items-center justify-center gap-4 bg-[var(--bg)]">
        <p className="text-red-400 text-sm">{loadError}</p>
        <button
          className="text-sm text-[var(--accent)] underline"
          onClick={() => router.push("/")}
        >
          На главную
        </button>
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
          />
        }
      >
        <Thread
          messages={messages}
          streamingStage={streamingStage}
          currentToolName={currentToolName}
          sessionId={id}
        />
        {error && (
          <div className="px-4 pb-2 text-xs text-red-400">{error}</div>
        )}
      </AppShell>
    </>
  );
}
