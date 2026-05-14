/**
 * Минимальная шина событий для toast-уведомлений.
 * ~30 строк, без глобальных переменных кроме window.
 */

export type ToastType = "info" | "warning" | "error";

export type ToastOptions = {
  type: ToastType;
  message: string;
  duration_ms?: number;
  countdownSeconds?: number;
};

const TOAST_EVENT = "app:toast";

/**
 * Публикует toast-уведомление через window CustomEvent.
 */
export function publishToast(opts: ToastOptions): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(TOAST_EVENT, { detail: opts }));
}

/**
 * Подписывается на toast-уведомления.
 * Возвращает функцию отписки.
 */
export function subscribeToast(listener: (opts: ToastOptions) => void): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = (e: Event) => {
    listener((e as CustomEvent<ToastOptions>).detail);
  };
  window.addEventListener(TOAST_EVENT, handler);
  return () => window.removeEventListener(TOAST_EVENT, handler);
}
