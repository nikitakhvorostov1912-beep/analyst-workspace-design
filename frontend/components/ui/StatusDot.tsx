"use client";

import { cn } from "@/lib/utils";

export type ConnectionStatus = "online" | "offline" | "connecting";

interface StatusDotProps {
  status: ConnectionStatus;
  size?: "sm" | "md";
  className?: string;
  "aria-label"?: string;
}

const SIZES: Record<NonNullable<StatusDotProps["size"]>, string> = {
  sm: "h-1.5 w-1.5",
  md: "h-2 w-2",
};

const COLORS: Record<ConnectionStatus, string> = {
  online: "bg-[var(--success)] animate-status-pulse",
  offline: "bg-[var(--error)]",
  connecting: "bg-[var(--warning)] animate-blink",
};

const LABELS: Record<ConnectionStatus, string> = {
  online: "Онлайн",
  offline: "Офлайн",
  connecting: "Подключение",
};

export function StatusDot({
  status,
  size = "md",
  className,
  "aria-label": ariaLabel,
}: StatusDotProps) {
  return (
    <span
      role="status"
      data-status={status}
      data-size={size}
      aria-label={ariaLabel ?? `Статус: ${LABELS[status]}`}
      className={cn(
        "inline-block rounded-full",
        SIZES[size],
        COLORS[status],
        className,
      )}
    />
  );
}
