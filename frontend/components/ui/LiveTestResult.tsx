"use client";

import { Check, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface LiveTestResultProps {
  /** Состояние теста — `idle` = ничего не показывать (до первого запуска) */
  state: "idle" | "testing" | "success" | "error";
  /** Время отклика в мс (показывается при success) */
  ms?: number;
  /** Доп. инфо (например, кол-во tools): «24 операций» */
  detail?: string;
  /** Сообщение ошибки (показывается при error) */
  errorMessage?: string;
}

/**
 * Inline-чип результата теста подключения. В отличие от toast — остаётся на экране
 * до следующего теста, показывает время отклика и success/error.
 *
 * Sprint 02 (handoff B · LiveTestResult): inline feedback дублирует toast — toast
 * мигает и исчезает, а пользователю иногда нужно вернуться к результату и увидеть
 * время отклика (особенно когда тестирует несколько подключений подряд).
 */
export function LiveTestResult({
  state,
  ms,
  detail,
  errorMessage,
}: LiveTestResultProps) {
  if (state === "idle") return null;

  const cfg = {
    testing: {
      label: "Проверяю...",
      classes:
        "bg-[var(--info-12)] text-[var(--info)] border-[var(--info-40)]",
      icon: <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />,
    },
    success: {
      label: ms
        ? `Готово · ${ms} мс${detail ? ` · ${detail}` : ""}`
        : "Готово",
      classes:
        "bg-[var(--success-12)] text-[var(--success)] border-[var(--success-40)]",
      icon: <Check className="h-3 w-3" aria-hidden="true" />,
    },
    error: {
      label: errorMessage ?? "Не удалось",
      classes:
        "bg-[var(--error-12)] text-[var(--error)] border-[var(--error-40)]",
      icon: <X className="h-3 w-3" aria-hidden="true" />,
    },
  }[state];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-1 rounded border text-[10px] tracking-[0.14em] uppercase font-medium",
        "animate-fade-up",
        cfg.classes,
      )}
      style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
      role="status"
      aria-live="polite"
    >
      {cfg.icon}
      <span className="truncate max-w-[300px]">{cfg.label}</span>
    </span>
  );
}
