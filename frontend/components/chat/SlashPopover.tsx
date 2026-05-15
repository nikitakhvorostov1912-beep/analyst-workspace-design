"use client";

import { useEffect, useState } from "react";
import { SLASH_COMMANDS, type SlashCommand } from "@/lib/slash-commands";

interface SlashPopoverProps {
  open: boolean;
  query: string;
  onSelect: (cmd: SlashCommand) => void;
  anchor: React.RefObject<HTMLElement | null>;
}

/**
 * Popover-список slash-команд, появляющийся при typing «/» в textarea.
 * Поддерживает навигацию клавишами ArrowUp/Down + Enter.
 * Escape закрывается через родительский компонент (onSelect не вызывается).
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function SlashPopover({ open, query, onSelect, anchor: _anchor }: SlashPopoverProps) {
  const [activeIdx, setActiveIdx] = useState(0);

  // Фильтруем команды по query (поиск в label и description)
  const filtered = SLASH_COMMANDS.filter(
    (cmd) =>
      cmd.label.includes(query) ||
      cmd.description.toLowerCase().includes(query.toLowerCase()),
  );

  // Сбрасываем активный индекс при изменении фильтра
  useEffect(() => {
    setActiveIdx(0);
  }, [query]);

  // Глобальный обработчик клавиш (пока popover открыт)
  useEffect(() => {
    if (!open) return;

    function handleKey(e: KeyboardEvent) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filtered[activeIdx]) {
          onSelect(filtered[activeIdx]);
        }
      }
    }

    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, filtered, activeIdx, onSelect]);

  if (!open || filtered.length === 0) return null;

  return (
    <div
      role="listbox"
      aria-label="Slash команды"
      className="absolute bottom-full left-0 right-0 z-50 mb-1 mx-3 rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] shadow-md overflow-hidden"
    >
      {filtered.map((cmd, idx) => (
        <div
          key={cmd.key}
          role="option"
          aria-selected={idx === activeIdx}
          onClick={() => onSelect(cmd)}
          onMouseEnter={() => setActiveIdx(idx)}
          className={`flex items-center gap-3 px-3 py-2 cursor-pointer text-sm transition-colors ${
            idx === activeIdx
              ? "bg-[var(--border)] text-[var(--fg)]"
              : "text-[var(--fg-muted)]"
          }`}
        >
          <span className="font-mono font-medium text-[var(--accent)] min-w-[60px]">
            {cmd.label}
          </span>
          <span className="flex-1 text-[var(--fg)]">{cmd.description}</span>
          {cmd.argsPlaceholder && (
            <span className="text-xs text-[var(--fg-muted)] font-mono">
              {cmd.argsPlaceholder}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
