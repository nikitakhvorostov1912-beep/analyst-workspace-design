"use client";

import { useEffect, useState } from "react";
import { Lock, Unlock } from "lucide-react";
import { StencilChip } from "@/components/ui/StencilChip";
import { fetchConnections } from "@/lib/api";
import { getActiveChannelId } from "@/lib/storage";
import type { MCPConnection } from "@/lib/types";

interface AnonymizationStatusProps {
  /**
   * Опционально — id активного канала. Если не передан, читается из
   * `getActiveChannelId()`. Передавать когда parent уже знает (Header).
   */
  activeChannelId?: string | null;
}

/**
 * Read-only индикатор состояния анонимизации.
 *
 * 2026-05-24 (rewrite): раньше был toggle с localStorage `analyst.anon_enabled`.
 * Это было неправильно — параметр маскировки задаётся НА СТОРОНЕ 1С обработки
 * (галочка в EPF/CFE), а не на стороне UI. UI просто отображает что 1С
 * прислала анонимизированные данные.
 *
 * Источник истины — поле `anon_enabled` в `MCPConnection` (backend ходит
 * к 1С при ping и узнаёт текущее состояние обработки).
 *
 * Если активной базы нет — chip скрыт (нет смысла показывать состояние).
 *
 * Обновляется при:
 *  - mount
 *  - смене активного канала (event `active-channel-changed`)
 *  - обновлении списка connections (event `connections-updated`)
 */
export function AnonymizationStatus({
  activeChannelId,
}: AnonymizationStatusProps) {
  const [connections, setConnections] = useState<MCPConnection[]>([]);
  const [resolvedChannelId, setResolvedChannelId] = useState<string | null>(
    activeChannelId ?? null,
  );

  // Refresh connections list
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const conns = await fetchConnections();
        if (!cancelled) setConnections(conns);
      } catch {
        // backend недоступен — chip скроется (нет данных)
      }
    }
    void load();

    function handleConnectionsUpdate() {
      void load();
    }
    function handleChannelChange(e: Event) {
      const detail = (e as CustomEvent<{ id: string | null }>).detail;
      if (detail) setResolvedChannelId(detail.id);
    }
    if (typeof window !== "undefined") {
      window.addEventListener("connections-updated", handleConnectionsUpdate);
      window.addEventListener("active-channel-changed", handleChannelChange);
    }
    return () => {
      cancelled = true;
      if (typeof window !== "undefined") {
        window.removeEventListener(
          "connections-updated",
          handleConnectionsUpdate,
        );
        window.removeEventListener(
          "active-channel-changed",
          handleChannelChange,
        );
      }
    };
  }, []);

  // Sync prop -> state когда parent явно передаёт activeChannelId
  useEffect(() => {
    if (activeChannelId !== undefined) {
      setResolvedChannelId(activeChannelId);
    } else if (typeof window !== "undefined") {
      // Fallback: читаем из localStorage когда prop не указан
      setResolvedChannelId(getActiveChannelId());
    }
  }, [activeChannelId]);

  if (!resolvedChannelId || connections.length === 0) return null;

  const active = connections.find((c) => c.id === resolvedChannelId);
  if (!active) return null;

  const enabled = Boolean(active.anon_enabled);
  const Icon = enabled ? Lock : Unlock;

  return (
    <StencilChip
      tone={enabled ? "warn" : "muted"}
      aria-label={
        enabled
          ? "Маскировка имён включена в обработке 1С — реальные имена скрыты"
          : "Маскировка имён отключена в обработке 1С — имена приходят как есть"
      }
      title={
        enabled
          ? "Маскировка ВКЛ — задано в обработке 1С (CFE/EPF). Меняется на стороне 1С администратором."
          : "Маскировка ВЫКЛ — задано в обработке 1С. Меняется на стороне 1С администратором."
      }
      data-testid="anon-status"
      data-state={enabled ? "on" : "off"}
    >
      <Icon className="h-3 w-3 shrink-0" />
      <span>Аноним · {enabled ? "ВКЛ" : "ВЫКЛ"}</span>
    </StencilChip>
  );
}
