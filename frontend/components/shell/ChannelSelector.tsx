"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Database, RefreshCw, Settings } from "lucide-react";
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
 * особенно когда баз несколько на одном порту :6010 но на разных хостах.
 */
function extractHostPort(endpoint: string): string {
  try {
    const u = new URL(endpoint);
    return u.port ? `${u.hostname}:${u.port}` : u.hostname;
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

  // Загрузка при монтировании + автоматический ping, чтобы аналитик при открытии
  // приложения видел зелёный/красный статус сразу. Плюс auto-retry: типичный
  // сценарий — аналитик открыл приложение ДО запуска MCP в 1С, autoping упал.
  // Без retry статус остаётся offline навсегда (до ручного refresh). Теперь:
  //   - re-ping при возврате окна в фокус (typical case: переключился в 1С → запустил
  //     MCP_Toolkit → вернулся в приложение → авто-проверка),
  //   - re-ping каждые 15 сек если есть error-соединения (backstop).
  useEffect(() => {
    async function pingOneConn(connId: string): Promise<boolean> {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 3000);
      try {
        const result = await pingConnection(connId, controller.signal);
        clearTimeout(timer);
        setConnections((prev) =>
          prev.map((c) =>
            c.id === connId ? { ...c, ping: "ok", tool_count: result.tool_count } : c,
          ),
        );
        return true;
      } catch {
        clearTimeout(timer);
        setConnections((prev) =>
          prev.map((c) => (c.id === connId ? { ...c, ping: "error" } : c)),
        );
        return false;
      }
    }

    async function load() {
      let initialConns: MCPConnection[];
      try {
        initialConns = await fetchConnections();
        syncMCPConnections(initialConns);
      } catch {
        initialConns = getMCPConnections();
      }
      const withStatus: ConnectionWithStatus[] = initialConns.map((c) => ({
        ...c,
        ping: "checking" as PingStatus,
      }));
      setConnections(withStatus);
      await Promise.all(withStatus.map((c) => pingOneConn(c.id)));
    }

    void load();

    // Re-ping при возврате окна в фокус — самый частый сценарий: аналитик
    // переключился в 1С чтобы запустить MCP, вернулся → видит обновлённый статус.
    function handleFocus() {
      setConnections((prev) => {
        for (const c of prev) {
          if (c.ping !== "ok") void pingOneConn(c.id);
        }
        return prev;
      });
    }
    window.addEventListener("focus", handleFocus);

    // Backstop: каждые 15 сек проверяем error-соединения. Когда все ok —
    // интервал ничего не делает, нагрузки нет.
    const intervalId = window.setInterval(() => {
      setConnections((prev) => {
        for (const c of prev) {
          if (c.ping === "error") void pingOneConn(c.id);
        }
        return prev;
      });
    }, 15_000);

    return () => {
      window.removeEventListener("focus", handleFocus);
      window.clearInterval(intervalId);
    };
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
      <div className="flex items-center gap-3 h-9 px-3 rounded-md border border-dashed border-[var(--warning-40)] bg-[var(--warning-12)] text-[13px] text-[var(--fg-1)] select-none min-w-[320px]">
        <Database className="h-3.5 w-3.5 text-[var(--warning)] flex-none" />
        <span
          className="text-[10px] tracking-[0.16em] uppercase text-[var(--warning)] flex-none"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          База 1С
        </span>
        <span className="flex-1 font-medium">Подключения не настроены</span>
        <Link
          href="/settings"
          className="text-[10px] tracking-[0.16em] uppercase text-[var(--accent)] hover:underline flex-none"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          Настроить →
        </Link>
      </div>
    );
  }

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <button
          className="flex items-center gap-3 h-9 px-3 rounded-md border border-[var(--bd-2)] bg-[var(--bg-2)] hover:bg-[var(--bg-hover)] hover:border-[var(--bd-3)] transition-colors min-w-[320px] cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent-20)]"
          aria-label="Выбор базы 1С"
          title={activeConn ? `${activeConn.name} — ${activeConn.endpoint}` : undefined}
          data-testid="channel-selector-button"
        >
          {/* Brand-eyebrow: иконка + БАЗА 1С uppercase */}
          <Database className="h-3.5 w-3.5 text-[var(--accent)] flex-none" />
          <span
            className="text-[10px] tracking-[0.16em] uppercase text-[var(--fg-3)] flex-none"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            База 1С
          </span>

          {/* Название канала — IBM Plex Mono 600. Технических подробностей
              (порт, embedded/proxy) тут нет: аналитику важно «база подключена / нет»,
              а не как именно она настроена. Полный адрес показывается в dropdown. */}
          <span
            className="flex-1 text-left truncate text-[12.5px] font-semibold text-[var(--fg-1)]"
            style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace" }}
          >
            {activeConn ? activeConn.name : "Выберите подключение"}
          </span>

          <PingDot status={activeConn?.ping ?? "unknown"} />
          <ChevronDown className="h-3.5 w-3.5 text-[var(--fg-3)] flex-none" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="center" className="min-w-[280px] max-h-[360px] overflow-y-auto">
        <DropdownMenuLabel>Базы 1С</DropdownMenuLabel>
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
                {/* REM-4 (2026-05-24): «Канал: ...» убран из видимого UI —
                    это техническая строка proxy-профиля, аналитику не нужна.
                    Полный endpoint виден в title attribute trigger'а. */}
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
