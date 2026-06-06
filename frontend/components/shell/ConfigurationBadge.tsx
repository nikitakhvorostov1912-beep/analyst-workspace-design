"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Layers, RotateCw, Sparkles } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  fetchTypicalConfigurations,
  type TypicalConfigurationDTO,
} from "@/lib/api";
import {
  getActiveTypicalChannelId,
  setActiveTypicalChannelId,
} from "@/lib/storage";
import {
  CONFIG_TO_TYPICAL_KIND,
  TYPICAL_KIND_LABELS,
  resolveTypicalChannelId,
} from "@/lib/config-typical-link";
import { cn } from "@/lib/utils";
import type { MCPConnection } from "@/lib/types";

/**
 * ConfigurationBadge — единственный контрол конфигурации базы в шапке.
 *
 *  • показывает детектнутую конфу клиентской базы + ручной override;
 *  • авто-привязывает активную ЭТАЛОННУЮ типовую к конфе текущей базы
 *    (КА база → типовая КА), заменяя прежнюю отдельную плашку TypicalSelector;
 *  • в дропдауне — секция «Сравнить с типовой» для миграционного кейса
 *    (база КА, а смотрим устройство ERP) — типовая ≠ конфа базы.
 */

const OVERRIDE_OPTIONS = [
  "УТ 11.5",
  "ERP 2.5",
  "КА 2.5",
  "БП 3.0",
  "ЗУП 3.1",
  "УСО 2.5",
  "Самописная",
] as const;

type ConfigState =
  | "auto"
  | "confirmed"
  | "manual"
  | "ambiguous"
  | "failed"
  | "custom"
  | "none";

function deriveState(conn: MCPConnection): ConfigState {
  const s = conn.configuration_source as ConfigState | null | undefined;
  if (s) return s;
  return conn.configuration ? "confirmed" : "none";
}

const SOURCE_LABEL: Partial<Record<ConfigState, string>> = {
  auto: "авто",
  confirmed: "подтверждено",
  manual: "вручную",
  ambiguous: "уточните",
  custom: "самописная",
};

type Props = {
  connection: MCPConnection;
  onOverride: (configuration: string) => void;
  onRetry?: () => void;
};

