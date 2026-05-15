"use client";

import { useEffect, useState } from "react";
import { Lock, LockOpen } from "lucide-react";
import { getAnonEnabled, setAnonEnabled } from "@/lib/storage";

/**
 * Глобальный переключатель анонимизации.
 *
 * - Состояние хранится в localStorage: `analyst.anon_enabled`
 * - Диспатчит CustomEvent `anon-toggle` для синхронизации без re-mount
 * - SSR-safe: читает localStorage только в useEffect (не в initial render)
 *
 * Plan 04-01.
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
      title={enabled ? "Анонимизация ВКЛ — нажмите для отключения" : "Анонимизация ВЫКЛ — нажмите для включения"}
      className={[
        "flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors select-none",
        enabled
          ? "bg-amber-500/15 border border-amber-500/40 text-amber-400 hover:bg-amber-500/25"
          : "bg-transparent border border-[var(--border)] text-[var(--fg-muted)] hover:text-[var(--fg)] hover:border-[var(--fg-muted)]",
      ].join(" ")}
    >
      {enabled ? (
        <Lock size={13} className="shrink-0" />
      ) : (
        <LockOpen size={13} className="shrink-0" />
      )}
      <span className="hidden sm:inline whitespace-nowrap">
        {enabled ? "Анон: ВКЛ" : "Анон: ВЫКЛ"}
      </span>
    </button>
  );
}
