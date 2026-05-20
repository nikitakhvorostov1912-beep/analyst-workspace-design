"use client";

import { useEffect, useState } from "react";
import { Lock, Unlock } from "lucide-react";
import { StencilChip } from "@/components/ui/StencilChip";
import { getAnonEnabled, setAnonEnabled } from "@/lib/storage";

/**
 * Глобальный переключатель анонимизации.
 *
 * Stencil/Mono redesign (2026-05-20): теперь это StencilChip с двумя
 * состояниями — ВКЛ = warn (охра), ВЫКЛ = muted (нейтральный).
 * Раньше был отдельный amber pill, теперь системный chip с brand-стилем.
 *
 * Поведение:
 *   - Состояние в localStorage `analyst.anon_enabled`
 *   - Диспатчит CustomEvent `anon-toggle` для синхронизации
 *   - SSR-safe: читает localStorage только в useEffect
 */
export function AnonymizationToggle() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    setEnabled(getAnonEnabled());
  }, []);

  function handleToggle() {
    const next = !enabled;
    setEnabled(next);
    setAnonEnabled(next);
    window.dispatchEvent(new CustomEvent("anon-toggle", { detail: { enabled: next } }));
  }

  const Icon = enabled ? Lock : Unlock;

  return (
    <StencilChip
      tone={enabled ? "warn" : "muted"}
      asButton
      onClick={handleToggle}
      aria-pressed={enabled}
      aria-label="Переключатель анонимизации"
      title={
        enabled
          ? "Маскировка ВКЛ — реальные имена контрагентов/документов скрыты. Нажмите для отключения."
          : "Маскировка ВЫКЛ — нажмите для включения, чтобы скрыть реальные имена."
      }
      data-testid="anon-toggle"
    >
      <Icon className="h-3 w-3 shrink-0" />
      <span>Аноним · {enabled ? "ВКЛ" : "ВЫКЛ"}</span>
    </StencilChip>
  );
}
