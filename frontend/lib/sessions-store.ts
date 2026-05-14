"use client";

import { useCallback, useState } from "react";
import {
  createSession,
  deleteSession,
  fetchSessions,
} from "./api";
import type { SessionDetail, SessionListItem, SessionsGrouped } from "./types";

const EMPTY_GROUPED: SessionsGrouped = {
  today: [],
  yesterday: [],
  this_week: [],
  earlier: [],
};

export type SessionsState = {
  grouped: SessionsGrouped;
  loading: boolean;
  error: string | null;
  refresh: (channel_id?: string) => Promise<void>;
  createNew: (channel_id: string) => Promise<SessionDetail>;
  remove: (id: string) => Promise<void>;
  renameLocal: (id: string, title: string) => void;
};

/**
 * Простой hook управления списком сессий — без Zustand, через useState.
 * Каждый вызов имеет свой state (owner-component pattern).
 * Для MVP достаточно — Sidebar получает grouped через props от page.
 */
export function useSessionsStore(): SessionsState {
  const [grouped, setGrouped] = useState<SessionsGrouped>(EMPTY_GROUPED);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (channel_id?: string): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSessions(channel_id);
      setGrouped(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ошибка загрузки истории";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const createNew = useCallback(
    async (channel_id: string): Promise<SessionDetail> => {
      const detail = await createSession(channel_id);
      await refresh(channel_id);
      return detail;
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string): Promise<void> => {
      await deleteSession(id);
      // Оптимистично убираем из всех групп без roundtrip
      setGrouped((prev) => {
        const filterOut = (items: SessionListItem[]) =>
          items.filter((s) => s.id !== id);
        return {
          today: filterOut(prev.today),
          yesterday: filterOut(prev.yesterday),
          this_week: filterOut(prev.this_week),
          earlier: filterOut(prev.earlier),
        };
      });
    },
    [],
  );

  const renameLocal = useCallback((id: string, title: string): void => {
    const updateItem = (items: SessionListItem[]): SessionListItem[] =>
      items.map((s) => (s.id === id ? { ...s, title } : s));
    setGrouped((prev) => ({
      today: updateItem(prev.today),
      yesterday: updateItem(prev.yesterday),
      this_week: updateItem(prev.this_week),
      earlier: updateItem(prev.earlier),
    }));
  }, []);

  return { grouped, loading, error, refresh, createNew, remove, renameLocal };
}
