"use client";

import { useState, useMemo } from "react";
import { ChevronDown, ChevronRight, Hash, Link2, FileText, Bell, Shield, MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ReferencesCardPayload, ReferenceItem } from "@/lib/types";

// Иконки по usage_kind
function KindIcon({ kind }: { kind: string }) {
  const cls = "h-3.5 w-3.5 shrink-0";
  switch (kind) {
    case "Реквизит": return <Hash className={cls} />;
    case "Подчинённый": return <Link2 className={cls} />;
    case "Шаблон": return <FileText className={cls} />;
    case "Подписка": return <Bell className={cls} />;
    case "Право": return <Shield className={cls} />;
    default: return <MoreHorizontal className={cls} />;
  }
}

interface ReferenceGroupProps {
  kind: string;
  items: ReferenceItem[];
  defaultOpen: boolean;
  onLinkClick?: (item: ReferenceItem) => void;
  filter: string;
}

function ReferenceGroupSection({ kind, items, defaultOpen, onLinkClick, filter }: ReferenceGroupProps) {
  const [open, setOpen] = useState(defaultOpen);

  const filteredItems = useMemo(() => {
    if (!filter.trim()) return items;
    const lower = filter.toLowerCase();
    return items.filter(
      (item) =>
        item.name.toLowerCase().includes(lower) ||
        item.full_path.toLowerCase().includes(lower),
    );
  }, [items, filter]);

  if (filteredItems.length === 0) return null;

  return (
    <div className="border-b border-[var(--border)] last:border-b-0">
      <button
        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-[var(--bg-surface)] text-left"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 text-[var(--fg-muted)] shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-[var(--fg-muted)] shrink-0" />
        )}
        <KindIcon kind={kind} />
        <span className="text-xs font-medium text-[var(--fg)]">{kind}</span>
        <span className="ml-auto text-xs text-[var(--fg-muted)]">{filteredItems.length}</span>
      </button>

      {open && (
        <ul className="py-0.5">
          {filteredItems.map((item, idx) => (
            <li key={idx}>
              {onLinkClick ? (
                <button
                  className={cn(
                    "w-full text-left px-6 py-1 hover:bg-[var(--bg-surface)]",
                    "flex items-start gap-2",
                  )}
                  onClick={() => onLinkClick(item)}
                  title={`Покажи ${item.name}`}
                >
                  <span className="text-xs text-[var(--fg)] font-mono truncate flex-1">
                    {item.full_path}
                  </span>
                  <span className="text-xs text-[var(--fg-muted)] shrink-0">{item.object_type}</span>
                </button>
              ) : (
                <div className="px-6 py-1 flex items-start gap-2">
                  <span className="text-xs text-[var(--fg)] font-mono truncate flex-1">
                    {item.full_path}
                  </span>
                  <span className="text-xs text-[var(--fg-muted)] shrink-0">{item.object_type}</span>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface ReferencesCardProps {
  payload: ReferencesCardPayload;
  onLinkClick?: (item: ReferenceItem) => void;
}

export function ReferencesCard({ payload, onLinkClick }: ReferencesCardProps) {
  const { groups, total } = payload;
  const [filter, setFilter] = useState("");

  const totalLabel = `Используется в ${total} ${
    total === 1 ? "месте" : total < 5 ? "местах" : "местах"
  }`;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] overflow-hidden">
      {/* Заголовок */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border)]">
        <span className="text-xs text-[var(--fg-muted)]">{totalLabel}</span>
      </div>

      {/* Фильтр */}
      <div className="px-3 py-1.5 border-b border-[var(--border)]">
        <input
          type="text"
          placeholder="Фильтр по имени или пути..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className={cn(
            "w-full bg-transparent text-xs text-[var(--fg)] placeholder:text-[var(--fg-muted)]",
            "border border-[var(--border)] rounded px-2 py-1 outline-none",
            "focus:border-[var(--accent)]",
          )}
        />
      </div>

      {/* Группы */}
      {groups.map((group, idx) => (
        <ReferenceGroupSection
          key={group.kind}
          kind={group.kind}
          items={group.items}
          defaultOpen={idx < 2}
          onLinkClick={onLinkClick}
          filter={filter}
        />
      ))}
    </div>
  );
}
