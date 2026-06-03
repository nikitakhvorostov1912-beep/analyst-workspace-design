"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Check, Pencil, Pin, Trash2, X } from "lucide-react";
import type { SessionListItem, SessionsGrouped } from "@/lib/types";
import { parseBackendDate } from "@/lib/utils";

interface SessionListProps {
  grouped: SessionsGrouped;
  activeId: string | null;
  onDelete: (id: string) => void;
  /** F-11: переименование чата. Если не задан — карандаш скрыт. */
  onRename?: (id: string, title: string) => void;
  /** F-11: закрепить/открепить чат. Если не задан — кнопка скрыта. */
  onPin?: (id: string, pinned: boolean) => void;
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
  onRename?: (id: string, title: string) => void;
  onPin?: (id: string, pinned: boolean) => void;
}

function GroupSection({ label, items, activeId, onDelete, onRename, onPin }: GroupSectionProps) {
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
          onRename={onRename}
          onPin={onPin}
        />
      ))}
    </div>
  );
}

interface SessionItemProps {
  item: SessionListItem;
  isActive: boolean;
  onDelete: (id: string) => void;
  onRename?: (id: string, title: string) => void;
  onPin?: (id: string, pinned: boolean) => void;
}

function SessionItem({ item, isActive, onDelete, onRename, onPin }: SessionItemProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.title ?? "");
  const inputRef = useRef<HTMLInputElement>(null);

  // Sprint 02 (handoff A): window.confirm заменён на оптимистичное удаление
  // с UndoToast — onDelete сразу убирает item из UI, через 5с делается
  // реальный DELETE на бэк, либо «↺ Отменить» восстанавливает.
  function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    onDelete(item.id);
  }

  function startEdit(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDraft(item.title ?? "");
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  }

  function commit() {
    const next = draft.trim();
    if (next && next !== item.title) onRename?.(item.id, next);
    setEditing(false);
  }

  function cancel() {
    setEditing(false);
    setDraft(item.title ?? "");
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
      onClick={editing ? (e) => e.preventDefault() : undefined}
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
        {editing ? (
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onClick={(e) => e.preventDefault()}
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === "Enter") {
                e.preventDefault();
                commit();
              } else if (e.key === "Escape") {
                e.preventDefault();
                cancel();
              }
            }}
            onBlur={commit}
            aria-label="Новое название чата"
            data-testid="session-rename-input"
            className="w-full bg-[var(--bg-1)] border border-[var(--accent)] rounded px-1.5 py-0.5 text-[13px] text-[var(--fg-1)] focus:outline-none"
          />
        ) : (
          <div
            className={`truncate text-[13px] font-medium ${
              item.title === null ? "text-[var(--fg-3)] italic" : ""
            }`}
          >
            {item.title ?? "Новый чат"}
          </div>
        )}
      </div>

      {editing ? (
        <div className="flex-none flex items-center gap-0.5">
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              commit();
            }}
            className="p-0.5 rounded text-[var(--success)] hover:bg-[var(--bg-3)]"
            aria-label="Сохранить название"
          >
            <Check size={14} />
          </button>
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              cancel();
            }}
            className="p-0.5 rounded text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-3)]"
            aria-label="Отменить"
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <div
          className={`flex-none flex items-center gap-0.5 transition-opacity ${
            item.pinned ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          }`}
        >
          {onPin && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onPin(item.id, !item.pinned);
              }}
              className={`p-0.5 rounded hover:text-[var(--accent)] ${
                item.pinned ? "text-[var(--accent)]" : "text-[var(--fg-3)]"
              }`}
              aria-label={item.pinned ? "Открепить чат" : "Закрепить чат"}
              title={item.pinned ? "Открепить" : "Закрепить"}
            >
              <Pin size={13} className={item.pinned ? "fill-current" : ""} />
            </button>
          )}
          {onRename && (
            <button
              onClick={startEdit}
              className="p-0.5 rounded text-[var(--fg-3)] hover:text-[var(--fg-1)]"
              aria-label="Переименовать чат"
              title="Переименовать"
            >
              <Pencil size={13} />
            </button>
          )}
          <button
            onClick={handleDelete}
            className="p-0.5 rounded text-[var(--fg-3)] hover:text-[var(--error)]"
            aria-label="Удалить сессию"
          >
            <Trash2 size={14} />
          </button>
        </div>
      )}
    </Link>
  );
}

export function SessionList({ grouped, activeId, onDelete, onRename, onPin }: SessionListProps) {
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
      <GroupSection label="Сегодня" items={grouped.today} activeId={activeId} onDelete={onDelete} onRename={onRename} onPin={onPin} />
      <GroupSection label="Вчера" items={grouped.yesterday} activeId={activeId} onDelete={onDelete} onRename={onRename} onPin={onPin} />
      <GroupSection label="На этой неделе" items={grouped.this_week} activeId={activeId} onDelete={onDelete} onRename={onRename} onPin={onPin} />
      <GroupSection label="Раньше" items={grouped.earlier} activeId={activeId} onDelete={onDelete} onRename={onRename} onPin={onPin} />
    </div>
  );
}
