"use client";

import type { SparklinePoint } from "@/lib/types";

interface SparklineProps {
  points: SparklinePoint[];
  width?: number;
  height?: number;
  stroke?: string;
}

export function Sparkline({ points, width = 120, height = 32, stroke }: SparklineProps) {
  if (points.length < 2) return null;

  const values = points.map((p) => p.value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal;

  // Нормализуем координаты
  const pad = 2; // отступ в пикселях чтобы линия не обрезалась
  function toX(i: number): number {
    return pad + (i / (points.length - 1)) * (width - pad * 2);
  }
  function toY(v: number): number {
    if (range === 0) return height / 2;
    return pad + ((maxVal - v) / range) * (height - pad * 2);
  }

  const polylinePoints = points.map((p, i) => `${toX(i)},${toY(p.value)}`).join(" ");

  // Fill area — polygon до нижнего края
  const fillPoints = [
    `${toX(0)},${height}`,
    ...points.map((p, i) => `${toX(i)},${toY(p.value)}`),
    `${toX(points.length - 1)},${height}`,
  ].join(" ");

  const minFmt = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(minVal);
  const maxFmt = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(maxVal);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      aria-label={`Спарклайн ${points.length} точек, мин ${minFmt}, макс ${maxFmt}`}
      role="img"
      className="overflow-visible"
    >
      {/* Fill area */}
      <polygon
        points={fillPoints}
        fill="currentColor"
        fillOpacity={0.1}
      />
      {/* Line */}
      <polyline
        points={polylinePoints}
        fill="none"
        stroke={stroke ?? "currentColor"}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
