"use client";

import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ConfirmRequiredPayload } from "@/lib/types";

type Props = {
  open: boolean;
  payload: ConfirmRequiredPayload | null;
  onResolve: (approved: boolean) => void;
  loading?: boolean;
};

/**
 * Модальный диалог подтверждения опасного execute_code (SEC-01).
 * Показывает reason + args JSON, кнопки Выполнить/Отменить.
 */
export function ConfirmExecuteDialog({ open, payload, onResolve, loading }: Props) {
  if (!payload) return null;

  return (
    <Dialog open={open}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Подтвердите выполнение кода 1С</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 py-2">
          <p className="text-sm text-[var(--fg-muted)]">
            LLM хочет выполнить потенциально опасный код:
          </p>

          {/* Reason — почему сработал триггер */}
          <div className="rounded border border-yellow-700/40 bg-yellow-950/30 px-3 py-2">
            <span className="font-mono text-sm text-yellow-300">{payload.reason}</span>
          </div>

          {/* Args JSON */}
          <div className="rounded border border-[var(--border)] bg-[var(--bg)] px-3 py-2">
            <pre className="overflow-auto text-xs text-[var(--fg-muted)] whitespace-pre-wrap">
              {JSON.stringify(payload.args, null, 2)}
            </pre>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="secondary"
            onClick={() => onResolve(false)}
            disabled={loading}
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Отменить
          </Button>
          <Button
            variant="destructive"
            onClick={() => onResolve(true)}
            disabled={loading}
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Выполнить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
