"use client";

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { cn } from "@/lib/utils";

export interface UndoToastProps {
  /** Уникальный id операции — для идемпотентности и React key */
  id: string;
  /** Заголовок: что произошло — «Чат удалён» */
  title: string;
  /** Уточнение (mono eyebrow) — «#A4F2 · Продажи апрель» */
  subtitle?: string;
  /** Сколько мс держать. Default: 5000 */
  durationMs?: number;
  /** Пользователь нажал «↺ Отменить» — onCommit НЕ будет вызван */
  onUndo: () => void;
  /** Истёк durationMs — отправляем реальный DELETE на backend */
  onCommit: () => void | Promise<void>;
}

export interface UndoToastHandle {
  dismiss(): void;
}

/**
 * UndoToast — оптимистичное удаление с возможностью отмены.
 *
 * Sprint 02 (handoff 2026-05-23, A): заменяет `window.confirm()` для
 * delete-операций. UX: запись пропадает мгновенно из UI, появляется
 * toast с прогресс-баром на durationMs (default 5s). За это время
 * пользователь может откатить кликом «↺ Отменить» — иначе commit
 * (реальный DELETE).
 *
 * Тоsta управляется через `publishUndoToast()` из `@/lib/undo-toast`,
 * рендерится в `<UndoToastHost />` на верхнем уровне layout.
 *
 * Hover паузит прогресс-бар (CSS animation-play-state).
 */
export const UndoToast = forwardRef<UndoToastHandle, UndoToastProps>(function UndoToast(
  { id, title, subtitle, durationMs = 5000, onUndo, onCommit },
  ref,
) {
  const [closing, setClosing] = useState(false);
  const committedRef = useRef(false);
  const timerRef = useRef<number>(0);

  useImperativeHandle(ref, () => ({
    dismiss() {
      window.clearTimeout(timerRef.current);
      setClosing(true);
    },
  }));

  useEffect(() => {
    timerRef.current = window.setTimeout(() => {
      if (!committedRef.current) {
        committedRef.current = true;
        void onCommit();
        setClosing(true);
      }
    }, durationMs);
    return () => window.clearTimeout(timerRef.current);
  }, [durationMs, onCommit]);

  function handleUndo() {
    if (committedRef.current) return;
    committedRef.current = true;
    window.clearTimeout(timerRef.current);
    onUndo();
    setClosing(true);
  }

  if (closing) return null;

  return (
    <div
      data-id={id}
      data-state={closing ? "closing" : "open"}
      role="status"
      aria-live="polite"
      className={cn(
        "toast-undo fixed left-1/2 -translate-x-1/2 bottom-4 z-50 min-w-[320px] max-w-md",
        "bg-[var(--bg-2)] border border-[var(--bd-3)] rounded-lg shadow-xl px-4 py-3",
        "flex items-center gap-3 overflow-hidden",
      )}
      style={{ ["--toast-duration" as string]: `${durationMs}ms` }}
    >
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <div className="text-sm font-medium text-[var(--fg-1)]">{title}</div>
        {subtitle && (
          <div
            className="text-[10px] tracking-[0.14em] uppercase text-[var(--fg-4)] truncate"
            style={{
              fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={handleUndo}
        className={cn(
          "px-3 py-1 text-[10px] tracking-[0.14em] uppercase rounded border",
          "border-[var(--bd-3)] text-[var(--accent)] hover:bg-[var(--accent-08)] transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-2)]",
        )}
        style={{
          fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
        }}
      >
        ↺ Отменить
      </button>
      <div
        className="toast-progress absolute left-0 bottom-0 h-[2px] bg-[var(--accent)] rounded-b-lg"
        aria-hidden="true"
      />
    </div>
  );
});
