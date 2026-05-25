"use client";

import { StencilChip } from "@/components/ui/StencilChip";
import type { ChannelMode } from "@/lib/capabilities";

interface ModeBadgeProps {
  /** mcp_only | epf | cfe — из MCPConnection.mode (M-K1.6 capability discovery) */
  mode: ChannelMode | undefined | null;
  className?: string;
}

/**
 * Бейдж режима канала для аналитика (M-K1.11):
 *   mcp_only → «MCP»     (muted, синий) — обычный 1С MCP Toolkit
 *   epf      → «EPF»     (info) — внешняя обработка АналитикLite
 *   cfe      → «CFE»     (accent) — расширение АналитикПлюс (premium)
 *
 * Помогает пользователю понять «что у меня подключено» — без deep dive
 * в settings. CFE badge подсвечивает что доступны все 23 capabilities.
 *
 * Использует StencilChip — единый brand-pattern.
 *
 * Скрывается если mode undefined/null (legacy connection без discovery).
 */
export function ModeBadge({ mode, className }: ModeBadgeProps) {
  if (!mode) return null;

  const config = {
    mcp_only: {
      label: "MCP",
      tone: "muted" as const,
      tooltip: "1С MCP Toolkit — базовые tools без расширения",
    },
    epf: {
      label: "EPF",
      tone: "muted" as const,
      tooltip: "АналитикLite — внешняя обработка quick-start",
    },
    cfe: {
      label: "CFE",
      tone: "signal" as const,  // фирменный signal — выделяем premium капсулу
      tooltip:
        "АналитикПлюс — полное расширение, доступны все capabilities (Activity Stream, Posting Trace, BSL Diagnostics)",
    },
  }[mode];

  return (
    <StencilChip
      tone={config.tone}
      title={config.tooltip}
      className={className}
      data-testid={`mode-badge-${mode}`}
    >
      {config.label}
    </StencilChip>
  );
}
