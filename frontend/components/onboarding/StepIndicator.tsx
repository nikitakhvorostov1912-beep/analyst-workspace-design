"use client";

interface StepIndicatorProps {
  current: 1 | 2 | 3;
  total: 3;
}

export function StepIndicator({ current, total }: StepIndicatorProps) {
  return (
    <div className="flex flex-col items-center gap-3">
      <div className="flex items-center w-full max-w-xs">
        {Array.from({ length: total }, (_, i) => {
          const step = (i + 1) as 1 | 2 | 3;
          const isDone = step < current;
          const isActive = step === current;

          return (
            <div key={step} className="flex items-center flex-1">
              <div
                className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-[var(--accent)] text-white"
                    : isDone
                      ? "bg-[var(--accent)]/30 text-[var(--accent)]"
                      : "bg-[var(--border)] text-[var(--fg-muted)]"
                }`}
              >
                {step}
              </div>
              {step < total && (
                <div
                  className={`h-px flex-1 mx-1 transition-colors ${
                    isDone ? "bg-[var(--accent)]/30" : "bg-[var(--border)]"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-[var(--fg-muted)]">
        Шаг {current} из {total}
      </p>
    </div>
  );
}
