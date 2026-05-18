"use client";

import { useState } from "react";
import { Database, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { resetLocalDb } from "@/lib/api";
import { publishToast } from "@/lib/toast";

interface LocalDataSectionProps {
  onReset?: () => void;
}

/**
 * Phase 9.1: Privacy reset секция в Settings.
 *
 * Удаляет: messages, sessions, card_states, metadata_cache.
 * Сохраняет: mcp_connections, llm_settings, schema_version.
 * Backend требует X-Confirm-Reset: true header — защита от случайного вызова.
 */
export function LocalDataSection({ onReset }: LocalDataSectionProps = {}) {
  const [loading, setLoading] = useState(false);

  async function handleReset() {
    setLoading(true);
    try {
      const result = await resetLocalDb();
      if (result.ok) {
        const tables = result.cleared?.join(", ") ?? "";
        publishToast({
          type: "info",
          message: tables
            ? `Локальная база сброшена (${tables})`
            : "Локальная база сброшена",
        });
        onReset?.();
        // Дать тосту показаться, затем перезагрузить страницу
        setTimeout(() => {
          if (typeof window !== "undefined") {
            window.location.reload();
          }
        }, 1200);
      } else {
        publishToast({
          type: "error",
          message: `Не удалось сбросить базу${result.error ? `: ${result.error}` : ""}`,
        });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section data-testid="local-data-section" className="space-y-3">
      <div className="flex items-start gap-2.5">
        <div
          className="h-7 w-7 rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] text-[var(--fg-3)] inline-flex items-center justify-center flex-shrink-0 mt-0.5"
          aria-hidden="true"
        >
          <Database className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-[var(--fg-1)]">
            Локальные данные
          </h2>
          <p className="text-xs text-[var(--fg-3)] mt-1 leading-relaxed">
            Удаляет все сессии чата, токены анонимизации, кеш метаданных и
            состояния карточек. Настройки MCP и LLM сохраняются.
          </p>
        </div>
      </div>

      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button
            variant="destructive"
            disabled={loading}
            className="gap-2"
            data-testid="reset-db-trigger"
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            {loading ? "Сбрасываю..." : "Сбросить локальную базу"}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Точно сбросить базу?</AlertDialogTitle>
            <AlertDialogDescription>
              Действие необратимо. Все ваши сессии чата и токены анонимизации
              будут удалены. Настройки MCP-подключений и LLM останутся.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="reset-db-cancel">
              Отмена
            </AlertDialogCancel>
            <AlertDialogAction
              data-testid="reset-db-confirm"
              onClick={handleReset}
              className="bg-[var(--error)] text-white hover:bg-[var(--error)]/90"
            >
              Сбросить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
