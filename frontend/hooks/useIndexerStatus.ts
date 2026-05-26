"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  getIndexerStatus,
  startIndexer,
  type IndexerStatusResponse,
  type IndexRun,
} from "@/lib/api";

/**
 * Hook для M-K2.10 «Изучаю вашу базу» — управляет жизненным циклом
 * indexing run'а одного канала:
 *
 * 1. Polling GET /knowledge/{ch}/index/status каждые `pollIntervalMs`
 *    пока есть `running` run. Когда running исчезает — polling замедляется
 *    до `idlePollIntervalMs` (или 0 = stop).
 * 2. `start()` вызывает POST /index/start. На 409 берём `running` из
 *    response.detail (через error.cause) и сразу обновляем state.
 * 3. На любую ошибку — пишем в `error`, прекращаем running polling.
 *
 * Использование:
 * ```tsx
 * const { status, isRunning, start, error } = useIndexerStatus(channelId);
 * <button onClick={start} disabled={isRunning}>Изучить базу</button>
 * ```
 */
export interface UseIndexerStatusOptions {
  /** Опрашивать каждые N миллисекунд пока running. По умолчанию 1500. */
  pollIntervalMs?: number;
  /**
   * Опрашивать каждые N миллисекунд когда idle (нет running).
   * 0 = не опрашивать. По умолчанию 0 (экономим запросы).
   */
  idlePollIntervalMs?: number;
  /**
   * Если true — first status fetch выполняется сразу при mount.
   * По умолчанию true.
   */
  fetchOnMount?: boolean;
}

export interface UseIndexerStatus {
  /** Полный ответ GET /index/status. null до первого успешного запроса. */
  status: IndexerStatusResponse | null;
  /** Удобный shorthand: status.running !== null. */
  isRunning: boolean;
  /** Последний завершённый run (любой статус), для отображения «было N объектов». */
  latest: IndexRun | null;
  /** Текущий running run, для прогресс-индикатора. */
  running: IndexRun | null;
  /** Ошибка последнего HTTP-запроса (start или status). null если всё ОК. */
  error: string | null;
  /** True пока идёт первый fetchOnMount запрос. */
  loading: boolean;
  /** POST /index/start. Throws при ошибке (handler пишет в `error`). */
  start: () => Promise<void>;
  /** Принудительный refetch статуса (например на focus окна). */
  refresh: () => Promise<void>;
}

export function useIndexerStatus(
  channelId: string | null | undefined,
  options: UseIndexerStatusOptions = {},
): UseIndexerStatus {
  const pollMs = options.pollIntervalMs ?? 1500;
  const idleMs = options.idlePollIntervalMs ?? 0;
  const fetchOnMount = options.fetchOnMount ?? true;

  const [status, setStatus] = useState<IndexerStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Stable ref для cleanup внутри useEffect без зависимости от status в DEPS
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  const fetchStatus = useCallback(async () => {
    if (!channelId) return null;
    try {
      const next = await getIndexerStatus(channelId);
      if (cancelledRef.current) return null;
      setStatus(next);
      setError(null);
      return next;
    } catch (e) {
      if (cancelledRef.current) return null;
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, [channelId]);

  // Polling loop — replanируется каждый раз исходя из running состояния
  useEffect(() => {
    if (!channelId) return;
    cancelledRef.current = false;

    async function tick() {
      const next = await fetchStatus();
      if (cancelledRef.current) return;
      const isStillRunning = next?.running != null;
      const nextDelay = isStillRunning ? pollMs : idleMs;
      if (nextDelay > 0) {
        timerRef.current = setTimeout(tick, nextDelay);
      }
    }

    if (fetchOnMount) {
      setLoading(true);
      tick().finally(() => {
        if (!cancelledRef.current) setLoading(false);
      });
    }

    return () => {
      cancelledRef.current = true;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [channelId, pollMs, idleMs, fetchOnMount, fetchStatus]);

  const start = useCallback(async () => {
    if (!channelId) {
      setError("Канал не выбран");
      return;
    }
    setError(null);
    try {
      const resp = await startIndexer(channelId);
      // Сразу подмешиваем «running» в state — модалка покажет прогресс
      // не дожидаясь следующего poll tick'а.
      setStatus((prev) => ({
        channel_id: channelId,
        latest: prev?.latest ?? null,
        running: {
          id: resp.run_id,
          channel_id: channelId,
          status: "running",
          started_at: resp.started_at,
          finished_at: null,
          duration_ms: null,
          objects_total: 0,
          objects_written: 0,
          objects_skipped: 0,
          error: null,
        },
      }));
      // Перепланируем polling tick — useEffect его обнаружит через state
      // change. Если polling отключён (pollMs=0) — не планируем.
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      if (pollMs > 0) {
        timerRef.current = setTimeout(async function tick() {
          const cur = await fetchStatus();
          if (cur?.running != null && !cancelledRef.current && pollMs > 0) {
            timerRef.current = setTimeout(tick, pollMs);
          }
        }, pollMs);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      // 409 cause содержит current_run — подставляем в state чтобы UI
      // показал прогресс «уже запущенного» процесса.
      const cause = (e as Error & { cause?: unknown }).cause;
      if (cause && typeof cause === "object" && "status" in cause) {
        const running = cause as IndexRun;
        setStatus({
          channel_id: channelId,
          latest: status?.latest ?? null,
          running,
        });
      }
      setError(msg);
      throw e;
    }
  }, [channelId, fetchStatus, pollMs, status?.latest]);

  return {
    status,
    isRunning: status?.running != null,
    latest: status?.latest ?? null,
    running: status?.running ?? null,
    error,
    loading,
    start,
    refresh: async () => {
      await fetchStatus();
    },
  };
}
