"use client";

import { cn } from "@/lib/utils";

interface StencilLockupProps {
  /** Версия приложения (по умолчанию 1.2.1). null/undefined — скрыть. */
  version?: string | null;
  /** Подпись под лого (PRODUCTION BUILD · STABLE). null — скрыть. */
  subtitle?: string | null;
  /** Размер текста АНАЛИТИК в px (по умолчанию 18). */
  fontSize?: number;
  className?: string;
}

/**
 * Stencil inline-lockup из фирменного стиля (2026-05-19).
 *
 * Структура (фиксированная по brand guideline):
 *   [orange bar] АНАЛИТИК [/] 1.2.1
 *   PRODUCTION BUILD · STABLE
 *
 * Слева — оранжевый «маркер данных» (квадратик ½ x-height).
 * АНАЛИТИК — IBM Plex Mono 700, uppercase, letter-spacing +0.02em.
 * Слэш — приглушённый разделитель (alpha 0.22 на тёмном фоне).
 * Версия — IBM Plex Mono 500, приглушённый цвет (alpha 0.55).
 * Подпись — JetBrains Mono 500, маленькая, очень разреженная.
 *
 * Эталонные размеры из лого-листа:
 *   xl 48px (hero) · lg 36px (about) · md 24px (titlebar) · sm 16px (inline) · xs 12px (meta).
 */
export function StencilLockup({
  version = "1.2.2",
  subtitle = "Production build · Stable",
  fontSize = 18,
  className,
}: StencilLockupProps) {
  const barSize = Math.round(fontSize * 0.52);

  return (
    <div className={cn("flex flex-col min-w-0", className)}>
      {/* Главный замок — bar + АНАЛИТИК + / + версия */}
      <div
        className="flex items-center gap-[0.28em] uppercase whitespace-nowrap leading-none"
        style={{
          fontFamily: "var(--font-plex-mono), ui-monospace, monospace",
          fontWeight: 700,
          fontSize: `${fontSize}px`,
          letterSpacing: "0.02em",
          color: "var(--fg-1)",
        }}
      >
        {/* Оранжевый маркер — signal #FF6A3D */}
        <span
          aria-hidden
          className="inline-block flex-none rounded-[2px]"
          style={{
            width: `${barSize}px`,
            height: `${barSize}px`,
            background: "var(--brand-signal, #ff6a3d)",
            marginRight: "0.05em",
          }}
        />
        <span>АНАЛИТИК</span>
        {version && (
          <>
            <span
              aria-hidden
              style={{
                color: "var(--lockup-slash)",
                fontWeight: 600,
                margin: "0 0.05em",
              }}
            >
              /
            </span>
            <span
              style={{
                color: "var(--lockup-version)",
                fontWeight: 500,
                letterSpacing: "0.02em",
              }}
            >
              {version}
            </span>
          </>
        )}
      </div>

      {/* Подпись — JetBrains Mono, разреженный uppercase */}
      {subtitle && (
        <div
          className="mt-1 truncate"
          style={{
            fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
            fontWeight: 500,
            fontSize: `${Math.max(9, Math.round(fontSize * 0.42))}px`,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--lockup-subtitle)",
          }}
        >
          {subtitle}
        </div>
      )}
    </div>
  );
}
