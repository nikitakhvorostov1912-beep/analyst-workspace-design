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

  return (
    <div
      className="fixed top-0 left-0 right-0 z-40 flex items-center justify-between gap-3 px-4 py-3 bg-red-950 border-b border-red-700 text-red-200 text-sm"
      role="alert"
    >
      <span>{text}</span>
      <Button
        size="sm"
        variant="secondary"
        onClick={onRetry}
        disabled={retrying}
        className="flex items-center gap-1.5 border-red-600 text-red-200 hover:bg-red-900"
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
