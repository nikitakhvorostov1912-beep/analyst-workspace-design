"use client";

import { cn } from "@/lib/utils";

interface BrandMarkProps {
  /** Размер квадрата в пикселях (по умолчанию 40). */
  size?: number;
  className?: string;
}

/**
 * Логотип «1С Аналитик» — text-glyph «1С» крупно по центру
 * плюс 4-точечная искра в верхнем правом углу как символ AI/анализа.
 *
 * Концепция:
 *   - Узнаваемые «1С» — крупным жирным шрифтом, гарантированно читаются
 *     даже на 32px (не размытые stroke path'ы как было сначала)
 *   - Sparkle — AI-индикатор (как у Claude/Perplexity иконок).
 *     Подсвечен мягким радиальным glow.
 *   - Diagonal gradient на фоне даёт глубину без glass-morphism.
 *   - Inner highlight на верхней кромке — лёгкий «глянец»
 *
 * Запрещено в проекте: purple-cyan gradients, glass morphism, decorative emoji.
 * Используем только accent (--accent = #3b82f6) и его прозрачные вариации.
 */
export function BrandMark({ size = 40, className }: BrandMarkProps) {
  const gradientId = "brandmark-bg";
  const sparkleId = "brandmark-sparkle";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="1С Аналитик"
      className={cn("flex-shrink-0 drop-shadow-md", className)}
    >
      <defs>
        {/* Diagonal gradient — насыщенный сверху-слева, спокойный снизу-справа.
             Только наша синяя палитра, без cyan/purple. */}
        <linearGradient id={gradientId} x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="1" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.65" />
        </linearGradient>
        {/* Радиальная подсветка sparkle — мягкое сияние вокруг искры */}
        <radialGradient id={sparkleId} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Основа: rounded square с градиентом и тонкой обводкой */}
      <rect
        x="0.5"
        y="0.5"
        width="39"
        height="39"
        rx="10"
        ry="10"
        fill={`url(#${gradientId})`}
        stroke="var(--accent)"
        strokeOpacity="0.4"
      />
      {/* Inner highlight — верхняя кромка светлее, имитация глянца */}
      <rect
        x="1.5"
        y="1.5"
        width="37"
        height="14"
        rx="9"
        ry="9"
        fill="#ffffff"
        fillOpacity="0.1"
      />

      {/* === Монограмма «1С» — text-glyph крупно ===
           Используем text вместо path'ов чтобы гарантированно читалось
           даже на мелких размерах. font-weight 700 + stroke даёт жирный bold,
           тень имитирует глубину */}
      <text
        x="20"
        y="28"
        textAnchor="middle"
        fill="#ffffff"
        fontFamily="'IBM Plex Sans', system-ui, sans-serif"
        fontSize="18"
        fontWeight="700"
        letterSpacing="-0.5"
        style={{ textShadow: "0 1px 2px rgba(0,0,0,0.25)" }}
      >
        1С
      </text>

      {/* === Sparkle (искра) — 4-точечная звезда сверху-справа === */}
      {/* Радиальное сияние под звездой */}
      <circle cx="31.5" cy="8.5" r="5" fill={`url(#${sparkleId})`} />
      {/* Сама 4-точечная звезда */}
      <path
        d="M31.5 5 L32.3 8 L35.2 8.5 L32.3 9 L31.5 12 L30.7 9 L27.8 8.5 L30.7 8 Z"
        fill="#ffffff"
      />
    </svg>
  );
}
