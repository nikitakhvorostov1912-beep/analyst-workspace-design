import { cn } from "@/lib/utils";

export type ChipTone =
  | "muted"
  | "signal"
  | "success"
  | "warn"
  | "error"
  | "solid";

export interface StencilChipProps {
  tone?: ChipTone;
  /** Использовать ли моно-шрифт (JetBrains Mono). По умолчанию true — это brand-pattern. */
  mono?: boolean;
  /** Кликабельный chip (стилизуется как кнопка). */
  asButton?: boolean;
  onClick?: () => void;
  title?: string;
  className?: string;
  /** data-testid для smoke-тестов. */
  "data-testid"?: string;
  /** aria-pressed для chip-кнопок с состоянием (toggle). */
  "aria-pressed"?: boolean;
  /** aria-label если содержимое не самодостаточно. */
  "aria-label"?: string;
  children: React.ReactNode;
}

/**
 * Stencil-pill — фирменная капсула.
 *
 * Brand pattern из лого-листа: pill с 1px border, padding 4×9, font-size 10,
 * letter-spacing .16em, uppercase. 6 тонов покрывают весь спектр:
 *   - muted    — нейтральная meta-метка (по умолчанию)
 *   - signal   — фирменный оранжевый (для активных триггеров типа маскировки)
 *   - success  — мятный, для «онлайн / ОК / live» статусов
 *   - warn     — охра, для предупреждений
 *   - error    — красный, для ошибок
 *   - solid    — заливка signal-цветом (CTA, primary action chip)
 *
 * НЕ использовать обычные Button или Badge для этих случаев — у нас системный
 * паттерн, должен быть консистентен по приложению.
 */
export function StencilChip({
  tone = "muted",
  mono = true,
  asButton = false,
  onClick,
  title,
  className,
  children,
  ...rest
}: StencilChipProps) {
  const base = cn(
    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border",
    "text-[10px] leading-[1.2] uppercase tracking-[0.16em] whitespace-nowrap",
    mono ? "font-mono" : "font-sans",
    asButton && "cursor-pointer transition-colors hover:brightness-110",
    TONE_CLASSES[tone],
    className,
  );

  if (asButton) {
    return (
      <button
        type="button"
        onClick={onClick}
        title={title}
        className={base}
        data-testid={rest["data-testid"]}
        aria-pressed={rest["aria-pressed"]}
        aria-label={rest["aria-label"]}
      >
        {children}
      </button>
    );
  }
  return (
    <span
      className={base}
      title={title}
      data-testid={rest["data-testid"]}
      aria-label={rest["aria-label"]}
    >
      {children}
    </span>
  );
}

const TONE_CLASSES: Record<ChipTone, string> = {
  muted:
    "bg-[var(--bg-2)] border-[var(--bd-2)] text-[var(--fg-3)]",
  signal:
    "bg-[var(--accent-12)] border-[var(--accent-32)] text-[var(--accent)]",
  success:
    "bg-[var(--success-12)] border-[var(--success-40)] text-[var(--success)]",
  warn:
    "bg-[var(--warning-12)] border-[var(--warning-40)] text-[var(--warning)]",
  error:
    "bg-[var(--error-12)] border-[var(--error-40)] text-[var(--error)]",
  solid:
    "bg-[var(--accent)] border-[var(--accent)] text-[var(--brand-ink,#15161a)]",
};
