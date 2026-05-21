"use client";

import Link from "next/link";
import { Trash2 } from "lucide-react";
import type { SessionListItem, SessionsGrouped } from "@/lib/types";
import { parseBackendDate } from "@/lib/utils";

interface SessionListProps {
  grouped: SessionsGrouped;
  activeId: string | null;
  onDelete: (id: string) => void;
}

/** Форматирует relative время на русском.
 *
 * `parseBackendDate` из lib/utils форсирует UTC для timezone-naive строк,
 * иначе на машине пользователя в Москве (+3) свежесозданная сессия
 * отображается как «3 часа назад» вместо «только что».
 */
function formatRelative(isoString: string): string {
  const date = parseBackendDate(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHr / 24);

  if (diffMin < 1) return "только что";
  if (diffMin < 60) return `${diffMin} мин назад`;
  if (diffHr < 24) return `${diffHr} ч назад`;
  if (diffDays < 0) {
    // Часы из будущего (clock skew между backend и клиентом) — показываем как "только что"
    return "только что";
  }
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

  // Brand pattern: «СЕГОДНЯ ──────── 03»
  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 px-2.5 pt-1 pb-1.5">
        <span
          className="text-[9.5px] tracking-[0.22em] uppercase text-[var(--fg-4)] flex-none"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          {label}
        </span>
        <span
          className="flex-1 h-px"
          style={{ background: "var(--bd-1)" }}
          aria-hidden="true"
        />
        <span
          className="text-[9.5px] tracking-[0.12em] text-[var(--fg-4)] flex-none tabular-nums"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          {String(items.length).padStart(2, "0")}
        </span>
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

  // Короткий ID — первые 4 hex-символа UUID (для brand-eyebrow «#A4F2»)
  const shortId = item.id.replace(/-/g, "").slice(0, 4).toUpperCase();

  return (
    <Link
      href={`/sessions/${item.id}`}
      className={`group relative flex items-start gap-2 px-2.5 py-2 rounded-md mb-0.5 transition-colors ${
        isActive
          ? "bg-[var(--bg-2)] text-[var(--fg-1)]"
          : "hover:bg-[var(--bg-2)] text-[var(--fg-2)] hover:text-[var(--fg-1)]"
      }`}
    >
      {/* Active = signal bar slева (brand pattern) */}
      {isActive && (
        <span
          aria-hidden="true"
          className="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full"
          style={{ background: "var(--accent)" }}
        />
      )}

      <div className="flex-1 min-w-0">
        {/* Brand eyebrow: #ID · time */}
        <div
          className="flex items-center gap-1.5 mb-0.5 text-[9px] tracking-[0.16em] uppercase text-[var(--fg-4)]"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          <span>#{shortId}</span>
          <span className="text-[var(--fg-4)]">·</span>
          <span className="text-[var(--fg-3)]">{item.message_count} сообщ.</span>
          <span className="ml-auto">{formatRelative(item.updated_at)}</span>
        </div>
        <div
          className={`truncate text-[13px] font-medium ${
            item.title === null ? "text-[var(--fg-3)] italic" : ""
          }`}
        >
          {item.title ?? "Новый чат"}
        </div>
      </div>
      <button
        onClick={handleDelete}
        className="flex-none opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:text-[var(--error)] text-[var(--fg-3)]"
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
