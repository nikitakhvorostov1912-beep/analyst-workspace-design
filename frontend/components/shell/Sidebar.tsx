"use client";

import { Plus } from "lucide-react";
import { Marker } from "@/components/ui/Marker";
import { SessionList } from "./SessionList";
import type { SessionsGrouped } from "@/lib/types";

interface SidebarProps {
  grouped?: SessionsGrouped;
  activeId?: string | null;
  onCreateNew?: () => void;
  onDelete?: (id: string) => void;
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
}: SidebarProps) {
  return (
    <aside className="flex flex-col h-full border-r border-[var(--bd-1)] bg-[var(--bg-0)]">
      {/* Кнопка нового чата — brand pattern: marker + mono uppercase */}
      <div className="p-3 border-b border-[var(--bd-1)]">
        <button
          type="button"
          onClick={onCreateNew}
          className="w-full flex items-center gap-2 h-9 px-3 rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] hover:border-[var(--bd-3)] hover:bg-[var(--bg-3)] transition-colors text-[var(--fg-1)]"
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
      </div>

      {/* Список сессий с группировкой */}
      <div className="flex-1 overflow-y-auto p-2">
        <SessionList
          grouped={grouped}
          activeId={activeId}
          onDelete={onDelete ?? (() => {})}
        />
      </div>
    </aside>
  );
}
