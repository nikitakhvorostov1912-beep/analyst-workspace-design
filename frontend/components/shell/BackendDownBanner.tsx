"use client";

import { useState } from "react";
import Link from "next/link";
import { RefreshCw, AlertOctagon } from "lucide-react";
import { Button } from "@/components/ui/button";

interface BackendDownBannerProps {
  /** Виден или нет — управляется хост-компонентом (HomePage / AppShell) */
  visible: boolean;
  /** Колбэк повторной проверки — должен вернуть промис, который завершится
   *  после нового вызова `fetchHealth`. Внутри банера — индикатор `Проверяю…`. */
  onRetry: () => Promise<void>;
}

/**
 * Sprint 03 (handoff F · BackendDownBanner): верхний баннер когда серверная
 * часть не отвечает.
 *
 * Заменяет мелкий chip в углу — раньше он был незаметен и пользователь думал
 * что приложение «зависло». Теперь явное предупреждение с действием:
 * `[Повторить]` (in-place retry) и `Диагностика →` (переход на /status).
 */
export function BackendDownBanner({
  visible,
  onRetry,
}: BackendDownBannerProps) {
  const [retrying, setRetrying] = useState(false);

  if (!visible) return null;

  async function handleRetry() {
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div
      role="alert"
      data-testid="backend-down-banner"
      className="fixed top-0 inset-x-0 z-50 flex items-center justify-between gap-3 px-4 py-2.5 bg-[var(--error-12)] border-b border-[var(--error-40)] text-sm animate-fade-up"
    >
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <AlertOctagon
          className="h-4 w-4 flex-none text-[var(--error)]"
          aria-hidden="true"
        />
        <span className="text-[var(--fg-1)] font-medium">
          Серверная часть не отвечает.
        </span>
        <span className="text-[var(--fg-3)] truncate hidden md:inline">
          Откройте «Диагностика» — там кнопка перезапуска и подробности.
        </span>
      </div>
      <div className="flex items-center gap-2 flex-none">
        <Button
          size="sm"
          variant="secondary"
          onClick={handleRetry}
          disabled={retrying}
          className="border-[var(--error-40)] text-[var(--error)] hover:bg-[var(--error-20)]"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 mr-1.5 ${retrying ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
          {retrying ? "Проверяю…" : "Повторить"}
        </Button>
        <Link
          href="/status"
          className="text-[10px] tracking-[0.18em] uppercase text-[var(--accent)] hover:underline font-medium"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          Диагностика →
        </Link>
      </div>
    </div>
  );
}
