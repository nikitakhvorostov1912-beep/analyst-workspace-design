"use client";

import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
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
    <aside className="flex flex-col h-full border-r border-[var(--border)] bg-[var(--bg)]">
      {/* Кнопка нового чата */}
      <div className="p-3 border-b border-[var(--border)]">
        <Button
          variant="secondary"
          className="w-full justify-start gap-2 text-sm"
          onClick={onCreateNew}
        >
          <Plus size={16} />
          Новый чат
        </Button>
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
