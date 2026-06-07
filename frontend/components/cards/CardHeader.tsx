"use client";

import type { ComponentType } from "react";
import {
  BookMarked,
  Code2,
  FileClock,
  FileText,
  Link as LinkIcon,
  Lock,
  Network,
  Table,
  TrendingUp,
  Unlock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { CardActionMenu, type CardActionItem } from "./CardActionMenu";

export type CardType = "table" | "object" | "log" | "metric" | "references" | "code" | "graph" | "its_sources";

interface TypeMeta {
  icon: ComponentType<{ className?: string }>;
  label: string;
  accentClass: string;
}

const TYPE_META: Record<CardType, TypeMeta> = {
  table: { icon: Table, label: "Таблица", accentClass: "text-[var(--accent)]" },
  object: { icon: FileText, label: "Объект", accentClass: "text-[var(--accent)]" },
  log: { icon: FileClock, label: "Журнал", accentClass: "text-[var(--warning)]" },
  metric: {
    icon: TrendingUp,
    label: "Метрика",
    accentClass: "text-[var(--success)]",
  },
  references: {
    icon: LinkIcon,
    label: "Ссылки",
    accentClass: "text-[var(--accent)]",
  },
  code: { icon: Code2, label: "Код", accentClass: "text-[var(--accent)]" },
  graph: { icon: Network, label: "Граф", accentClass: "text-[var(--accent)]" },
  its_sources: {
    icon: BookMarked,
    label: "Источники ИТС",
    accentClass: "text-[var(--accent)]",
  },
};

interface CardHeaderProps {
  type: CardType;
  title: string;
  meta?: string;
  toolName?: string;
  anonymizable?: boolean;
  anonOn?: boolean;
  onAnonToggle?: () => void;
  actions?: (CardActionItem | "separator")[];
  /** Чип в строке меты — напр. усечение «500 из 12 480» (§3.7). */
  chip?: React.ReactNode;
  /** Доп. действия в правой части шапки (напр. кнопка «Скачать CSV») — в одну строку. */
  extra?: React.ReactNode;
}

export function CardHeader({
  type,
  title,
  meta,
  toolName,
  anonymizable,
  anonOn,
  onAnonToggle,
  actions = [],
  chip,
  extra,
}: CardHeaderProps) {
  const typeMeta = TYPE_META[type];
  const TypeIcon = typeMeta.icon;

  return (
    <div
      data-card-type={type}
      className="flex items-start gap-2.5 px-3 py-3 border-b border-[var(--bd-1)]"
    >
      <div
        className={cn(
          "h-7 w-7 rounded-md inline-flex items-center justify-center bg-[var(--bg-2)] border border-[var(--bd-2)] flex-shrink-0",
          typeMeta.accentClass,
        )}
        aria-label={typeMeta.label}
      >
        <TypeIcon className="h-3.5 w-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-medium text-[var(--fg-1)] text-[13.5px] leading-tight">
          {title}
        </div>
        <div className="flex items-center gap-2 mt-1 text-xs text-[var(--fg-3)] flex-wrap">
          {toolName && (
            <span className="font-mono px-1.5 py-px bg-[var(--bg-2)] border border-[var(--bd-2)] rounded text-[11px] text-[var(--fg-2)]">
              {toolName}
            </span>
          )}
          {meta && <span>{meta}</span>}
          {chip}
        </div>
      </div>
      <div className="flex items-center gap-1">
        {extra}
        {anonymizable && (
          <button
            type="button"
            onClick={onAnonToggle}
            data-anon={anonOn ? "on" : "off"}
            className={cn(
              "inline-flex items-center gap-1.5 px-2 py-1 rounded text-[11.5px] border transition-colors duration-micro ease-design-ease",
              anonOn
                ? "bg-[var(--warning-12)] text-[var(--warning)] border-[var(--warning-20)]"
                : "text-[var(--fg-3)] border-[var(--bd-2)] hover:border-[var(--bd-3)]",
            )}
            title={anonOn ? "Раскрыть значения" : "Включить маски"}
            aria-pressed={anonOn ? "true" : "false"}
          >
            {anonOn ? <Lock className="h-3 w-3" /> : <Unlock className="h-3 w-3" />}
            <span>{anonOn ? "Маскировано" : "Раскрыто"}</span>
          </button>
        )}
        {actions.length > 0 && <CardActionMenu items={actions} />}
      </div>
    </div>
  );
}
