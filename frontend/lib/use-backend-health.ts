"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchHealth } from "./api";
import type { HealthResponse } from "./types";

export type BackendStatus = "loading" | "ok" | "unavailable";

interface BackendHealthState {
  status: BackendStatus;
  info: HealthResponse | null;
  /** Принудительно перепроверить health — используется в BackendDownBanner */
  retry: () => Promise<void>;
}

/**
 * Sprint 03 (handoff F · BackendDownBanner): hook для отслеживания
 * доступности серверной части.
 *
 * Раньше каждый компонент сам дергал `fetchHealth` — теперь единая точка.
 * `retry()` используется кнопкой «Повторить» в BackendDownBanner.
 *
 * NOTE: не делаем глобальный store с подпиской — для текущих масштабов
 * useState внутри hook'а достаточно. AppShell владеет одним экземпляром
 * и пробрасывает status в Banner / BackendIndicator.
 */
export function useBackendHealth(): BackendHealthState {
  const [status, setStatus] = useState<BackendStatus>("loading");
  const [info, setInfo] = useState<HealthResponse | null>(null);

  const probe = useCallback(async () => {
    try {
      const data = await fetchHealth();
      setInfo(data);
      setStatus("ok");
    } catch {
      setInfo(null);
      setStatus("unavailable");
    }
  }, []);

  useEffect(() => {
    void probe();
  }, [probe]);

  const retry = useCallback(async () => {
    setStatus("loading");
    await probe();
  }, [probe]);

  return { status, info, retry };
}
