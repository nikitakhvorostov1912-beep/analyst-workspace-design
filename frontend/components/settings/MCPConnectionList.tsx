"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { MCPConnectionForm } from "./MCPConnectionForm";
import { deleteConnection, fetchConnections, pingConnection } from "@/lib/api";
import { publishToast } from "@/lib/toast";
import type { MCPConnection } from "@/lib/types";

interface MCPConnectionListProps {
  initialConnections: MCPConnection[];
  onChanged?: () => void;
}

export function MCPConnectionList({
  initialConnections,
  onChanged,
}: MCPConnectionListProps) {
  const [connections, setConnections] =
    useState<MCPConnection[]>(initialConnections);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [addingNew, setAddingNew] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [pingingId, setPingingId] = useState<string | null>(null);

  async function reload() {
    try {
      const updated = await fetchConnections();
      setConnections(updated);
      onChanged?.();
    } catch {
      // keep current state
    }
  }

  async function handlePing(id: string) {
    setPingingId(id);
    try {
      const result = await pingConnection(id);
      publishToast({
        type: "info",
        message: `MCP работает: ${result.tool_count} инструментов, ${result.duration_ms}мс`,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка пинга";
      publishToast({ type: "error", message });
    } finally {
      setPingingId(null);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteConnection(id);
      publishToast({ type: "info", message: "Подключение удалено" });
      await reload();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка удаления";
      publishToast({ type: "error", message });
    } finally {
      setDeleteId(null);
    }
  }

  const deleteTarget = connections.find((c) => c.id === deleteId);

  return (
    <div className="space-y-3">
      {connections.length === 0 && !addingNew ? (
        <p className="text-sm text-[var(--fg-muted)]">
          Подключения не настроены
        </p>
      ) : (
        <div className="space-y-2">
          {connections.map((conn) =>
            editingId === conn.id ? (
              <MCPConnectionForm
                key={conn.id}
                initial={conn}
                onSaved={() => {
                  reload();
                  setEditingId(null);
                }}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <div
                key={conn.id}
                className="flex items-center justify-between gap-3 p-3 border border-[var(--border)] rounded-md"
              >
                <div className="min-w-0 flex-1">
                  <span className="text-sm font-medium text-[var(--fg)]">
                    {conn.name}
                  </span>
                  {conn.channel && (
                    <span className="text-xs text-[var(--fg-muted)] ml-1">
                      ({conn.channel})
                    </span>
                  )}
                  <p className="text-xs text-[var(--fg-muted)] font-mono truncate">
                    {conn.endpoint}
                  </p>
                </div>
                <div className="flex items-center gap-1 flex-none">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handlePing(conn.id)}
                    disabled={pingingId === conn.id}
                  >
                    {pingingId === conn.id ? "..." : "Тест"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditingId(conn.id)}
                  >
                    Изменить
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-400 hover:text-red-300"
                    onClick={() => setDeleteId(conn.id)}
                  >
                    Удалить
                  </Button>
                </div>
              </div>
            ),
          )}
        </div>
      )}

      {addingNew && (
        <MCPConnectionForm
          onSaved={() => {
            reload();
            setAddingNew(false);
          }}
          onCancel={() => setAddingNew(false)}
        />
      )}

      {!addingNew && (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setAddingNew(true)}
        >
          + Добавить подключение
        </Button>
      )}

      <AlertDialog open={deleteId !== null}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить подключение?</AlertDialogTitle>
            <AlertDialogDescription>
              Удалить подключение &laquo;{deleteTarget?.name}&raquo;? Это
              действие нельзя отменить.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setDeleteId(null)}>
              Отмена
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-800 hover:bg-red-700"
              onClick={() => deleteId && handleDelete(deleteId)}
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
