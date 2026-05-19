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
import {
  StatusDot,
  type ConnectionStatus,
} from "@/components/ui/StatusDot";
import { KindBadge } from "@/components/shell/KindBadge";
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

/**
 * Phase 11.4: внутренний ping-статус (4 значения) → атомарный ConnectionStatus (3 значения).
 *   unknown / error → offline
 *   checking → connecting (blink анимация)
 *   ok → online (pulse анимация)
 */
function mapPingToStatus(ping: PingStatus): ConnectionStatus {
  if (ping === "ok") return "online";
  if (ping === "checking") return "connecting";
  return "offline"; // unknown + error
}

/**
 * Извлекает host:port из endpoint URL.
 *   http://localhost:6010/mcp → "localhost:6010"
 *   https://api.example.com/mcp → "api.example.com"
 *   битый URL → пустая строка
 *
 * Аналитик должен всегда видеть к какой базе он подключён —
 * особенно когда баз несколько (Транзит :6010 vs КА Демо :6010 на разных хостах).
 */
function extractHostPort(endpoint: string): string {
  try {
    const u = new URL(endpoint);
    return u.port ? `${u.hostname}:${u.port}` : u.hostname;
  } catch {
    return "";
  }
}

/** Только порт (для компактного отображения в header). */
function extractPort(endpoint: string): string {
  try {
    const u = new URL(endpoint);
    return u.port || (u.protocol === "https:" ? "443" : "80");
  } catch {
    return "";
  }
}

function PingDot({ status }: { status: PingStatus }) {
  return (
    <StatusDot
      status={mapPingToStatus(status)}
      size="sm"
      aria-label={
        status === "ok"
          ? "онлайн"
          : status === "error"
            ? "офлайн"
            : status === "checking"
              ? "проверяется"
              : "статус неизвестен"
      }
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

  // Empty state — крупно, чтобы аналитик сразу заметил «надо настроить»
  if (connections.length === 0) {
    return (
      <div className="flex items-center gap-2.5 h-10 px-3.5 rounded-md border-2 border-dashed border-[var(--warning-20)] bg-[var(--bg-2)] text-[13.5px] text-[var(--fg-2)] select-none min-w-[300px]">
        <PingDot status="unknown" />
        <span className="font-medium">Подключения не настроены</span>
        <Link href="/settings" className="ml-auto text-[var(--accent)] hover:underline text-xs font-medium">
          Настроить
        </Link>
      </div>
    );
  }

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <button
          className="flex items-center gap-2.5 h-10 px-3.5 rounded-md border border-[var(--bd-2)] bg-[var(--bg-2)] text-[13.5px] text-[var(--fg-1)] hover:bg-[var(--bg-hover)] hover:border-[var(--accent-20)] transition-colors min-w-[300px] cursor-pointer shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-20)]"
          aria-label="Выбор канала"
          title={activeConn ? `${activeConn.name} — ${activeConn.endpoint}` : undefined}
          data-testid="channel-selector-button"
        >
          <PingDot status={activeConn?.ping ?? "unknown"} />
          <span className="flex-1 text-left truncate font-semibold">
            {activeConn ? activeConn.name : "Выберите подключение"}
          </span>
          {activeConn && <KindBadge kind={activeConn.kind} size="md" />}
          {activeConn && (
            <span
              className="font-mono text-[12px] text-[var(--fg-2)] flex-none tabular-nums"
              data-testid="channel-selector-port"
            >
              :{extractPort(activeConn.endpoint)}
            </span>
          )}
          <span className="text-[var(--fg-3)] text-xs">▾</span>
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
              <PingDot status={conn.ping} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="truncate font-medium">{conn.name}</span>
                  <KindBadge kind={conn.kind} />
                </div>
                <div
                  className="text-xs text-[var(--fg-muted)] truncate font-mono"
                  title={conn.endpoint}
                >
                  {extractHostPort(conn.endpoint) || conn.endpoint}
                </div>
                {conn.channel && (
                  <div className="text-xs text-[var(--fg-muted)] truncate">
                    Канал: {conn.channel}
                  </div>
                )}
                {conn.ping === "ok" && conn.tool_count !== undefined && (
                  <div className="text-xs text-[var(--fg-muted)]">{conn.tool_count} инструментов</div>
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
