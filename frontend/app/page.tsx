"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/shell/AppShell";
import { Thread } from "@/components/chat/Thread";
import { ChatInput } from "@/components/chat/Input";
import { Button } from "@/components/ui/button";
import { fetchHealth } from "@/lib/api";
import { getMCPConnections, getLLMConfig } from "@/lib/storage";
import type { ChatMessage, HealthResponse } from "@/lib/types";

const DUMMY_MESSAGES: ChatMessage[] = [
  {
    id: "welcome-1",
    role: "assistant",
    content:
      "Готов отвечать на вопросы про вашу базу 1С. Выберите подключение или настройте новое.",
    created_at: new Date().toISOString(),
  },
];

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
  const [ready, setReady] = useState(false);
  const [hasConfig, setHasConfig] = useState(false);

  useEffect(() => {
    const conns = getMCPConnections();
    const llm = getLLMConfig();
    setHasConfig(conns.length > 0 && !!llm);
    setReady(true);
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

  // Основной layout — AppShell с dummy thread
  return (
    <>
      <AppShell bottom={<ChatInput />}>
        <Thread messages={DUMMY_MESSAGES} />
      </AppShell>
      <BackendIndicator />
    </>
  );
}
