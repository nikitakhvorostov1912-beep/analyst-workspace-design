"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { PanelLeftClose, PanelLeftOpen, Plus, Search, X } from "lucide-react";
import { Marker } from "@/components/ui/Marker";
import { SessionList } from "./SessionList";
import type { SessionsGrouped, SessionListItem } from "@/lib/types";

/** F-11: свёрнутый сайдбар — вертикальная полоса иконок чатов (вместо пустоты). */
function CollapsedSessionStrip({
  grouped,
  activeId,
}: {
  grouped: SessionsGrouped;
  activeId: string | null;
}) {
  const items = [
    ...grouped.today,
    ...grouped.yesterday,
    ...grouped.this_week,
    ...grouped.earlier,
  ].slice(0, 20);
  if (items.length === 0) return null;
  return (
    <div className="flex flex-col items-center gap-1">
      {items.map((s) => {
        const active = s.id === activeId;
        const letter = (s.title ?? "Ч").trim().charAt(0).toUpperCase() || "Ч";
        return (
          <Link
            key={s.id}
            href={`/sessions/${s.id}`}
            title={s.title ?? "Новый чат"}
            aria-label={s.title ?? "Новый чат"}
            className={`relative h-8 w-8 inline-flex items-center justify-center rounded-md text-[12px] font-medium transition-colors ${
              active
                ? "bg-[var(--bg-2)] text-[var(--fg-1)] border border-[var(--accent-32)]"
                : "text-[var(--fg-3)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)] border border-transparent"
            }`}
            style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
          >
            {active && (
              <span
                aria-hidden="true"
                className="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full"
                style={{ background: "var(--accent)" }}
              />
            )}
            {letter}
          </Link>
        );
      })}
    </div>
  );
}

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
  onRename,
  onPin,
  collapsed = false,
  onToggleCollapse,
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

  return (
    <aside className="flex flex-col h-full border-r border-[var(--bd-1)] bg-[var(--bg-0)] overflow-hidden">
      {/* Шапка: отдельная понятная кнопка сворачивания/разворачивания панели
          (иконка PanelLeft — стандарт «боковая панель», как в VS Code/Linear) +
          кнопка нового чата. В свёрнутом режиме — вертикальный стек, чтобы кнопки
          не теснились в 56px и каждая была читаемой. */}
      <div className="p-3 border-b border-[var(--bd-1)]">
        {collapsed ? (
          <div className="flex flex-col gap-2">
            {onToggleCollapse && (
              <button
                type="button"
                onClick={onToggleCollapse}
                className="h-9 w-full inline-flex items-center justify-center rounded-md border border-[var(--bd-2)] bg-[var(--bg-2)] hover:bg-[var(--bg-3)] hover:border-[var(--accent-32)] text-[var(--fg-2)] hover:text-[var(--accent)] transition-colors"
                aria-label="Развернуть боковую панель"
                title="Развернуть панель с чатами"
                data-testid="sidebar-toggle"
              >
                <PanelLeftOpen className="h-4 w-4" />
              </button>
            )}
            <button
              type="button"
              onClick={onCreateNew}
              className="h-9 w-full inline-flex items-center justify-center rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] hover:border-[var(--bd-3)] hover:bg-[var(--bg-3)] transition-colors text-[var(--fg-1)]"
              title="Новый чат"
              aria-label="Новый чат"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
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
            {onToggleCollapse && (
              <button
                type="button"
                onClick={onToggleCollapse}
                className="flex-none h-9 w-9 inline-flex items-center justify-center rounded-md border border-[var(--bd-2)] bg-[var(--bg-2)] hover:bg-[var(--bg-3)] hover:border-[var(--accent-32)] text-[var(--fg-2)] hover:text-[var(--accent)] transition-colors"
                aria-label="Свернуть боковую панель"
                title="Свернуть панель"
                data-testid="sidebar-toggle"
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Поиск по чатам (F-11) — скрыт в свёрнутом режиме и при отсутствии чатов */}
      {!collapsed && hasAnySession && (
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

      {/* Список сессий: развёрнут — полный, свёрнут — полоса иконок (F-11) */}
      <div className="flex-1 overflow-y-auto p-2">
        {collapsed ? (
          <CollapsedSessionStrip grouped={grouped} activeId={activeId} />
        ) : noMatches ? (
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
