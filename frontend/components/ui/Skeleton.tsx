"use client";

import { cn } from "@/lib/utils";

/**
 * Skeleton — placeholder для loading-состояний.
 *
 * Sprint 02 (handoff 2026-05-23, M01 motion): заменяет голый текст
 * «Загрузка...» в 4+ местах (welcome, chat, settings, insights).
 *
 * Стиль определён в `styles/design-tokens.css` как `.skeleton`:
 * gradient 200% × 100% сдвигается за 1.6s linear infinite, тёмная
 * тема — bg-1 → bg-3, светлая — переопределяется через --skeleton-bg-*.
 *
 * `prefers-reduced-motion: reduce` — переключает на тихую pulse.
 *
 * Использование:
 * ```tsx
 * <Skeleton className="h-4 w-32" />
 * <Skeleton className="h-48 w-full" />
 * ```
 */
export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="status"
      aria-label="Загрузка"
      className={cn("skeleton", className)}
      {...props}
    />
  );
}
