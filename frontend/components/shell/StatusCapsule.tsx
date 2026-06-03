"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import {
  Activity,
  RefreshCw,
  ChevronDown,
  Database,
  Cpu,
  ShieldCheck,
} from "lucide-react";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { StatusDot, type ConnectionStatus } from "@/components/ui/StatusDot";
import { fetchConnections, fetchLLMConfig, pingConnection } from "@/lib/api";
import { getActiveChannelId } from "@/lib/storage";
import { resolveProviderAndModel } from "@/lib/llm-providers";
import type { MCPConnection } from "@/lib/types";

type Ping = "checking" | "ok" | "error" | "unknown";

function pingToStatus(p: Ping): ConnectionStatus {
  if (p === "ok") return "online";
  if (p === "checking") return "connecting";
  return "offline";
}

function hostPort(endpoint: string): string {
  try {
    const u = new URL(endpoint);
    return u.port ? `${u.hostname}:${u.port}` : u.hostname;
  } catch {
    return endpoint;
  }
}

/**
 * StatusCapsule (shell v3 §2) — единый статус системы в Зоне 3 хедера.
 *
 * Капсула: агрегатная точка (худшая подсистема) + модель + латентность.
 * Поповер: База 1С (host + ping) · Модель · Анонимизация — в одном месте.
 * Поглощает ModelBadge + AnonymizationStatus + KnowledgeBadge из хедера.
 *
 * Без нового polling: connections/модель грузим один раз + слушаем события
 * connections-updated / llm-config-updated; ping — на mount, открытие
 * поповера, возврат фокуса.
 */
