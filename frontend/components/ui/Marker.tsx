import { cn } from "@/lib/utils";

export interface MarkerProps {
  /** Размер стороны квадрата в пикселях. По умолчанию 10. */
  size?: number;
  /** Цвет заливки. По умолчанию accent (signal #FF6A3D). */
  color?: string;
  className?: string;
}

/**
 * Brand marker — оранжевый квадрат, который якорит wordmark и meta-блоки.
 *
 * Используется:
 *   - Перед «АНАЛИТИК» в лого-замке (StencilLockup делает его сам).
 *   - Перед лейблами секций и meta-eyebrow («METRIC», «TABLE», «LOG»).
 *   - В sidebar перед «Новый чат».
 *
 * Стороны 0.52em высоты текста рядом — это brand-rhythm.
 */
export function Marker({ size = 10, color, className }: MarkerProps) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block flex-none rounded-[2px]", className)}
      style={{
        width: size,
        height: size,
        background: color ?? "var(--accent)",
      }}
    />
  );
}
