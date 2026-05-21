"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

interface CopyButtonProps {
  /** Что копировать. Если пусто — кнопка disabled. */
  value: string;
  /** Подпись tooltip (по умолчанию: «Скопировать»). */
  label?: string;
  size?: "xs" | "sm";
  className?: string;
}

/**
 * Маленькая кнопка «копировать» с feedback-галочкой.
 * Для диагностики аналитик копирует адреса/пути и шлёт ИТ-отделу одним нажатием.
 */
export function CopyButton({
  value,
  label = "Скопировать",
  size = "xs",
  className,
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      // если clipboard API недоступен (insecure context) — fallback на textarea
      const ta = document.createElement("textarea");
      ta.value = value;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        setCopied(true);
        setTimeout(() => setCopied(false), 1400);
      } finally {
        document.body.removeChild(ta);
      }
    }
  }

  const sizeClass = size === "xs" ? "h-5 w-5 p-0.5" : "h-6 w-6 p-1";
  const iconSize = size === "xs" ? 12 : 14;

  return (
    <button
      type="button"
      onClick={handleCopy}
      disabled={!value}
      title={copied ? "Скопировано" : label}
      aria-label={label}
      className={cn(
        "inline-flex items-center justify-center rounded transition-colors flex-none",
        "text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-hover)]",
        "disabled:opacity-40 disabled:cursor-not-allowed",
        sizeClass,
        className,
      )}
    >
      {copied ? (
        <Check size={iconSize} className="text-[var(--success)]" />
      ) : (
        <Copy size={iconSize} />
      )}
    </button>
  );
}
