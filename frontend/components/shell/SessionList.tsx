"use client";

import Link from "next/link";
import { Trash2 } from "lucide-react";
import type { SessionListItem, SessionsGrouped } from "@/lib/types";

interface SessionListProps {
  grouped: SessionsGrouped;
  activeId: string | null;
  onDelete: (id: string) => void;
}

/** Форматирует relative время на русском. */
function formatRelative(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHr / 24);

  if (diffMin < 1) return "только что";
  if (diffMin < 60) return `${diffMin} мин назад`;
  if (diffHr < 24) return `${diffHr} ч назад`;
  if (diffDays === 1) {
    return `вчера ${date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
  }
  return date.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

interface GroupSectionProps {
  label: string;
  items: SessionListItem[];
  activeId: string | null;
  onDelete: (id: string) => void;
}

function GroupSection({ label, items, activeId, onDelete }: GroupSectionProps) {
  if (items.length === 0) return null;

  return (
    <div className="mb-3">
      <div className="px-2 py-1 text-xs font-medium text-[var(--fg-muted)] uppercase tracking-wide">
        {label}
      </div>
      {items.map((item) => (
        <SessionItem
          key={item.id}
          item={item}
          isActive={item.id === activeId}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}

interface SessionItemProps {
  item: SessionListItem;
  isActive: boolean;
  onDelete: (id: string) => void;
}

function SessionItem({ item, isActive, onDelete }: SessionItemProps) {
  function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`Удалить чат "${item.title ?? "Новый чат"}"?`)) {
      onDelete(item.id);
    }
  }

  return (
    <Link
      href={`/sessions/${item.id}`}
      className={`group flex items-start gap-1 px-2 py-2 rounded text-sm transition-colors hover:bg-[var(--bg-elevated)] ${
        isActive ? "border-l-2 border-[var(--accent)] bg-[var(--bg-elevated)] pl-[6px]" : ""
      }`}
    >
      <div className="flex-1 min-w-0">
        <div
          className={`truncate text-sm ${
            item.title === null
              ? "text-[var(--fg-muted)] italic"
              : "text-[var(--fg)]"
          }`}
        >
          {item.title ?? "Новый чат"}
        </div>
        <div className="text-xs text-[var(--fg-muted)] mt-0.5">
          {item.message_count} сообщ. · {formatRelative(item.updated_at)}
        </div>
      </div>
      <button
        onClick={handleDelete}
        className="flex-none opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:text-red-400 text-[var(--fg-muted)]"
        aria-label="Удалить сессию"
      >
        <Trash2 size={14} />
      </button>
    </Link>
  );
}

export function SessionList({ grouped, activeId, onDelete }: SessionListProps) {
  const totalCount =
    grouped.today.length +
    grouped.yesterday.length +
    grouped.this_week.length +
    grouped.earlier.length;

  if (totalCount === 0) {
    return (
      <div className="px-4 py-3 text-xs text-[var(--fg-muted)] italic">
        Истории пока нет
      </div>
    );
  }

  return (
    <div>
      <GroupSection
        label="Сегодня"
        items={grouped.today}
        activeId={activeId}
        onDelete={onDelete}
      />
      <GroupSection
        label="Вчера"
        items={grouped.yesterday}
        activeId={activeId}
        onDelete={onDelete}
      />
      <GroupSection
        label="На этой неделе"
        items={grouped.this_week}
        activeId={activeId}
        onDelete={onDelete}
      />
      <GroupSection
        label="Раньше"
        items={grouped.earlier}
        activeId={activeId}
        onDelete={onDelete}
      />
    </div>
  );
}
