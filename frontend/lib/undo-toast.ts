/**
 * UndoToast pub/sub — тонкий event emitter для глобального tost-state.
 *
 * Sprint 02 (handoff 2026-05-23, A): аналог `lib/toast.ts`, но для
 * undo-операций. `UndoToastHost` слушает изменения и рендерит активный
 * toast; component-caller вызывает `publishUndoToast({...})` чтобы
 * запустить оптимистичное удаление с возможностью отмены.
 *
 * Одновременно в системе только ОДИН undo-toast (последний публикует
 * предыдущий). Это OK для типичного UX delete-операции.
 */
import type { UndoToastProps } from "@/components/ui/UndoToast";

type Listener = (toast: UndoToastProps | null) => void;
const listeners = new Set<Listener>();
let current: UndoToastProps | null = null;

export function publishUndoToast(toast: UndoToastProps) {
  current = toast;
  listeners.forEach((l) => l(toast));
}

export function dismissUndoToast() {
  current = null;
  listeners.forEach((l) => l(null));
}

export function listenUndoToast(l: Listener): () => void {
  listeners.add(l);
  l(current);
  return () => {
    listeners.delete(l);
  };
}
