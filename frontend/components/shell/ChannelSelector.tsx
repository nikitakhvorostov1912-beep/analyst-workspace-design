"use client";

import { useEffect, useRef, useState } from "react";
import { RefreshCw, Settings } from "lucide-react";
import Link from "next/link";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { fetchConnections, pingConnection } from "@/lib/api";
import { getMCPConnections, setActiveChannelId, syncMCPConnections } from "@/lib/storage";
import type { MCPConnection } from "@/lib/types";

type PingStatus = "unknown" | "checking" | "ok" | "error";

type ConnectionWithStatus = MCPConnection & {
  ping: PingStatus;
  tool_count?: number;
};

type Props = {
  activeId: string | null;
  onChange: (newId: string) => void;
};

function StatusDot({ status }: { status: PingStatus }) {
  const colors: Record<PingStatus, string> = {
    unknown: "bg-[var(--fg-muted)]",
    checking: "bg-yellow-400 animate-pulse",
    ok: "bg-green-500",
    error: "bg-red-500",
  };
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full flex-none ${colors[status]}`}
      aria-label={status === "ok" ? "онлайн" : status === "error" ? "офлайн" : "проверяется"}
    />
  );
}

export function ChannelSelector({ activeId, onChange }: Props) {
  const [connections, setConnections] = useState<ConnectionWithStatus[]>([]);
  const [open, setOpen] = useState(false);
  const pingInProgress = useRef(false);

  // Загрузка при монтировании
  useEffect(() => {
    async function load() {
      try {
        const conns = await fetchConnections();
        syncMCPConnections(conns);
        setConnections(conns.map((c) => ({ ...c, ping: "unknown" as PingStatus })));
      } catch {
        // @deprecated legacy cache fallback — если backend недоступен, используем последний known state
        const cached = getMCPConnections();
        setConnections(cached.map((c) => ({ ...c, ping: "unknown" as PingStatus })));
      }
    }
    void load();
  }, []);

  async function pingOne(conn: ConnectionWithStatus): Promise<void> {
    setConnections((prev) =>
      prev.map((c) => (c.id === conn.id ? { ...c, ping: "checking" } : c)),
    );

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3000);

    try {
      const result = await pingConnection(conn.id, controller.signal);
      clearTimeout(timer);
      setConnections((prev) =>
        prev.map((c) =>
          c.id === conn.id
            ? { ...c, ping: "ok", tool_count: result.tool_count }
            : c,
        ),
      );
    } catch {
      clearTimeout(timer);
      setConnections((prev) =>
        prev.map((c) => (c.id === conn.id ? { ...c, ping: "error" } : c)),
      );
    }
  }

  async function pingAll(): Promise<void> {
    if (pingInProgress.current) return;
    pingInProgress.current = true;
    try {
      await Promise.all(connections.map((c) => pingOne(c)));
    } finally {
      pingInProgress.current = false;
    }
  }

  // Запускаем параллельный ping при открытии dropdown
  function handleOpenChange(isOpen: boolean) {
    setOpen(isOpen);
    if (isOpen && connections.length > 0) {
      void pingAll();
    }
  }

  function handleSelect(id: string) {
    setActiveChannelId(id);
    onChange(id);
    setOpen(false);
  }

  const activeConn = connections.find((c) => c.id === activeId);

  // Empty state
  if (connections.length === 0) {
    return (
      <div className="flex items-center gap-2 h-9 px-3 rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] text-sm text-[var(--fg-muted)] select-none min-w-[200px]">
        <StatusDot status="unknown" />
        <span>Подключения не настроены</span>
        <Link href="/settings" className="ml-auto text-[var(--accent)] hover:underline text-xs">
          Настроить
        </Link>
      </div>
    );
  }

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <button
          className="flex items-center gap-2 h-9 px-3 rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] text-sm text-[var(--fg)] hover:bg-[var(--bg-hover)] transition-colors min-w-[200px] cursor-pointer"
          aria-label="Выбор канала"
        >
          <StatusDot status={activeConn?.ping ?? "unknown"} />
          <span className="flex-1 text-left truncate">
            {activeConn ? activeConn.name : "Выберите подключение"}
          </span>
          <span className="text-[var(--fg-muted)] text-xs">▾</span>
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="center" className="min-w-[280px] max-h-[360px] overflow-y-auto">
        <DropdownMenuLabel>Канал</DropdownMenuLabel>
        <DropdownMenuSeparator />

        {connections.map((conn) => (
          <div key={conn.id} className="flex items-center gap-1 pr-1">
            <DropdownMenuItem
              className="flex-1 gap-2 cursor-pointer"
              onSelect={() => handleSelect(conn.id)}
            >
              <StatusDot status={conn.ping} />
              <div className="flex-1 min-w-0">
                <div className="truncate font-medium">{conn.name}</div>
                {conn.channel && (
                  <div className="text-xs text-[var(--fg-muted)] truncate">{conn.channel}</div>
                )}
                {conn.ping === "ok" && conn.tool_count !== undefined && (
                  <div className="text-xs text-[var(--fg-muted)]">{conn.tool_count} tools</div>
                )}
              </div>
              {conn.id === activeId && (
                <span className="text-[var(--accent)] text-xs flex-none">✓</span>
              )}
            </DropdownMenuItem>
            <button
              className="p-1 rounded text-[var(--fg-muted)] hover:text-[var(--fg)] hover:bg-[var(--bg-hover)] transition-colors flex-none"
              onClick={(e) => {
                e.stopPropagation();
                void pingOne(conn);
              }}
              aria-label={`Обновить статус ${conn.name}`}
              title="Обновить статус"
            >
              <RefreshCw size={12} className={conn.ping === "checking" ? "animate-spin" : ""} />
            </button>
          </div>
        ))}

        <DropdownMenuSeparator />

        <div className="flex items-center justify-between px-2 py-1">
          <button
            className="flex items-center gap-1 text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              void pingAll();
            }}
          >
            <RefreshCw size={11} />
            Обновить статус
          </button>
          <Link
            href="/settings"
            className="text-xs text-[var(--accent)] hover:underline"
            onClick={() => setOpen(false)}
          >
            <Settings size={11} className="inline mr-1" />
            Настроить
          </Link>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
