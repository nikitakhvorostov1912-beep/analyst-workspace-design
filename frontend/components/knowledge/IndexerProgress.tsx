"use client";

import { BookOpenCheck, Loader2, RefreshCw, AlertTriangle, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StencilChip } from "@/components/ui/StencilChip";
import { useIndexerStatus } from "@/hooks/useIndexerStatus";

interface IndexerProgressProps {
  channelId: string;
  /** Компактный режим — только chip без кнопки и подписи. */
  compact?: boolean;
  className?: string;
}

function formatDuration(ms: number | null | undefined): string {
  if (!ms || ms < 0) return "—";
  if (ms < 1000) return `${ms} мс`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)} с`;
  const min = Math.floor(sec / 60);
  const remSec = Math.round(sec - min * 60);
  return `${min} мин ${remSec.toString().padStart(2, "0")} с`;
}

function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const diffSec = (Date.now() - date.getTime()) / 1000;
  if (diffSec < 60) return "только что";
  if (diffSec < 3600) {
    const min = Math.floor(diffSec / 60);
    return `${min} мин назад`;
  }
  if (diffSec < 86400) {
    const hours = Math.floor(diffSec / 3600);
    return `${hours} ч назад`;
  }
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/**
 * M-K2.10: индикатор состояния indexer'а канала + кнопка «Изучить базу».
 *
 * Стек состояний:
 *   - idle (нет latest, нет running) → кнопка «Изучить базу»
 *   - running → chip с анимированным spinner'ом + «обрабатывается N объектов»
 *   - done → chip success «N объектов · M секунд назад» + кнопка обновить
 *   - failed → chip error с сообщением + кнопка retry
 *
 * При compact=true рендерится только chip (без кнопок и подписей) —
 * для встраивания в ChannelSelector dropdown.
 */
export function IndexerProgress({
  channelId,
  compact = false,
  className,
}: IndexerProgressProps) {
  const { running, latest, isRunning, error, loading, start } = useIndexerStatus(
    channelId,
    {
      pollIntervalMs: 1500,
      idlePollIntervalMs: 0,
      fetchOnMount: true,
    },
  );

  // 1) RUNNING — самый высокий приоритет
  if (isRunning && running) {
    const chip = (
      <StencilChip tone="signal" data-testid="indexer-chip-running" className={className}>
        <Loader2 className="h-3 w-3 animate-spin" />
        Индексирую {running.objects_written > 0 ? `· ${running.objects_written}` : "…"}
      </StencilChip>
    );
    if (compact) return chip;
    return (
      <div className="flex items-center gap-2">
        {chip}
        <span className="text-xs text-[var(--fg-3)]">
          Прогресс обновляется каждые 1.5 с
        </span>
      </div>
    );
  }

  // 2) FAILED — последний run закончился ошибкой
  if (latest && latest.status === "failed") {
    const chip = (
      <StencilChip tone="error" title={latest.error ?? undefined} data-testid="indexer-chip-failed" className={className}>
        <AlertTriangle className="h-3 w-3" />
        Ошибка индексации
      </StencilChip>
    );
    if (compact) return chip;
    return (
      <div className="flex items-center gap-2 flex-wrap">
        {chip}
        <span className="text-xs text-[var(--error)] max-w-[280px] truncate" title={latest.error ?? undefined}>
          {latest.error ?? "Подробности неизвестны"}
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => { void start().catch(() => undefined); }}
          className="h-7 text-xs gap-1"
          data-testid="indexer-retry-button"
        >
          <RefreshCw className="h-3 w-3" />
          Повторить
        </Button>
      </div>
    );
  }

  // 3) DONE — успешный последний run
  if (latest && latest.status === "done") {
    const chip = (
      <StencilChip tone="success" data-testid="indexer-chip-done" className={className}>
        <Check className="h-3 w-3" />
        {latest.objects_written} объектов
      </StencilChip>
    );
    if (compact) return chip;
    return (
      <div className="flex items-center gap-2 flex-wrap">
        {chip}
        <span className="text-xs text-[var(--fg-3)]">
          {formatRelativeTime(latest.finished_at)} · {formatDuration(latest.duration_ms)}
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => { void start().catch(() => undefined); }}
          className="h-7 text-xs gap-1"
          data-testid="indexer-refresh-button"
        >
          <RefreshCw className="h-3 w-3" />
          Переиндексировать
        </Button>
      </div>
    );
  }

  // 4) IDLE — ни одного run не было (или ещё загружается)
  if (loading) {
    if (compact) {
      return (
        <StencilChip tone="muted" className={className} data-testid="indexer-chip-loading">
          <Loader2 className="h-3 w-3 animate-spin" />
          …
        </StencilChip>
      );
    }
    return (
      <div className="text-xs text-[var(--fg-3)] inline-flex items-center gap-1.5">
        <Loader2 className="h-3 w-3 animate-spin" />
        Загружаю статус…
      </div>
    );
  }

  if (compact) {
    return (
      <Button
        size="sm"
        variant="ghost"
        onClick={() => { void start().catch(() => undefined); }}
        className="h-6 px-2 text-[10px] gap-1 uppercase tracking-[0.16em] font-mono"
        data-testid="indexer-start-button-compact"
      >
        <BookOpenCheck className="h-3 w-3" />
        Изучить
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Button
        size="sm"
        variant="secondary"
        onClick={() => { void start().catch(() => undefined); }}
        className="h-7 text-xs gap-1"
        data-testid="indexer-start-button"
      >
        <BookOpenCheck className="h-3 w-3" />
        Изучить базу
      </Button>
      <span className="text-xs text-[var(--fg-3)]">
        Загрузит структуру метаданных в локальный кеш (≈ 1–10 минут)
      </span>
      {error && (
        <span className="text-xs text-[var(--error)] truncate max-w-[280px]" title={error}>
          {error}
        </span>
      )}
    </div>
  );
}
