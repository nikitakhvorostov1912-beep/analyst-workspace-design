"use client";

import { cn } from "@/lib/utils";
import type { MCPKind } from "@/lib/types";

interface KindBadgeProps {
  kind: MCPKind | undefined;
  size?: "sm" | "md";
  className?: string;
}

/**
 * Бейдж типа подключения для аналитика:
 *   embedded  → «Локально» (синий) — обработка на этом компьютере
 *   proxy     → «Прокси»   (фиолетовый) — обработка на сервере, через интернет
 *
 * Без kind не рендерится (backend старой версии).
 */
export function KindBadge({ kind, size = "sm", className }: KindBadgeProps) {
  if (!kind) return null;

  const label = kind === "embedded" ? "Локально" : "Прокси";
  const tooltip =
    kind === "embedded"
      ? "Встроенный сервер — обработка MCP_Toolkit работает на этом компьютере"
      : "Прокси — обработка работает на удалённом сервере, доступ через интернет";

  const palette =
    kind === "embedded"
      ? "bg-blue-500/10 text-blue-300 border-blue-500/30"
      : "bg-purple-500/10 text-purple-300 border-purple-500/30";

  const sizeClass = size === "sm" ? "text-[10px] px-1.5 py-px" : "text-xs px-2 py-0.5";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded border font-medium leading-none whitespace-nowrap",
        palette,
        sizeClass,
        className,
      )}
      title={tooltip}
      data-testid={`kind-badge-${kind}`}
    >
      {label}
    </span>
  );
}
