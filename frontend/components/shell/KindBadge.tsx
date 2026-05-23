"use client";

import { StencilChip } from "@/components/ui/StencilChip";
import type { MCPKind } from "@/lib/types";

interface KindBadgeProps {
  kind: MCPKind | undefined;
  /** Сохранено ради backward-compat по сигнатуре (раньше было `sm`/`md`). Сейчас не используется. */
  size?: "sm" | "md";
  className?: string;
}

/**
 * Бейдж типа подключения для аналитика:
 *   embedded  → «Локально» (muted) — обработка на этом компьютере
 *   proxy     → «Прокси»   (muted, accent-tooltip) — обработка через сервер
 *
 * Использует StencilChip — единый brand-pattern (mono uppercase, тёмные/sand
 * темы выглядят одинаково ровно). До 2026-05-21 рендерил blue/purple chip,
 * который ломался по контрасту в обеих темах.
 */
export function KindBadge({ kind, className }: KindBadgeProps) {
  if (!kind) return null;

  const label = kind === "embedded" ? "Локально" : "Прокси";
  const tooltip =
    kind === "embedded"
      ? "Встроенный сервер — обработка-обработчик работает на этом компьютере"
      : "Прокси — обработка работает на удалённом сервере, доступ через интернет";

  return (
    <StencilChip
      tone="muted"
      title={tooltip}
      className={className}
      data-testid={`kind-badge-${kind}`}
    >
      {label}
    </StencilChip>
  );
}
