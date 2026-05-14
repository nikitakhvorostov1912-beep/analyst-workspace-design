"use client";

import { useEffect, useState } from "react";
import { subscribeToast } from "@/lib/toast";
import type { ToastOptions, ToastType } from "@/lib/toast";

const MAX_TOASTS = 5;
const DEFAULT_DURATION_MS = 8000;

type ToastItem = ToastOptions & {
  id: string;
  remaining?: number; // секунды обратного отсчёта
};

function toastIcon(type: ToastType): string {
  if (type === "error") return "⚠";
  if (type === "warning") return "⚡";
  return "ℹ";
}

function ToastItem({ item, onClose }: { item: ToastItem; onClose: (id: string) => void }) {
  const [remaining, setRemaining] = useState(item.countdownSeconds ?? null);

  // Countdown tick — рекурсивный setTimeout чтобы не создавать бесконечный setInterval
  useEffect(() => {
    if (remaining === null || remaining <= 0) return;
    let cancelled = false;
    function tick() {
      if (cancelled) return;
      setRemaining((prev) => {
        if (prev === null || prev <= 1) return 0;
        return prev - 1;
      });
    }
    const timer = setTimeout(tick, 1000);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [remaining]); // eslint-disable-line react-hooks/exhaustive-deps

  const borderColor =
    item.type === "error"
      ? "border-red-700"
      : item.type === "warning"
        ? "border-yellow-600"
        : "border-[var(--border)]";

  return (
    <div
      className={`flex items-start gap-2 px-4 py-3 rounded-md border ${borderColor} bg-[var(--bg-elevated)] text-sm text-[var(--fg)] shadow-lg min-w-[260px] max-w-[400px]`}
    >
      <span className="flex-none mt-0.5 text-base">{toastIcon(item.type)}</span>
      <div className="flex-1">
        <span>{item.message}</span>
        {remaining !== null && remaining > 0 && (
          <span className="ml-2 text-[var(--fg-muted)] tabular-nums">({remaining}с)</span>
        )}
      </div>
      <button
        onClick={() => onClose(item.id)}
        className="flex-none text-[var(--fg-muted)] hover:text-[var(--fg)] ml-1"
        aria-label="Закрыть"
      >
        ×
      </button>
    </div>
  );
}

/**
 * Toaster — монтируется один раз в layout.tsx.
 * ~100 строк без внешних зависимостей (без sonner).
 */
export function Toaster() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const remove = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  useEffect(() => {
    const unsub = subscribeToast((opts) => {
      const id = crypto.randomUUID();
      const duration =
        opts.duration_ms ??
        (opts.countdownSeconds != null ? opts.countdownSeconds * 1000 : DEFAULT_DURATION_MS);

      setToasts((prev) => {
        const updated = [...prev, { ...opts, id }];
        // FIFO cap — не более MAX_TOASTS
        return updated.slice(-MAX_TOASTS);
      });

      setTimeout(() => remove(id), duration);
    });
    return unsub;
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <ToastItem key={t.id} item={t} onClose={remove} />
      ))}
    </div>
  );
}

/**
 * Re-export useToast-совместимый хелпер (для тестов).
 */
export { subscribeToast as useToastSubscribe };
