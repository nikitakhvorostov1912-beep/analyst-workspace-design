"use client";

import { ChartCard, ChartCardError, parseChartSpec } from "@/components/cards/ChartCard";

/**
 * H-06 (Web Vitals): тонкая обёртка над ChartCard, чтобы Markdown.tsx мог
 * подключать её через next/dynamic. ChartCard тянет recharts (~100 KB gzip);
 * вынеся parseChartSpec + рендер сюда, мы убираем recharts из initial bundle —
 * он грузится только когда в ответе реально есть ```chart-блок.
 */
export function ChartBlock({ raw }: { raw: string }) {
  const trimmed = raw.replace(/\n$/, "");
  const spec = parseChartSpec(trimmed);
  if (spec) {
    return <ChartCard spec={spec} />;
  }
  return (
    <ChartCardError
      raw={trimmed}
      error="невалидный JSON или неподдерживаемый type (нужен bar / line / pie)"
    />
  );
}
