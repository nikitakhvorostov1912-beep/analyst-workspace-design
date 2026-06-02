"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  fetchHealth,
  fetchTypicalConfigurations,
  getITSStatus,
  getBSPStatus,
  pingConnection,
  type ITSStatusResponse,
  type BSPStatusResponse,
} from "@/lib/api";
import { getActiveChannelId } from "@/lib/storage";

/**
 * Статус «3 источников знаний» для header-бейджа и /status.
 *
 * Продукт грунтит ответы из трёх источников — пользователь должен видеть,
 * какой из них жив:
 *   1. База      — активное MCP-подключение к живой 1С (ping).
 *   2. Типовая   — граф + карточки типовых конфигураций (pilot.db).
 *   3. ИТС        — живой 1С:Напарник (buddy) ИЛИ статический RAG как fallback.
 *
 * Все запросы best-effort и независимы (Promise.allSettled) — падение одного
 * не гасит остальные. Поллинг по умолчанию 60s (статус меняется редко;
 * ping живой базы не хочется дёргать чаще).
 */

export type SourceState = "ready" | "down" | "unknown" | "disabled";

export interface SourceInfo {
  state: SourceState;
  /** Короткая строка для попапа: «4 конфигурации · 63 207 карточек». */
  detail: string;
}

export interface UseSourcesStatus {
  base: SourceInfo;
  typical: SourceInfo;
  its: SourceInfo;
  /** Сырые статические индексы — для детального попапа (ИТС-стандарты/БСП). */
  itsStatic: ITSStatusResponse | null;
  bspStatic: BSPStatusResponse | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

const UNKNOWN: SourceInfo = { state: "unknown", detail: "проверяю…" };

export function useSourcesStatus(pollIntervalMs = 60_000): UseSourcesStatus {
  const [base, setBase] = useState<SourceInfo>(UNKNOWN);
  const [typical, setTypical] = useState<SourceInfo>(UNKNOWN);
  const [its, setIts] = useState<SourceInfo>(UNKNOWN);
  const [itsStatic, setItsStatic] = useState<ITSStatusResponse | null>(null);
  const [bspStatic, setBspStatic] = useState<BSPStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const cancelled = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchAll = useCallback(async () => {
    const activeId = getActiveChannelId();

    const [healthR, typicalR, itsR, bspR, baseR] = await Promise.allSettled([
      fetchHealth(),
      fetchTypicalConfigurations(),
      getITSStatus(),
      getBSPStatus(),
      activeId ? pingConnection(activeId) : Promise.reject(new Error("no-active")),
    ]);

    if (cancelled.current) return;

    // --- База: ping активного подключения ---
    if (!activeId) {
      setBase({ state: "unknown", detail: "база не выбрана" });
    } else if (baseR.status === "fulfilled") {
      const tools = baseR.value?.tool_count ?? 0;
      setBase({ state: "ready", detail: `подключение живо · ${tools} инструментов` });
    } else {
      setBase({ state: "down", detail: "нет связи с 1С — проверьте обработку MCP" });
    }

    // --- Типовая: граф + карточки ---
    if (typicalR.status === "fulfilled") {
      const configs = typicalR.value.configurations ?? [];
      const count = configs.length;
      const cards = configs.reduce(
        (sum, c) => sum + (c.total_cards ?? c.card_counts?.generated ?? 0),
        0,
      );
      if (count > 0) {
        setTypical({
          state: "ready",
          detail: `${count} конфигурации · ${cards.toLocaleString("ru-RU")} карточек`,
        });
      } else {
        setTypical({ state: "down", detail: "типовые не загружены" });
      }
    } else {
      setTypical({ state: "unknown", detail: "не удалось получить статус" });
    }

    // --- Статические индексы (для детального попапа) ---
    const itsStaticVal = itsR.status === "fulfilled" ? itsR.value : null;
    const bspStaticVal = bspR.status === "fulfilled" ? bspR.value : null;
    setItsStatic(itsStaticVal);
    setBspStatic(bspStaticVal);

    // --- ИТС: живой Напарник (buddy) — primary; статика — fallback ---
    const buddy = healthR.status === "fulfilled" ? healthR.value.buddy : null;
    if (buddy?.enabled) {
      if (buddy.status === "up") {
        setIts({ state: "ready", detail: "Напарник на связи · живая ИТС" });
      } else if (buddy.status === "down") {
        // Напарник упал — но возможно есть статический RAG как запасной
        if (itsStaticVal?.ready) {
          setIts({ state: "ready", detail: "Напарник недоступен · работает локальный RAG" });
        } else {
          setIts({ state: "down", detail: "Напарник недоступен — запустите 1c-buddy :6002" });
        }
      } else {
        setIts({ state: "unknown", detail: "проверяю Напарника…" });
      }
    } else if (itsStaticVal?.ready) {
      setIts({ state: "ready", detail: "локальный RAG ИТС (Напарник выключен)" });
    } else {
      setIts({ state: "disabled", detail: "ИТС не подключён" });
    }
  }, []);

  useEffect(() => {
    cancelled.current = false;
    async function tick() {
      try {
        await fetchAll();
      } finally {
        if (!cancelled.current) setLoading(false);
      }
      if (cancelled.current) return;
      if (pollIntervalMs > 0) timer.current = setTimeout(tick, pollIntervalMs);
    }
    void tick();
    return () => {
      cancelled.current = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [fetchAll, pollIntervalMs]);

  return { base, typical, its, itsStatic, bspStatic, loading, refresh: fetchAll };
}
