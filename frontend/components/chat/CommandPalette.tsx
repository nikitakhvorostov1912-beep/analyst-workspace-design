"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { searchMessages } from "@/lib/api";
import type { SearchResultItem } from "@/lib/types";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  channelId?: string;
}

/** Получить отображение hotkey по платформе */
function getHotkeyLabel(): string {
  if (typeof navigator === "undefined") return "Ctrl+K";
  // navigator.platform deprecated но широко поддерживается
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const navAny = navigator as any;
  const isMac =
    navigator.platform.includes("Mac") ||
    ((navAny.userAgentData?.platform ?? "") as string).includes("macOS");
  return isMac ? "Cmd+K" : "Ctrl+K";
}

/**
 * Безопасная вставка HTML snippet — экранирует всё кроме тегов <mark> и </mark>.
 * XSS-защита: T-04-18.
 */
function sanitizeSnippet(raw: string): string {
  // Сначала экранируем весь HTML
  const escaped = raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  // Затем восстанавливаем только <mark> и </mark>
  return escaped.replace(/&lt;mark&gt;/g, "<mark>").replace(/&lt;\/mark&gt;/g, "</mark>");
}

/**
 * Command Palette — modal dialog с поиском по сессиям и messages.
 * Открывается по Cmd+K (Mac) / Ctrl+K (Win). Закрывается Escape или blur.
 * Результаты: click → navigate /sessions/{id}#message-{mid}.
 */
export function CommandPalette({ open, onClose, channelId }: CommandPaletteProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [hotkeyLabel] = useState(getHotkeyLabel);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Фокус при открытии
  useEffect(() => {
    if (open) {
      setQuery("");
      setResults([]);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Fetch с debounce 250ms
  useEffect(() => {
    if (!open || query.length < 2) {
      setResults([]);
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const resp = await searchMessages(query, channelId);
        setResults(resp.results);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, channelId, open]);

  // Escape → close
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  function handleResultClick(item: SearchResultItem) {
    router.push(`/sessions/${item.session_id}#message-${item.message_id}`);
    onClose();
  }

  if (!open) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Поиск по сессиям и сообщениям"
        className="fixed left-1/2 top-[20%] z-50 w-full max-w-lg -translate-x-1/2 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] shadow-xl overflow-hidden"
      >
        {/* Input */}
        <div className="flex items-center border-b border-[var(--border)] px-3 gap-2">
          <svg
            className="w-4 h-4 text-[var(--fg-muted)] shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            ref={inputRef}
            type="text"
            placeholder="Поиск по сессиям и сообщениям..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 h-12 bg-transparent text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] outline-none"
          />
          <kbd className="text-xs text-[var(--fg-muted)] border border-[var(--border)] rounded px-1.5 py-0.5 font-mono">
            {hotkeyLabel}
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[400px] overflow-y-auto">
          {loading && (
            <div className="px-4 py-3 text-sm text-[var(--fg-muted)]">Поиск...</div>
          )}

          {!loading && query.length >= 2 && results.length === 0 && (
            <div className="px-4 py-3 text-sm text-[var(--fg-muted)]">
              Ничего не найдено по запросу «{query}»
            </div>
          )}

          {!loading && query.length < 2 && (
            <div className="px-4 py-3 text-sm text-[var(--fg-muted)]">
              Введите минимум 2 символа для поиска
            </div>
          )}

          {results.map((item) => (
            <button
              key={`${item.session_id}-${item.message_id}`}
              type="button"
              onClick={() => handleResultClick(item)}
              className="w-full text-left px-4 py-2.5 hover:bg-[var(--border)] transition-colors border-b border-[var(--border)] last:border-0"
            >
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs text-[var(--fg-muted)] truncate">
                  {item.session_title ?? "Без заголовка"}
                </span>
                <span className="text-xs text-[var(--fg-muted)] ml-auto shrink-0">
                  {item.created_at.slice(0, 10)}
                </span>
              </div>
              <p
                className="text-sm text-[var(--fg)] line-clamp-2 [&_mark]:bg-yellow-400/30 [&_mark]:text-[var(--fg)] [&_mark]:rounded-sm"
                // eslint-disable-next-line react/no-danger
                dangerouslySetInnerHTML={{ __html: sanitizeSnippet(item.snippet) }}
              />
            </button>
          ))}
        </div>
      </div>
    </>
  );
}
