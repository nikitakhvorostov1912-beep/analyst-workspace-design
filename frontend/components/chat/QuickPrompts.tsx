"use client";

import { DEFAULT_QUICK_PROMPTS } from "@/lib/quick-prompts";

interface QuickPromptsProps {
  onSelect: (prompt: string) => void;
  hidden?: boolean;
}

/**
 * 5 chip-кнопок с дефолтными промптами — показываются над Input когда textarea пустая.
 * Click chip → onSelect(prompt) → textarea заполняется текстом.
 */
export function QuickPrompts({ onSelect, hidden }: QuickPromptsProps) {
  if (hidden) return null;

  return (
    <div
      className="flex flex-wrap gap-1.5 px-3 pt-1 pb-0"
      role="group"
      aria-label="Быстрые подсказки"
    >
      {DEFAULT_QUICK_PROMPTS.map((prompt) => {
        // Короткое отображаемое имя — первые ~25 символов до первого тире/запятой
        const displayName = (prompt.split(/[—,]/)[0] ?? prompt).trim();

        return (
          <button
            key={prompt}
            type="button"
            onClick={() => onSelect(prompt)}
            aria-label={`Быстрая подсказка: ${displayName}`}
            className="inline-flex items-center rounded-full border border-[var(--border)] bg-transparent px-2.5 py-0.5 text-xs text-[var(--fg-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--fg)] transition-colors"
          >
            {displayName}
          </button>
        );
      })}
    </div>
  );
}