export function ConfigurationBadge({ connection, onOverride, onRetry }: Props) {
  const [open, setOpen] = useState(false);
  const [typicals, setTypicals] = useState<TypicalConfigurationDTO[]>([]);
  const [activeTypicalId, setActiveTypicalId] = useState<string | null>(null);

  // Грузим список типовых один раз + читаем текущую активную из localStorage.
  // Типовые опциональны — ошибку загрузки гасим тихо (бейдж конфы работает и без них).
  useEffect(() => {
    setActiveTypicalId(getActiveTypicalChannelId());
    let cancelled = false;
    fetchTypicalConfigurations()
      .then((r) => {
        if (!cancelled) setTypicals(r.configurations);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Авто-привязка: эталонная типовая следует за конфой текущей базы.
  // Эффект срабатывает только при смене базы/конфы/набора типовых — ручной
  // выбор «сравнить с другой типовой» он не перезатирает (deps не меняются).
  useEffect(() => {
    const match = resolveTypicalChannelId(connection.configuration, typicals);
    if (match && match !== getActiveTypicalChannelId()) {
      setActiveTypicalChannelId(match);
      setActiveTypicalId(match);
    }
  }, [connection.id, connection.configuration, typicals]);

  const state = deriveState(connection);
  const label =
    state === "failed" ? "детекция…" : (connection.configuration ?? "—");

  const toneClass =
    state === "failed"
      ? "border-[var(--error-40)] bg-[var(--error-12)] text-[var(--error)]"
      : state === "ambiguous"
        ? "border-[var(--warning-40)] bg-[var(--warning-12)] text-[var(--warning)]"
        : connection.configuration && state !== "none"
          ? "border-[var(--accent-32)] bg-[var(--accent-08)] text-[var(--fg-1)]"
          : "border-[var(--bd-2)] bg-[var(--bg-2)] text-[var(--fg-2)]";

  const wantKind = connection.configuration
    ? CONFIG_TO_TYPICAL_KIND[connection.configuration]
    : undefined;
  const typicalLoaded = wantKind
    ? typicals.some((t) => t.config_kind === wantKind)
    : false;

  function pickTypical(id: string | null) {
    setActiveTypicalChannelId(id);
    setActiveTypicalId(id);
    setOpen(false);
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          data-testid="config-badge"
          data-state={state}
          className={cn(
            "flex items-center gap-2 h-9 px-3 rounded-md border transition-colors cursor-pointer",
            "focus:outline-none focus:ring-2 focus:ring-[var(--accent-20)] flex-none",
            toneClass,
          )}
          title="Конфигурация базы — нажми, чтобы изменить вручную или сравнить с типовой"
        >
          {state === "failed" ? (
            <RotateCw className="h-3.5 w-3.5 flex-none" />
          ) : (
            <Layers className="h-3.5 w-3.5 flex-none" />
          )}
          <span
            className="text-[10px] tracking-[0.16em] uppercase flex-none"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            Конфа
          </span>
          <span className="text-[12.5px] font-semibold truncate max-w-[140px]">
            {label}
          </span>
          {SOURCE_LABEL[state] && state !== "failed" && (
            <span className="text-[10px] text-[var(--fg-3)]">
              ({SOURCE_LABEL[state]})
            </span>
          )}
          <ChevronDown className="h-3.5 w-3.5 text-[var(--fg-3)] flex-none" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="center" className="min-w-[260px]">
        <DropdownMenuLabel>Конфигурация базы</DropdownMenuLabel>
        {state === "failed" && onRetry && (
          <>
            <DropdownMenuItem
              onSelect={() => {
                setOpen(false);
                onRetry();
              }}
            >
              <RotateCw className="h-3.5 w-3.5 mr-2" /> Повторить детекцию
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        <div className="px-3 pb-1.5 text-[11px] text-[var(--fg-3)] leading-snug">
          Указать вручную, если детекция ошиблась:
        </div>
        {OVERRIDE_OPTIONS.map((opt) => (
          <DropdownMenuItem
            key={opt}
            className={cn(
              "cursor-pointer",
              connection.configuration === opt && "bg-[var(--accent-08)]",
            )}
            onSelect={() => {
              setOpen(false);
              onOverride(opt);
            }}
          >
            {opt}
            {connection.configuration === opt && (
              <span className="ml-auto text-[var(--accent)]">✓</span>
            )}
          </DropdownMenuItem>
        ))}

        <DropdownMenuSeparator />
        <div className="px-3 pb-1 pt-0.5 text-[11px] text-[var(--fg-3)] leading-snug">
          Сравнить с типовой (как устроено в эталоне):
        </div>
        {wantKind && !typicalLoaded && (
          <div
            data-testid="typical-not-loaded-hint"
            className="px-3 pb-1.5 text-[10px] text-[var(--warning)] leading-snug"
          >
            Типовая {TYPICAL_KIND_LABELS[wantKind] ?? wantKind} не загружена —
            добавьте её в Настройках.
          </div>
        )}
        <DropdownMenuItem
          data-testid="typical-option-none"
          className={cn(
            "cursor-pointer text-[12px]",
            activeTypicalId === null && "bg-[var(--accent-08)]",
          )}
          onSelect={() => pickTypical(null)}
        >
          <Sparkles className="h-3.5 w-3.5 mr-2 text-[var(--fg-3)]" /> Без типовой
          {activeTypicalId === null && (
            <span className="ml-auto text-[var(--accent)]">✓</span>
          )}
        </DropdownMenuItem>
        {typicals.map((t) => (
          <DropdownMenuItem
            key={t.channel_id}
            data-testid={`typical-option-${t.channel_id}`}
            className={cn(
              "cursor-pointer text-[12px]",
              activeTypicalId === t.channel_id && "bg-[var(--accent-08)]",
            )}
            onSelect={() => pickTypical(t.channel_id)}
          >
            {TYPICAL_KIND_LABELS[t.config_kind] ?? t.config_kind}
            <span className="ml-1.5 text-[10px] text-[var(--fg-3)]">
              {t.config_version}
            </span>
            {activeTypicalId === t.channel_id && (
              <span className="ml-auto text-[var(--accent)]">✓</span>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
