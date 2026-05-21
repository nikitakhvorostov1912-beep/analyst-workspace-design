"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface StepIndicatorProps {
  current: number;
  total: number;
  labels?: string[];
}

export function StepIndicator({ current, total, labels }: StepIndicatorProps) {
  return (
    <div className="flex flex-col items-center gap-3" data-testid="step-indicator">
      <div className="flex items-center w-full max-w-md">
        {Array.from({ length: total }, (_, i) => {
          const step = i + 1;
          const isDone = step < current;
          const isActive = step === current;

          return (
            <div key={step} className="flex items-center flex-1">
              <div
                data-step={step}
                data-state={isActive ? "active" : isDone ? "done" : "future"}
                className={cn(
                  "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-medium transition-colors duration-normal ease-design-ease",
                  // accent = signal #FF6A3D (оранжевый) — на нём белый текст имеет
                  // контраст ~3.0 (близко к WCAG-провалу). Тёмный --brand-ink
                  // даёт ~6.5 и читается одинаково в обеих темах.
                  isActive &&
                    "bg-[var(--accent)] text-[var(--brand-ink,#15161a)] shadow-[0_0_0_3px_var(--accent-20)]",
                  isDone && "bg-[var(--accent-20)] text-[var(--accent)]",
                  !isActive &&
                    !isDone &&
                    "bg-[var(--bd-2)] text-[var(--fg-3)]",
                )}
                aria-label={
                  labels?.[i]
                    ? `Шаг ${step}: ${labels[i]}`
                    : `Шаг ${step} из ${total}`
                }
              >
                {isDone ? <Check className="h-4 w-4" /> : step}
              </div>
              {step < total && (
                <div
                  className={cn(
                    "h-px flex-1 mx-1 transition-colors duration-normal ease-design-ease",
                    isDone ? "bg-[var(--accent-20)]" : "bg-[var(--bd-2)]",
                  )}
                />
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-[var(--fg-3)]">
        Шаг {current} из {total}
        {labels?.[current - 1] && (
          <span className="text-[var(--fg-2)]">: {labels[current - 1]}</span>
        )}
      </p>
    </div>
  );
}
