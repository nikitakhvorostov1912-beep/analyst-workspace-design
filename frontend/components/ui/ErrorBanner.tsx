"use client";

import type { ComponentType } from "react";
import { AlertCircle, AlertTriangle, Info, RotateCw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ErrorSeverity = "info" | "warning" | "error";

interface SeverityMeta {
  icon: ComponentType<{ className?: string }>;
  classes: string;
}

const SEVERITY: Record<ErrorSeverity, SeverityMeta> = {
  info: {
    icon: Info,
    classes:
      "bg-[var(--accent-08)] border-[var(--accent-20)] text-[var(--accent)]",
  },
  warning: {
    icon: AlertTriangle,
    classes:
      "bg-[var(--warning-12)] border-[var(--warning-20)] text-[var(--warning)]",
  },
  error: {
    icon: AlertCircle,
    classes: "bg-[var(--error-12)] border-[var(--error-20)] text-[var(--error)]",
  },
};

interface ErrorBannerProps {
  severity?: ErrorSeverity;
  title: string;
  description?: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}

export function ErrorBanner({
  severity = "error",
  title,
  description,
  onRetry,
  onDismiss,
  className,
}: ErrorBannerProps) {
  const meta = SEVERITY[severity];
  const Icon = meta.icon;

  return (
    <div
      role="alert"
      data-severity={severity}
      className={cn(
        "flex items-start gap-3 p-3 rounded-md border animate-fade-up",
        meta.classes,
        className,
      )}
    >
      <Icon className="h-4 w-4 flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-[var(--fg-1)]">{title}</div>
        {description && (
          <div className="text-xs text-[var(--fg-3)] mt-1">{description}</div>
        )}
      </div>
      <div className="flex items-center gap-1">
        {onRetry && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRetry}
            className="h-7 px-2 gap-1.5"
          >
            <RotateCw className="h-3 w-3" />
            Повторить
          </Button>
        )}
        {onDismiss && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onDismiss}
            className="h-7 w-7"
            aria-label="Закрыть"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
}
