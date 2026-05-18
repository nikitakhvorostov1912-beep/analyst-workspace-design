"use client";

import { useEffect, useState } from "react";
import { Lock, Unlock } from "lucide-react";
import { cn } from "@/lib/utils";
import { getAnonEnabled, setAnonEnabled } from "@/lib/storage";

/**
 * Глобальный переключатель анонимизации (amber pill дизайн).
 *
 * - Состояние хранится в localStorage: `analyst.anon_enabled`
 * - Диспатчит CustomEvent `anon-toggle` для синхронизации без re-mount
 * - SSR-safe: читает localStorage только в useEffect (не в initial render)
 *
 * Phase 04-01 (поведение) + Phase 11.3 (визуал из Claude Design v2).
 */
export function AnonymizationToggle() {
  // Инициализируем false для SSR — значение подставляется в useEffect
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    setEnabled(getAnonEnabled());
  }, []);

  function handleToggle() {
    const next = !enabled;
    setEnabled(next);
    setAnonEnabled(next);

    // Диспатчим событие для useChatStream и других слушателей
    window.dispatchEvent(new CustomEvent("anon-toggle", { detail: { enabled: next } }));
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      aria-pressed={enabled}
      aria-label="Переключатель анонимизации"
      data-anon={enabled ? "on" : "off"}
      title={
        enabled
          ? "Анонимизация ВКЛ — нажмите для отключения"
          : "Анонимизация ВЫКЛ — нажмите для включения"
      }
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 h-[30px] rounded-md text-xs border transition-colors duration-micro ease-design-ease select-none",
        enabled
          ? "bg-[var(--warning-12)] text-[var(--warning)] border-[var(--warning-20)] hover:bg-[var(--warning-20)]"
          : "bg-[var(--bg-1)] text-[var(--fg-3)] border-[var(--bd-2)] hover:text-[var(--fg-1)] hover:border-[var(--bd-3)]",
      )}
    >
      {enabled ? (
        <Lock className="h-3 w-3 shrink-0" />
      ) : (
        <Unlock className="h-3 w-3 shrink-0" />
      )}
      <span className="hidden sm:inline whitespace-nowrap">
        Анон: <span className="font-mono">{enabled ? "ВКЛ" : "ВЫКЛ"}</span>
      </span>
    </button>
  );
}
