"use client";

import { useEffect, useRef, useState } from "react";
import { metadataSuggest } from "@/lib/api";
import type { MetadataSuggestItem } from "@/lib/types";

interface MentionPopoverProps {
  open: boolean;
  query: string;
  channelId: string;
  onSelect: (item: MetadataSuggestItem) => void;
  anchor: React.RefObject<HTMLElement | null>;
}

/**
 * Popover с объектами метаданных 1С при typing «@» в textarea.
 * Загружает данные из /connections/{channelId}/metadata-suggest с debounce 200ms.
 * Поддерживает keyboard nav ArrowUp/Down + Enter.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function MentionPopover({ open, query, channelId, onSelect, anchor: _anchor }: MentionPopoverProps) {
  const [items, setItems] = useState<MetadataSuggestItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [stale, setStale] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch с debounce 200ms при изменении query
  useEffect(() => {
    if (!open || !channelId || query.length < 1) {
      setItems([]);
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const resp = await metadataSuggest(channelId, query);
        setItems(resp.items);
        setStale(resp.stale);
      } catch {
        setItems([]);
      } finally {
        setLoading(false);
      }
    }, 200);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [open, query, channelId]);

  // Сбрасываем активный индекс при изменении items
  useEffect(() => {
    setActiveIdx(0);
  }, [items]);

  // Keyboard navigation
  useEffect(() => {
    if (!open) return;

    function handleKey(e: KeyboardEvent) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, items.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (items[activeIdx]) {
          onSelect(items[activeIdx]);
        }
      }
    }

    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, items, activeIdx, onSelect]);

  if (!open) return null;

  return (
    <div
      role="listbox"
      aria-label="Объекты метаданных"
      className="absolute bottom-full left-0 right-0 z-50 mb-1 mx-3 rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] shadow-md overflow-hidden max-h-[240px] overflow-y-auto"
    >
      {/* Заголовок с индикатором stale */}
      <div className="flex items-center justify-between px-3 py-1 border-b border-[var(--border)] bg-[var(--bg)]">
        <span className="text-xs text-[var(--fg-muted)]">Объекты 1С</span>
        {stale && (
          <span className="text-xs text-amber-400 border border-amber-700 rounded px-1">
            устаревший кеш
          </span>
        )}
      </div>

      {loading && (
        <div className="px-3 py-2 text-sm text-[var(--fg-muted)]">Загрузка...</div>
      )}

      {!loading && items.length === 0 && (
        <div className="px-3 py-2 text-sm text-[var(--fg-muted)]">Ничего не найдено</div>
      )}

      {!loading &&
        items.map((item, idx) => (
          <div
            key={item.full_path}
            role="option"
            aria-selected={idx === activeIdx}
            onClick={() => onSelect(item)}
            onMouseEnter={() => setActiveIdx(idx)}
            className={`flex items-center gap-2 px-3 py-1.5 cursor-pointer text-sm transition-colors ${
              idx === activeIdx
                ? "bg-[var(--border)] text-[var(--fg)]"
                : "text-[var(--fg-muted)]"
            }`}
          >
            <span className="text-xs px-1 py-0.5 rounded bg-[var(--bg)] border border-[var(--border)] text-[var(--fg-muted)] shrink-0">
              {item.object_type}
            </span>
            <span className="font-medium text-[var(--fg)]">{item.name}</span>
            {item.presentation && (
              <span className="text-xs text-[var(--fg-muted)] truncate">
                {item.presentation}
              </span>
            )}
          </div>
        ))}
    </div>
  );
}
