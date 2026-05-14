"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { publishToast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import type { LogCardPayload, LogEntry } from "@/lib/types";

type LogLevel = LogEntry["level"];

const LEVEL_CLASSES: Record<LogLevel, string> = {
  Info: "text-[var(--fg-muted)] bg-[var(--bg-elevated)] border-[var(--border)]",
  Warning: "text-yellow-300 bg-yellow-950 border-yellow-800",
  Error: "text-red-300 bg-red-950 border-red-800",
  Critical: "text-red-200 bg-red-900 border-red-700 font-semibold",
};

const LEVEL_ROW_CLASSES: Record<LogLevel, string> = {
  Info: "",
  Warning: "border-l-2 border-l-yellow-600",
  Error: "border-l-2 border-l-red-600",
  Critical: "border-l-2 border-l-red-400 bg-red-950/20",
};

function LogEntryRow({ entry }: { entry: LogEntry }) {
  const timeLabel = (() => {
    try {
      return new Date(entry.time).toLocaleString("ru-RU");
    } catch {
      return entry.time;
    }
  })();

  return (
    <div
      className={cn(
        "px-3 py-2 border-b border-[var(--border)] last:border-0",
        LEVEL_ROW_CLASSES[entry.level],
      )}
      data-level={entry.level}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          className={cn("text-xs border shrink-0", LEVEL_CLASSES[entry.level])}
          variant="outline"
        >
          {entry.level}
        </Badge>
        <span className="text-xs text-[var(--fg-muted)] tabular-nums whitespace-nowrap">
          {timeLabel}
        </span>
        {entry.user && (
          <span className="text-xs text-[var(--fg-muted)]">{entry.user}</span>
        )}
        <span className="text-xs font-mono text-[var(--fg)] break-all">
          {entry.event}
        </span>
      </div>
      {entry.comment && (
        <details className="mt-1">
          <summary className="text-xs text-[var(--fg-muted)] cursor-pointer select-none hover:text-[var(--fg)]">
            Комментарий
          </summary>
          <p className="text-xs text-[var(--fg)] mt-1 whitespace-pre-wrap break-words pl-2">
            {entry.comment}
          </p>
        </details>
      )}
    </div>
  );
}

interface LogCardProps {
  payload: LogCardPayload;
  /**
   * Вызывается при клике «Загрузить ещё» с cursor.
   * Должна вернуть Promise с {entries, next_cursor}.
   * При null next_cursor кнопка исчезает.
   */
  onLoadMore?: (cursor: string) => Promise<{ entries: LogEntry[]; next_cursor: string | null }>;
}

export function LogCard({ payload, onLoadMore }: LogCardProps) {
  const [extraEntries, setExtraEntries] = useState<LogEntry[]>([]);
  const [currentCursor, setCurrentCursor] = useState<string | null>(payload.next_cursor);
  const [loading, setLoading] = useState(false);

  const allEntries = [...payload.entries, ...extraEntries];

  async function handleLoadMore() {
    if (!currentCursor || !onLoadMore || loading) return;
    setLoading(true);
    try {
      const result = await onLoadMore(currentCursor);
      setExtraEntries((prev) => [...prev, ...result.entries]);
      setCurrentCursor(result.next_cursor);
    } catch {
      publishToast({ type: "error", message: "Не удалось загрузить следующую страницу" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] overflow-hidden">
      {/* Заголовок */}
      <div className="px-3 py-2 border-b border-[var(--border)]">
        <span className="text-xs text-[var(--fg-muted)]">
          Журнал регистрации · {allEntries.length}{" "}
          {allEntries.length === 1 ? "запись" : "записей"}
        </span>
      </div>

      {allEntries.length === 0 ? (
        <div className="px-3 py-6 text-xs text-[var(--fg-muted)] text-center">
          Записи отсутствуют
        </div>
      ) : (
        <ScrollArea className="max-h-[400px]">
          <div>
            {allEntries.map((entry, i) => (
              <LogEntryRow key={i} entry={entry} />
            ))}
          </div>
        </ScrollArea>
      )}

      {/* Кнопка загрузки следующей страницы */}
      {currentCursor !== null && (
        <div className="px-3 py-2 border-t border-[var(--border)]">
          {onLoadMore ? (
            <Button
              size="sm"
              variant="secondary"
              className="w-full text-xs"
              disabled={loading}
              onClick={() => { void handleLoadMore(); }}
            >
              {loading ? "Загрузка..." : "Загрузить ещё"}
            </Button>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              className="w-full text-xs"
              disabled
              title="Загрузка следующей страницы — Phase 3"
            >
              Загрузить ещё
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
