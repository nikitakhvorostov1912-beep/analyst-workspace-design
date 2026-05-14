"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { Thread } from "@/components/chat/Thread";
import { ChatInput } from "@/components/chat/Input";
import { useChatStream } from "@/components/chat/useChatStream";
import { useSessionsStore } from "@/lib/sessions-store";
import {
  fetchSessionDetail,
  fetchSessionMessages,
} from "@/lib/api";
import { getActiveChannelId } from "@/lib/storage";
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

  const store = useSessionsStore();

  // Активный channelId — из сессии или из localStorage
  const channelId = detail?.channel_id ?? getActiveChannelId() ?? "default";

  useEffect(() => {
    async function load() {
      try {
        // Загружаем данные сессии параллельно
        const [sessionDetail, messages] = await Promise.all([
          fetchSessionDetail(id),
          fetchSessionMessages(id),
          store.refresh(),
        ]);

        if (sessionDetail === null) {
          // 404 — редирект на главную
          router.replace("/");
          return;
        }

        setDetail(sessionDetail);
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

  const { messages, isStreaming, error, send } = useChatStream({
    sessionId: id,
    channelId,
    initialMessages,
  });

  async function handleCreateNew() {
    const ch = getActiveChannelId() ?? "default";
    try {
      const newSession = await store.createNew(ch);
      router.push(`/sessions/${newSession.id}`);
    } catch {
      // Fallback — просто обновляем список
      await store.refresh();
    }
  }

  async function handleDelete(sessionId: string) {
    await store.remove(sessionId);
    // Если удалили текущую — идём на главную
    if (sessionId === id) {
      router.push("/");
    }
  }

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

  return (
    <AppShell
      grouped={store.grouped}
      activeId={id}
      onCreateNew={handleCreateNew}
      onDeleteSession={handleDelete}
      bottom={
        <ChatInput
          onSubmit={send}
          disabled={isStreaming}
        />
      }
    >
      <Thread messages={messages} />
      {error && (
        <div className="px-4 pb-2 text-xs text-red-400">{error}</div>
      )}
    </AppShell>
  );
}
