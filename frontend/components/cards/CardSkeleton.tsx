"use client";

import { cn } from "@/lib/utils";

interface CardSkeletonProps {
  rows?: number;
  className?: string;
  "aria-label"?: string;
}

const ROW_WIDTHS = ["w-full", "w-3/4", "w-5/6", "w-2/3"] as const;

/**
 * Generic loading placeholder для cards.
 *
 * Phase 11.4 — используется CardRenderer когда payload ещё не пришёл
 * (streaming partial state) и при перезапросе card через action menu.
 *
 * Animate-skeleton-pulse — единая анимация загрузки из design-tokens.css.
 */
export function CardSkeleton({
  rows = 3,
  className,
  "aria-label": ariaLabel = "Загрузка карточки",
}: CardSkeletonProps) {
  return (
    <div
      role="status"
      aria-label={ariaLabel}
      aria-busy="true"
      data-testid="card-skeleton"
      className={cn(
        "bg-[var(--bg-1)] border border-[var(--bd-1)] rounded-md p-3 min-h-32 animate-skeleton-pulse",
        className,
      )}
    >
      {/* Header placeholder: icon + 2-line title */}
      <div className="flex items-center gap-2.5 mb-3">
        <div
          className="h-7 w-7 rounded-md bg-[var(--bg-2)] flex-shrink-0"
          aria-hidden="true"
        />
        <div className="flex-1 space-y-1.5 min-w-0">
          <div className="h-3.5 bg-[var(--bg-2)] rounded w-1/3" />
          <div className="h-2.5 bg-[var(--bg-2)] rounded w-1/4" />
        </div>
      </div>

      {/* Body placeholder: N rows */}
      <div className="space-y-2">
        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={`row-${i}`}
            className={cn(
              "h-3 bg-[var(--bg-2)] rounded",
              ROW_WIDTHS[i % ROW_WIDTHS.length],
            )}
            aria-hidden="true"
          />
        ))}
      </div>
    </div>
  );
}
