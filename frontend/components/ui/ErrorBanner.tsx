"use client";

import { RotateCw } from "lucide-react";
import { Alert, type AlertTone } from "@/components/ui/Alert";
import { Button } from "@/components/ui/button";

/**
 * ErrorBanner — тонкая обёртка над единым `Alert` (redesign 2.0 §3.1, F-04).
 * Сохранён прежний API (severity/onRetry/onDismiss), чтобы не трогать call-site'ы,
 * но визуальный язык теперь общий с остальными сообщениями.
 */

export type ErrorSeverity = "info" | "warning" | "error";

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
  const tone: AlertTone = severity;
  return (
    <Alert
      tone={tone}
      title={title}
      description={description}
      onClose={onDismiss}
      className={className}
      data-testid="error-banner"
      actions={
        onRetry ? (
          <Button variant="ghost" size="sm" onClick={onRetry} className="h-8 px-2.5 gap-1.5">
            <RotateCw className="h-3.5 w-3.5" />
            Повторить
          </Button>
        ) : undefined
      }
    />
  );
}
