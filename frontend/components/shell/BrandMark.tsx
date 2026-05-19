"use client";

import { cn } from "@/lib/utils";

interface BrandMarkProps {
  /** Размер квадрата в пикселях (по умолчанию 40). */
  size?: number;
  className?: string;
}

/**
 * Stencil brand glyph «Аналитик» (2026-05-19).
 *
 * Конструкция:
 *   - Squircle (rounded rectangle) с радиусом ~18% от размера
 *   - Чёрный фон #15161A (--brand-ink)
 *   - Белая буква «А» по центру, IBM Plex Mono 700, ~47% от размера
 *   - Маленький оранжевый маркер #FF6A3D (--brand-signal) в левом верхнем углу
 *     ~14% от размера, отступ ~13% от края
 *
 * Применение: favicon · app icon · taskbar · header brand.
 * Эталонные размеры из лого-листа: 128 / 64 / 32 / 16 px.
 *
 * Запрещено: gradients, glass, sparkles, decorative effects.
 * Только signal + ink + white — стенциловая дисциплина.
 */
export function BrandMark({ size = 40, className }: BrandMarkProps) {
  // Геометрия из лого-листа (favicon scaling rules)
  const radius = Math.round(size * 0.18);
  const markerSize = Math.max(3, Math.round(size * 0.14));
  const markerOffset = Math.max(2, Math.round(size * 0.135));
  const markerRadius = Math.max(1, Math.round(markerSize * 0.18));
  const fontSize = Math.round(size * 0.5);

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Аналитик"
      className={cn("flex-shrink-0", className)}
    >
      {/* Squircle основа — чёрный ink. Тонкая обводка для отделения на ink-фоне. */}
      <rect
        x="0.5"
        y="0.5"
        width={size - 1}
        height={size - 1}
        rx={radius}
        ry={radius}
        fill="#15161A"
        stroke="rgba(255,255,255,0.08)"
      />

      {/* Буква «А» — IBM Plex Mono 700 uppercase, гарантированно читаемая */}
      <text
        x={size / 2}
        y={size / 2 + fontSize * 0.36}
        textAnchor="middle"
        fill="#ffffff"
        fontFamily="'IBM Plex Mono', ui-monospace, monospace"
        fontSize={fontSize}
        fontWeight="700"
      >
        А
      </text>

      {/* Оранжевый маркер в левом верхнем углу — signal #FF6A3D */}
      <rect
        x={markerOffset}
        y={markerOffset}
        width={markerSize}
        height={markerSize}
        rx={markerRadius}
        ry={markerRadius}
        fill="#FF6A3D"
      />
    </svg>
  );
}
