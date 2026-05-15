"use client";

import { useState } from "react";
import { ArrowUp, ArrowDown, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sparkline } from "./Sparkline";
import { publishToast } from "@/lib/toast";
import type { MetricCardPayload } from "@/lib/types";

interface MetricCardProps {
  payload: MetricCardPayload;
  onDeanonymize?: (tokens: string[]) => Promise<Record<string, string>>;
}

export function MetricCard({ payload, onDeanonymize }: MetricCardProps) {
  const { value, label, unit, sparkline, delta } = payload;
  const [revealing, setRevealing] = useState(false);

  const formattedValue = new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 2,
  }).format(value);

  async function handleReveal() {
    if (!onDeanonymize || revealing) return;
    setRevealing(true);
    try {
      await onDeanonymize([]);
    } catch {
      publishToast({ type: "error", message: "Не удалось раскрыть значения" });
    } finally {
      setRevealing(false);
    }
  }

  const hasDelta = delta != null;
  const deltaUp = hasDelta && delta.direction === "up";
  const deltaDown = hasDelta && delta.direction === "down";

  const deltaPercent =
    hasDelta && delta.percent_value != null
      ? `${delta.percent_value >= 0 ? "+" : ""}${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(delta.percent_value)}%`
      : null;

  const deltaAbs = hasDelta
    ? `${delta.value >= 0 ? "+" : ""}${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(delta.value)}`
    : null;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-4 inline-block min-w-[160px]">
      <div className="flex items-start justify-between gap-4">
        {/* Основное значение */}
        <div className="flex flex-col gap-0.5">
          <div className="flex items-baseline gap-1">
            <span className="text-4xl font-semibold tabular-nums text-[var(--fg)]">
              {formattedValue}
            </span>
            {unit && (
              <span className="text-lg text-[var(--fg-muted)]">{unit}</span>
            )}
          </div>
          <span className="text-sm text-[var(--fg-muted)]">{label}</span>
        </div>

        {/* Delta */}
        {hasDelta && (
          <div
            className={`flex flex-col items-end gap-0.5 ${deltaUp ? "text-emerald-400" : deltaDown ? "text-rose-400" : "text-[var(--fg-muted)]"}`}
          >
            {deltaUp ? (
              <ArrowUp className="h-4 w-4" />
            ) : deltaDown ? (
              <ArrowDown className="h-4 w-4" />
            ) : null}
            {deltaPercent && (
              <span className="text-xs font-medium tabular-nums">{deltaPercent}</span>
            )}
            {deltaAbs && !deltaPercent && (
              <span className="text-xs font-medium tabular-nums">{deltaAbs}</span>
            )}
          </div>
        )}
      </div>

      {/* Sparkline */}
      {sparkline && sparkline.length >= 2 && (
        <div className="mt-3 text-[var(--accent)]">
          <Sparkline points={sparkline} width={200} height={40} />
        </div>
      )}

      {/* Anon footer */}
      {onDeanonymize && (
        <div className="mt-2 pt-2 border-t border-[var(--border)]">
          <Button
            size="sm"
            variant="ghost"
            className="text-xs h-7 gap-1 text-amber-400 hover:text-amber-300"
            disabled={revealing}
            onClick={() => { void handleReveal(); }}
          >
            <Eye className="h-3 w-3" />
            {revealing ? "Загрузка..." : "Раскрыть реальные значения"}
          </Button>
        </div>
      )}
    </div>
  );
}
