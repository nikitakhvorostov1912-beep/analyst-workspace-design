"use client";

import { useMemo, useState } from "react";
import { Plus, Search, X } from "lucide-react";
import { Marker } from "@/components/ui/Marker";
import { SessionList } from "./SessionList";
import type { SessionsGrouped, SessionListItem } from "@/lib/types";

/** Фильтрует сгруппированные сессии по подстроке в title (F-11 поиск). */
function filterGrouped(grouped: SessionsGrouped, query: string): SessionsGrouped {
  const q = query.trim().toLowerCase();
  if (!q) return grouped;
  const pick = (arr: SessionListItem[]) =>
    arr.filter((s) => (s.title ?? "").toLowerCase().includes(q));
  return {
    today: pick(grouped.today),
    yesterday: pick(grouped.yesterday),
    this_week: pick(grouped.this_week),
    earlier: pick(grouped.earlier),
  };
}

interface SidebarProps {
  grouped?: SessionsGrouped;
  activeId?: string | null;
  onCreateNew?: () => void;
  onDelete?: (id: string) => void;
  /** F-11: переименование чата. */
  onRename?: (id: string, title: string) => void;
  /** F-11: закрепить/открепить чат. */
  onPin?: (id: string, pinned: boolean) => void;
  /** Свёрнут или развёрнут. Переключатель живёт в Header. */
  collapsed?: boolean;
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
  onRename,
  onPin,
  collapsed = false,
}: SidebarProps) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => filterGrouped(grouped, query), [grouped, query]);
  const hasAnySession =
    grouped.today.length +
      grouped.yesterday.length +
      grouped.this_week.length +
      grouped.earlier.length >
    0;
  const noMatches =
    query.trim() !== "" &&
    filtered.today.length +
      filtered.yesterday.length +
      filtered.this_week.length +
      filtered.earlier.length ===
      0;

  // Свёрнутый режим — панель пустая и скрытая (ширина колонки 0 задаётся в
  // AppShell). Контрол разворота вынесен в Header, чтобы рельс не засорять.
  // Пустой <aside> сохраняем для стабильного grid-placement остальных ячеек.
  if (collapsed) {
    return <aside aria-hidden="true" className="h-full overflow-hidden" />;
  }

  return (
    <aside className="flex flex-col h-full border-r border-[var(--bd-1)] bg-[var(--bg-0)] overflow-hidden">
      {/* Новый чат */}
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

      {/* Поиск по чатам (F-11) — при наличии чатов */}
      {hasAnySession && (
        <div className="px-3 pt-2.5 pb-1.5">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--fg-3)] pointer-events-none" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Поиск по чатам"
              aria-label="Поиск по чатам"
              data-testid="sidebar-search"
              className="w-full h-8 pl-8 pr-7 rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] text-[12.5px] text-[var(--fg-1)] placeholder:text-[var(--fg-3)] focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                aria-label="Очистить поиск"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-[var(--fg-3)] hover:text-[var(--fg-1)]"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Список сессий */}
      <div className="flex-1 overflow-y-auto p-2">
        {noMatches ? (
          <p className="text-center text-[12px] text-[var(--fg-3)] py-6">
            Ничего не найдено по «{query.trim()}»
          </p>
        ) : (
          <SessionList
            grouped={filtered}
            activeId={activeId}
            onDelete={onDelete ?? (() => {})}
            onRename={onRename}
            onPin={onPin}
          />
        )}
      </div>
    </aside>
  );
}
