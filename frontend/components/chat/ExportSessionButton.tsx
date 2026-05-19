"use client";

import { useState } from "react";
import { Check, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { publishToast } from "@/lib/toast";
import { sessionExportFilename, sessionToMarkdown } from "@/lib/session-export";
import { cn } from "@/lib/utils";
import type { ChatMessage, SessionDetail } from "@/lib/types";

interface ExportSessionButtonProps {
  detail: SessionDetail | null;
  messages: readonly ChatMessage[];
  /** Дополнительные классы для позиционирования (по умолчанию absolute top-right). */
  className?: string;
}

/**
 * Кнопка «Экспорт чата» в шапке сессии. Один клик:
 *   1. Собирает markdown из всех сообщений + tool_calls + cards
 *   2. Копирует в clipboard
 *   3. Toast «Скопировано»
 * Fallback (insecure context / clipboard API недоступен) — скачивание .md.
 *
 * Тонкая обёртка над pure sessionToMarkdown(), вся логика сборки markdown в lib.
 */
export function ExportSessionButton({
  detail,
  messages,
  className,
}: ExportSessionButtonProps) {
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (busy || messages.length === 0) return;
    setBusy(true);
    try {
      const md = sessionToMarkdown(detail, messages);
      const ok = await copyOrDownload(md, sessionExportFilename(detail));
      if (ok === "copied") {
        publishToast({
          type: "info",
          message: `Чат скопирован в буфер обмена · ${messages.length} сообщений`,
        });
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      } else if (ok === "downloaded") {
        publishToast({
          type: "info",
          message: "Чат сохранён в файл (буфер обмена недоступен)",
        });
      } else {
        publishToast({ type: "error", message: "Не удалось экспортировать чат" });
      }
    } finally {
      setBusy(false);
    }
  }

  const disabled = messages.length === 0;

  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={handleClick}
      disabled={disabled || busy}
      title={
        disabled
          ? "Сначала задайте вопрос"
          : "Скопировать всю переписку в буфер (для передачи аналитику/в Claude)"
      }
      className={cn(
        "gap-1.5 h-8 px-2.5 text-[12px] font-medium",
        "bg-[var(--bg-2)] hover:bg-[var(--bg-hover)] border-[var(--bd-2)]",
        className,
      )}
      data-testid="export-session-button"
    >
      {copied ? (
        <Check size={14} className="text-green-500" />
      ) : (
        <Download size={14} />
      )}
      <span>{copied ? "Скопировано" : "Экспорт чата"}</span>
    </Button>
  );
}

type CopyResult = "copied" | "downloaded" | "failed";

async function copyOrDownload(text: string, filename: string): Promise<CopyResult> {
  // Сначала пробуем clipboard API — стандартный путь.
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return "copied";
    } catch {
      // fall through
    }
  }
  // Fallback 1: legacy execCommand через скрытую textarea.
  if (typeof document !== "undefined") {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      if (ok) return "copied";
    } catch {
      // fall through
    }
    // Fallback 2: скачивание файла — точно работает везде.
    try {
      const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      return "downloaded";
    } catch {
      return "failed";
    }
  }
  return "failed";
}
