"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/shell/AppShell";
import { Thread } from "@/components/chat/Thread";
import { CommandPalette } from "@/components/chat/CommandPalette";
import { Button } from "@/components/ui/button";
import { fetchHealth } from "@/lib/api";
import { useSessionsStore } from "@/lib/sessions-store";
import { getMCPConnections, getLLMConfig, getActiveChannelId, setActiveChannelId } from "@/lib/storage";
import type { HealthResponse } from "@/lib/types";

type BackendStatus = "loading" | "ok" | "unavailable";

function BackendIndicator() {
  const [status, setStatus] = useState<BackendStatus>("loading");
  const [info, setInfo] = useState<HealthResponse | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        setInfo(data);
        setStatus("ok");
      })
      .catch(() => {
        setStatus("unavailable");
      });
  }, []);

  if (status === "loading") return null;

  return (
    <div className="fixed bottom-3 right-3 z-50">
      <span
        className={`text-xs px-2 py-1 rounded border ${
          status === "ok"
            ? "text-green-400 border-green-800 bg-green-950"
            : "text-red-400 border-red-800 bg-red-950"
        }`}
      >
        {status === "ok"
          ? `Backend: ok ${info?.version ?? ""}`
          : "Backend: недоступен"}
      </span>
    </div>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [hasConfig, setHasConfig] = useState(false);
  const [activeChannelId, setLocalActiveChannelId] = useState<string | null>(null);
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const store = useSessionsStore();

  useEffect(() => {
    const conns = getMCPConnections();
    const llm = getLLMConfig();
    setHasConfig(conns.length > 0 || !!llm);
    setLocalActiveChannelId(getActiveChannelId());
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    void store.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  function handleChannelChange(newId: string) {
    setActiveChannelId(newId);
    setLocalActiveChannelId(newId);
    // Обновляем список сессий для нового канала
    void store.refresh();
  }

  // Global Cmd+K / Ctrl+K hotkey для CommandPalette (должен быть до ранних return)
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

  // Skeleton пока не загрузились данные из localStorage
  if (!ready) {
    return (
      <div className="h-screen flex items-center justify-center bg-[var(--bg)]">
        <div className="text-sm text-[var(--fg-muted)]">Загрузка...</div>
      </div>
    );
  }

  // Empty state — нет конфигурации
  if (!hasConfig) {
    return (
      <>
        <div className="h-screen flex flex-col items-center justify-center gap-6 bg-[var(--bg)]">
          <div className="text-center space-y-3">
            <h1 className="text-2xl font-semibold text-[var(--fg)]">
              Начните работу
            </h1>
            <p className="text-[var(--fg-muted)] max-w-sm text-sm leading-relaxed">
              Подключите вашу базу 1С через MCP и укажите LLM-провайдер
            </p>
          </div>
          <Button asChild>
            <Link href="/settings">Настроить</Link>
          </Button>
        </div>
        <BackendIndicator />
      </>
    );
  }

  async function handleCreateNew() {
    const ch = getActiveChannelId() ?? "default";
    try {
      const newSession = await store.createNew(ch);
      router.push(`/sessions/${newSession.id}`);
    } catch {
      // Если создание не удалось — остаёмся на главной
    }
  }

  async function handleDelete(sessionId: string) {
    await store.remove(sessionId);
  }

  // Основной layout — AppShell с пустым Thread (нет активной сессии)
  // На главной нет активной сессии и чата — ConfirmExecuteDialog не нужен
  return (
    <>
      <CommandPalette
        open={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        channelId={activeChannelId ?? undefined}
      />
      <AppShell
        grouped={store.grouped}
        activeId={null}
        onCreateNew={handleCreateNew}
        onDeleteSession={handleDelete}
        headerProps={{
          activeChannelId,
          onChannelChange: handleChannelChange,
        }}
      >
        <div className="h-full flex flex-col items-center justify-center gap-4 text-center px-6">
          <p className="text-[var(--fg-muted)] text-sm">
            Выберите сессию из истории или начните новый чат
          </p>
          <Button onClick={handleCreateNew} variant="secondary">
            + Новый чат
          </Button>
        </div>
        <Thread messages={[]} />
      </AppShell>
      <BackendIndicator />
    </>
  );
}
