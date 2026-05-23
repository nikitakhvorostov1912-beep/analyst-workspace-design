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
import { KindBadge } from "@/components/shell/KindBadge";
import { deleteConnection, fetchConnections, pingConnection } from "@/lib/api";
import { publishToast } from "@/lib/toast";
import type { MCPConnection } from "@/lib/types";

interface MCPConnectionListProps {
  initialConnections: MCPConnection[];
  onChanged?: () => void;
}

/** Короткое описание подключения без технического URL — рядом с KindBadge.
 *  embedded → `:6010` (mono); proxy с каналом → `канал «X»`; proxy без — `—`. */
function ConnectionSummary({ conn }: { conn: MCPConnection }) {
  if (conn.kind === "proxy") {
    if (!conn.channel) return null;
    return (
      <>
        канал <span className="font-mono">«{conn.channel}»</span>
      </>
    );
  }
  try {
    const u = new URL(conn.endpoint);
    const port = u.port || (u.protocol === "https:" ? "443" : "80");
    return <span className="font-mono">:{port}</span>;
  } catch {
    return null;
  }
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
    const conn = connections.find((c) => c.id === id);
    try {
      const result = await pingConnection(id);
      publishToast({
        type: "info",
        message: `База 1С отвечает · ${result.tool_count} инструментов · ${result.duration_ms} мс`,
      });
    } catch (err) {
      const detail = err instanceof Error ? err.message : "не отвечает";
      // Достаём порт из endpoint чтобы аналитик сразу увидел куда мы пытались
      // подключиться (типичная ошибка — порт в 1С отличается от настроенного).
      let portHint = "";
      try {
        if (conn) {
          const u = new URL(conn.endpoint);
          portHint = u.port ? ` (порт :${u.port})` : "";
        }
      } catch {
        /* malformed url */
      }
      publishToast({
        type: "error",
        message: `База «${conn?.name ?? "?"}» не отвечает${portHint}. Проверьте что в 1С запущен встроенный сервер обработки 1С на том же порту. ${detail}`,
      });
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
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium text-[var(--fg)]">
                      {conn.name}
                    </span>
                    <KindBadge kind={conn.kind} />
                  </div>
                  {/* Технический URL не показываем аналитику. Embedded — порт mono,
                      proxy — имя профиля внешнего шлюза. Полный endpoint виден в форме редактирования
                      под «Расширенные настройки». */}
                  <p className="text-xs text-[var(--fg-muted)] truncate">
                    <ConnectionSummary conn={conn} />
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
                    className="text-[var(--error)] hover:text-[var(--error)]"
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
              className="bg-[var(--error)] hover:opacity-90"
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
