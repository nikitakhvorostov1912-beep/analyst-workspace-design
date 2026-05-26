"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  getBSPStatus,
  getITSStatus,
  type BSPStatusResponse,
  type ITSStatusResponse,
} from "@/lib/api";

/**
 * Хук для M-K2.11 «Local Knowledge» badge — fetches ИТС + БСП index status
 * параллельно. Polls раз в `pollIntervalMs` (default 30s — статус меняется
 * редко, только при /reload).
 *
 * Использование:
 * ```tsx
 * const { its, bsp, loading, error } = useKnowledgeStatus();
 * <KnowledgeBadge its={its} bsp={bsp} />
 * ```
 *
 * Графовая модель: оба запроса — best-effort. Если один упал, другой
 * всё равно возвращается (UI просто скроет недоступную часть).
 */
export interface UseKnowledgeStatusOptions {
  /** Интервал polling в миллисекундах. 0 = не опрашивать (только fetchOnMount). */
  pollIntervalMs?: number;
  /** Делать fetch сразу при mount. По умолчанию true. */
  fetchOnMount?: boolean;
}

export interface UseKnowledgeStatus {
  its: ITSStatusResponse | null;
  bsp: BSPStatusResponse | null;
  /** Любая из двух подсистем готова (enabled + ready). */
  anyReady: boolean;
  /** Обе подсистемы готовы. */
  bothReady: boolean;
  /** Total chunks/methods (для прогресс-индикатора). */
  totalEntries: number;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useKnowledgeStatus(
  options: UseKnowledgeStatusOptions = {},
): UseKnowledgeStatus {
  const pollMs = options.pollIntervalMs ?? 30_000;
  const fetchOnMount = options.fetchOnMount ?? true;

  const [its, setIts] = useState<ITSStatusResponse | null>(null);
  const [bsp, setBsp] = useState<BSPStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const cancelledRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchBoth = useCallback(async () => {
    // Settled — каждый запрос обрабатывается независимо
    const results = await Promise.allSettled([getITSStatus(), getBSPStatus()]);
    if (cancelledRef.current) return;
    const [itsResult, bspResult] = results;
    if (itsResult.status === "fulfilled") {
      setIts(itsResult.value);
    }
    if (bspResult.status === "fulfilled") {
      setBsp(bspResult.value);
    }
    // Ошибку показываем только если оба провалились
    if (itsResult.status === "rejected" && bspResult.status === "rejected") {
      const itsErr =
        itsResult.reason instanceof Error
          ? itsResult.reason.message
          : String(itsResult.reason);
      setError(itsErr);
    } else {
      setError(null);
    }
  }, []);

  useEffect(() => {
    cancelledRef.current = false;

    async function tick() {
      await fetchBoth();
      if (cancelledRef.current) return;
      if (pollMs > 0) {
        timerRef.current = setTimeout(tick, pollMs);
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
  }, [pollMs, fetchOnMount, fetchBoth]);

  const itsReady = Boolean(its?.enabled && its?.ready);
  const bspReady = Boolean(bsp?.enabled && bsp?.ready);
  const itsCount = its?.chunks ?? 0;
  const bspCount = bsp?.methods ?? 0;

  return {
    its,
    bsp,
    anyReady: itsReady || bspReady,
    bothReady: itsReady && bspReady,
    totalEntries: itsCount + bspCount,
    loading,
    error,
    refresh: fetchBoth,
  };
}
