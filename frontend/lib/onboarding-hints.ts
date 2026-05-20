/**
 * Contextual one-time onboarding hints (порт паттерна Hermes `agent/onboarding.py`).
 *
 * Каждая подсказка показывается ОДИН раз когда пользователь
 * впервые попадает в behavior fork (а не блокирующим wizard на старте).
 * Состояние «seen» хранится в localStorage.
 *
 * Использование:
 *   if (shouldShowHint("memory_first_use", {sessionCount: 3})) {
 *     publishToast({ type: "info", message: "..." });
 *     markHintSeen("memory_first_use");
 *   }
 */

const HINT_STORAGE_PREFIX = "analyst.onboarding.";

export type HintId =
  | "memory_first_use"
  | "clarify_first_use"
  | "compression_first_fire"
  | "trajectory_first_log";

/** True если этот hint ещё не был показан этому пользователю. */
export function hasNotSeen(hintId: HintId): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(`${HINT_STORAGE_PREFIX}${hintId}`) !== "true";
}

/** Помечает hint как показанный. После этого hasNotSeen вернёт false. */
export function markHintSeen(hintId: HintId): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(`${HINT_STORAGE_PREFIX}${hintId}`, "true");
}

/** Сброс ВСЕХ hints — для тестов / debug. */
export function resetAllHints(): void {
  if (typeof window === "undefined") return;
  const keys = Object.keys(localStorage).filter((k) =>
    k.startsWith(HINT_STORAGE_PREFIX),
  );
  for (const k of keys) localStorage.removeItem(k);
}
