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
  /** Удалить с syncronous wait для backend. Если возможен undo — лучше removeOptimistic + commitRemove. */
  remove: (id: string) => Promise<void>;
  /** Sprint 02 A · UndoToast: убрать из UI без roundtrip — сохраняем в `pending` */
  removeOptimistic: (id: string) => void;
  /** Sprint 02 A · UndoToast: вернуть из pending (пользователь нажал «↺ Отменить») */
  restoreOptimistic: (id: string) => void;
  /** Sprint 02 A · UndoToast: реальный DELETE на backend, удаление из pending */
  commitRemove: (id: string) => Promise<void>;
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
  // Sprint 02 A · UndoToast: оптимистично удалённые сессии хранятся
  // в Map<id, item> на случай нажатия «↺ Отменить». commitRemove
  // вычистит этот Map после реального DELETE; restoreOptimistic вернёт
  // item обратно в `grouped`.
  const [pendingRemove, setPendingRemove] = useState<
    Map<string, { item: SessionListItem; group: keyof SessionsGrouped }>
  >(new Map());

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

  const removeOptimistic = useCallback((id: string): void => {
    setGrouped((prev) => {
      let saved: { item: SessionListItem; group: keyof SessionsGrouped } | null = null;
      const filterOut = (items: SessionListItem[], group: keyof SessionsGrouped) => {
        const found = items.find((s) => s.id === id);
        if (found && !saved) saved = { item: found, group };
        return items.filter((s) => s.id !== id);
      };
      const next: SessionsGrouped = {
        today: filterOut(prev.today, "today"),
        yesterday: filterOut(prev.yesterday, "yesterday"),
        this_week: filterOut(prev.this_week, "this_week"),
        earlier: filterOut(prev.earlier, "earlier"),
      };
      if (saved) {
        setPendingRemove((p) => {
          const m = new Map(p);
          m.set(id, saved!);
          return m;
        });
      }
      return next;
    });
  }, []);

  const restoreOptimistic = useCallback((id: string): void => {
    setPendingRemove((p) => {
      const saved = p.get(id);
      if (!saved) return p;
      // Вернуть item в его исходную группу. Сортировка нарушится по
      // updated_at — refresh() поправит при следующем заходе в UI.
      setGrouped((prev) => ({
        ...prev,
        [saved.group]: [saved.item, ...prev[saved.group]],
      }));
      const m = new Map(p);
      m.delete(id);
      return m;
    });
  }, []);

  const commitRemove = useCallback(async (id: string): Promise<void> => {
    try {
      await deleteSession(id);
    } catch (err) {
      // Backend упал — откатываем оптимистичное удаление, возвращаем item.
      const msg = err instanceof Error ? err.message : "Не удалось удалить чат";
      setError(msg);
      restoreOptimistic(id);
      throw err;
    }
    setPendingRemove((p) => {
      const m = new Map(p);
      m.delete(id);
      return m;
    });
  }, [restoreOptimistic]);

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

  // Игнорируем pendingRemove в публичном API возврата — он используется
  // только внутри callbacks restoreOptimistic / commitRemove.
  void pendingRemove;

  return {
    grouped,
    loading,
    error,
    refresh,
    createNew,
    remove,
    removeOptimistic,
    restoreOptimistic,
    commitRemove,
    renameLocal,
  };
}