export function StatusCapsule({
  activeChannelId,
}: {
  activeChannelId: string | null;
}) {
  const [conns, setConns] = useState<MCPConnection[]>([]);
  const [ping, setPing] = useState<Ping>("unknown");
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const channelId = activeChannelId ?? getActiveChannelId();
  const active = useMemo(
    () => conns.find((c) => c.id === channelId) ?? null,
    [conns, channelId],
  );

  // Загрузка connections + модели. БЕЗ нового polling — слушаем существующие
  // события и пингуем при открытии поповера / возврате фокуса.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [cs, llm] = await Promise.all([
          fetchConnections(),
          fetchLLMConfig(),
        ]);
        if (cancelled) return;
        setConns(cs);
        if (llm?.model) {
          const matched = resolveProviderAndModel(llm.model);
          setModel(matched?.model.label ?? llm.model);
        }
      } catch {
        /* backend лежит — капсула покажет offline через ping */
      }
    }
    void load();

    const onConns = () => void load();
    const onModel = () => void load();
    window.addEventListener("connections-updated", onConns);
    window.addEventListener("llm-config-updated", onModel);
    return () => {
      cancelled = true;
      window.removeEventListener("connections-updated", onConns);
      window.removeEventListener("llm-config-updated", onModel);
    };
  }, []);

  async function doPing() {
    if (!channelId) return;
    setPing("checking");
    const t0 = performance.now();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3000);
    try {
      await pingConnection(channelId, controller.signal);
      clearTimeout(timer);
      setPing("ok");
      setLatencyMs(Math.round(performance.now() - t0));
    } catch {
      clearTimeout(timer);
      setPing("error");
      setLatencyMs(null);
    }
  }

  // Пинг при первом mount и при возврате фокуса (если не ok).
  useEffect(() => {
    void doPing();
    const onFocus = () => {
      if (ping !== "ok") void doPing();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channelId]);

  const dbOk = ping === "ok";
  const overall: ConnectionStatus =
    ping === "error" ? "offline" : ping === "checking" ? "connecting" : "online";

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) void doPing();
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Состояние системы"
          data-testid="status-capsule"
          className="inline-flex items-center gap-2 h-[34px] px-2.5 rounded-md border bg-transparent hover:bg-[var(--bg-2)] border-[var(--bd-2)] hover:border-[var(--bd-3)] transition-colors flex-none data-[state=open]:bg-[var(--bg-2)]"
        >
          <StatusDot status={overall} size="sm" aria-label="статус системы" />
          <span
            className="text-[10.5px] tracking-[0.08em] text-[var(--fg-2)] max-w-[110px] truncate"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            {model ?? "—"}
          </span>
          {latencyMs != null && (
            <>
              <span aria-hidden className="h-3 w-px bg-[var(--bd-2)]" />
              <span
                className="text-[10.5px] text-[var(--fg-3)] tabular-nums"
                style={{
                  fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
                }}
              >
                {latencyMs} мс
              </span>
            </>
          )}
          <ChevronDown className="h-3.5 w-3.5 text-[var(--fg-3)]" />
        </button>
      </PopoverTrigger>

      <PopoverContent align="end" sideOffset={8} className="w-[320px] p-0">
        {/* Заголовок-агрегат */}
        <div className="flex items-center gap-2 px-3.5 py-3 border-b border-[var(--bd-1)]">
          <StatusDot status={overall} size="md" />
          <span
            className="text-[13px] font-semibold text-[var(--fg-1)]"
            style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
          >
            {overall === "online"
              ? "Система в порядке"
              : overall === "connecting"
                ? "Проверка…"
                : "Есть проблемы"}
          </span>
        </div>

        {/* База 1С */}
        <Row
          icon={<Database className="h-3.5 w-3.5" />}
          label="MCP · база 1С"
          value={active ? `${active.name} · ${dbOk ? "LIVE" : "офлайн"}` : "—"}
          sub={
            active
              ? `${hostPort(active.endpoint)}${latencyMs != null ? ` · ${latencyMs} мс` : ""}`
              : undefined
          }
          status={pingToStatus(ping)}
        />

        {/* Модель */}
        <Row
          icon={<Cpu className="h-3.5 w-3.5" />}
          label="Модель"
          value={model ?? "не задана"}
          status="online"
        />

        {/* Анонимизация (read-only, источник — 1С) */}
        <Row
          icon={<ShieldCheck className="h-3.5 w-3.5" />}
          label="Анонимизация"
          value={active?.anon_enabled ? "Включена" : "Выключена"}
          sub={
            active?.anon_enabled
              ? "контрагенты скрыты токенами"
              : "имена приходят как есть"
          }
          status={active?.anon_enabled ? "online" : "offline"}
          data-testid="anon-status"
        />

        {/* Футер */}
        <div className="flex items-center gap-2 px-3 py-2">
          <Link
            href="/status"
            onClick={() => setOpen(false)}
            className="inline-flex items-center gap-1.5 text-[11px] text-[var(--fg-2)] hover:text-[var(--fg-1)]"
          >
            <Activity className="h-3.5 w-3.5" /> Диагностика
          </Link>
          <span className="flex-1" />
          <button
            type="button"
            onClick={() => void doPing()}
            className="inline-flex items-center gap-1.5 text-[11px] text-[var(--fg-3)] hover:text-[var(--fg-1)]"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${ping === "checking" ? "animate-spin" : ""}`}
            />{" "}
            Проверить
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function Row({
  icon,
  label,
  value,
  sub,
  status,
  ...rest
}: {
  icon: ReactNode;
  label: string;
  value: string;
  sub?: string;
  status: ConnectionStatus;
  "data-testid"?: string;
}) {
  return (
    <div
      className="flex items-center gap-3 px-3.5 py-2.5 border-b border-[var(--bd-1)]"
      data-testid={rest["data-testid"]}
    >
      <span className="text-[var(--fg-3)] flex-none">{icon}</span>
      <div className="flex-1 min-w-0">
        <div
          className="text-[9.5px] tracking-[0.16em] uppercase text-[var(--fg-4)]"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          {label}
        </div>
        <div
          className="text-[12.5px] text-[var(--fg-1)] truncate"
          style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
        >
          {value}
        </div>
        {sub && <div className="text-[10px] text-[var(--fg-4)] truncate">{sub}</div>}
      </div>
      <StatusDot status={status} size="sm" />
    </div>
  );
}
