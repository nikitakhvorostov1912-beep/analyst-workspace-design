"use client";

import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ConnectionStatusBannerProps {
  visible: boolean;
  channelName?: string;
  onRetry: () => void;
  retrying: boolean;
}

/**
 * Красный баннер поверх чата при разрыве соединения с 1С MCP.
 * Показывает сообщение и кнопку «Повторить».
 * При retrying=true — кнопка заблокирована со спиннером.
 */
export function ConnectionStatusBanner({
  visible,
  channelName,
  onRetry,
  retrying,
}: ConnectionStatusBannerProps) {
  if (!visible) return null;

  const text = channelName
    ? `Подключение к базе "${channelName}" потеряно`
    : "Подключение к 1С потеряно";

  // UX-13 fix (2026-05-24): раньше top-0 → banner накладывался на Header
  // (52px) и перекрывал logo «АНАЛИТИК». Header — sticky top-0 z-10,
  // banner был z-40 (выше) и full-width поверх. Решение: top-[52px]
  // чтобы banner шёл ПОД Header'ом, остаётся виден без overlay logo.
  return (
    <div
      className="fixed top-[52px] left-0 right-0 z-40 flex items-center justify-between gap-3 px-4 py-3 bg-[var(--error-12)] border-b border-[var(--error-40)] text-[var(--error)] text-sm"
      role="alert"
    >
      <span>{text}</span>
      <Button
        size="sm"
        variant="secondary"
        onClick={onRetry}
        disabled={retrying}
        className="flex items-center gap-1.5 border-[var(--error-40)] text-[var(--error)] hover:bg-[var(--error-20)]"
      >
        {retrying ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            <span>Повторяю...</span>
          </>
        ) : (
          <span>Повторить</span>
        )}
      </Button>
    </div>
  );
}
