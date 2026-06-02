"use client";

import { AlertCircle, AlertTriangle, CheckCircle2, Info, X, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Alert — единая система сообщений (redesign 2.0 §3.1, лечит F-04).
 *
 * До этого в проекте было ПЯТЬ разных поверхностей ошибок (BackendDownBanner,
 * ConnectionStatusBanner, ErrorBanner, inline «⚠ {message}» в AssistantMessage,
 * border-red-800 в settings). Все ошибки/уведомления теперь — через этот примитив.
 * Иконки — lucide (НЕ emoji). Статус передаётся цвет + иконка + текст.
 */

export type AlertTone = "info" | "success" | "warning" | "error";

const TONE_ICON: Record<AlertTone, LucideIcon> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: AlertCircle,
};

interface AlertProps {
  tone: AlertTone;
  title: string;
  description?: React.ReactNode;
  /** Кнопки действий (Повторить / Что это значит?) — слот снизу. */
  actions?: React.ReactNode;
  /** Иконка-переопределение; по умолчанию по тону. */
  icon?: LucideIcon;
  /** Если задан — показывается крестик закрытия. */
  onClose?: () => void;
  className?: string;
  /** data-testid для тестов (сохраняем старые id баннеров). */
  "data-testid"?: string;
}

export function Alert({
  tone,
  title,
  description,
  actions,
  icon,
  onClose,
  className,
  "data-testid": testId,
}: AlertProps) {
  const Icon = icon ?? TONE_ICON[tone];
  return (
    <div
      role="alert"
      data-testid={testId}
      data-tone={tone}
      className={cn(
        "flex gap-3 rounded-[10px] border px-4 py-3.5",
        "bg-[var(--tone-bg)] border-[var(--tone-bd)]",
        className,
      )}
      style={
        {
          // токены тона через CSS-переменные — корректно резолвятся в обеих темах
          "--tone-bg": `var(--${tone}-12)`,
          "--tone-bd": `var(--${tone}-40)`,
          "--tone-fg": `var(--${tone})`,
        } as React.CSSProperties
      }
    >
      <Icon className="h-[18px] w-[18px] flex-shrink-0 mt-0.5 text-[var(--tone-fg)]" />
      <div className="min-w-0 flex-1">
        <div className="text-[14px] font-medium text-[var(--fg-1)] leading-snug">{title}</div>
        {description != null && (
          <div className="text-[13px] text-[var(--fg-2)] leading-relaxed mt-1">{description}</div>
        )}
        {actions != null && <div className="flex flex-wrap gap-2 mt-3">{actions}</div>}
      </div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Закрыть"
          className="flex-shrink-0 -mr-1 -mt-0.5 p-1 rounded text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-2)] transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
