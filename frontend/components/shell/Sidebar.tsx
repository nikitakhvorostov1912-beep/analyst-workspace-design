"use client";

import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { Marker } from "@/components/ui/Marker";
import { SessionList } from "./SessionList";
import { cn } from "@/lib/utils";
import type { SessionsGrouped } from "@/lib/types";

interface SidebarProps {
  grouped?: SessionsGrouped;
  activeId?: string | null;
  onCreateNew?: () => void;
  onDelete?: (id: string) => void;
  /** Sprint 04 (M07): свёрнут или развёрнут. */
  collapsed?: boolean;
  /** Sprint 04 (M07): toggle handler. */
  onToggleCollapse?: () => void;
}

const EMPTY_GROUPED: SessionsGrouped = {
  today: [],
  yesterday: [],
  this_week: [],
  earlier: [],
};

export function Sidebar({
  grouped = EMPTY_GROUPED,
  activeId = null,
  onCreateNew,
  onDelete,
  collapsed = false,
  onToggleCollapse,
}: SidebarProps) {
  return (
    <aside className="flex flex-col h-full border-r border-[var(--bd-1)] bg-[var(--bg-0)] overflow-hidden">
      {/* Кнопка нового чата + collapse toggle */}
      <div className="p-3 border-b border-[var(--bd-1)] flex items-center gap-2">
        {collapsed ? (
          // Свёрнутый режим: только icon-кнопка «+» и chevron-right
          <button
            type="button"
            onClick={onCreateNew}
            className="flex-1 h-9 inline-flex items-center justify-center rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] hover:border-[var(--bd-3)] hover:bg-[var(--bg-3)] transition-colors text-[var(--fg-1)]"
            title="Новый чат"
            aria-label="Новый чат"
          >
            <Plus className="h-4 w-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onCreateNew}
            className="flex-1 flex items-center gap-2 h-9 px-3 rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] hover:border-[var(--bd-3)] hover:bg-[var(--bg-3)] transition-colors text-[var(--fg-1)]"
          >
            <Marker size={10} />
            <span
              className="font-semibold text-[12px] tracking-[0.08em] uppercase"
              style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
            >
              Новый чат
            </span>
            <Plus className="h-3.5 w-3.5 ml-auto text-[var(--fg-3)]" />
          </button>
        )}
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            className="flex-none h-9 w-9 inline-flex items-center justify-center rounded-md border border-[var(--bd-2)] bg-[var(--bg-2)] hover:bg-[var(--bg-3)] hover:border-[var(--bd-3)] text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors"
            aria-label={collapsed ? "Развернуть боковую панель" : "Свернуть боковую панель"}
            title={collapsed ? "Развернуть" : "Свернуть"}
            data-testid="sidebar-toggle"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        )}
      </div>

      {/* Список сессий — fade-out при collapsed */}
      <div
        className={cn(
          "flex-1 overflow-y-auto p-2 transition-opacity duration-200 ease-out",
          collapsed && "opacity-0 pointer-events-none",
        )}
        aria-hidden={collapsed}
      >
        <SessionList
          grouped={grouped}
          activeId={activeId}
          onDelete={onDelete ?? (() => {})}
        />
      </div>
    </aside>
  );
}
