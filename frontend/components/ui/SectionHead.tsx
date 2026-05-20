import { cn } from "@/lib/utils";

export interface SectionHeadProps {
  /** Двузначный номер. Если не задан — не рендерится. */
  num?: string | number;
  title: string;
  /** Метка в правом углу (uppercase, dim). */
  tag?: string;
  className?: string;
}

/**
 * Section header в стиле Stencil лого-листа:
 *
 *   01 · TITLE  ──────────  TAG
 *
 * Где:
 *   - 01 — двузначный номер JetBrains Mono, ls .2em
 *   - TITLE — IBM Plex Mono 600 uppercase ls .08em
 *   - ─── — тонкая линия, заполняющая остаток
 *   - TAG — опциональный label справа, JetBrains Mono, dim
 *
 * Использовать для крупных смысловых блоков на длинных страницах (Guide, Settings).
 */
export function SectionHead({ num, title, tag, className }: SectionHeadProps) {
  return (
    <div className={cn("flex items-baseline gap-[18px]", className)}>
      {num !== undefined && (
        <span
          className="font-mono text-[11px] tracking-[0.2em] text-[var(--fg-3)] flex-none tabular-nums"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          {typeof num === "number" ? String(num).padStart(2, "0") : num}
        </span>
      )}
      <span
        className="font-mono font-semibold text-[14px] tracking-[0.08em] uppercase text-[var(--fg-1)]"
        style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
      >
        {title}
      </span>
      <span
        className="flex-1 h-px"
        style={{ background: "var(--bd-1)" }}
        aria-hidden="true"
      />
      {tag && (
        <span
          className="text-[10.5px] tracking-[0.18em] uppercase text-[var(--fg-3)] flex-none"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          {tag}
        </span>
      )}
    </div>
  );
}
