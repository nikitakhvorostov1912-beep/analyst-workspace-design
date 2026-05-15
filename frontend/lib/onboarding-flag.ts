/**
 * localStorage helpers для флага прохождения onboarding.
 * SSR-safe: возвращает false/no-op если не в браузере.
 */

const KEY_ONBOARDING = "analyst.onboarding_completed";

// SSR-safe helper — паттерн storage.ts
function safeLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

/**
 * Возвращает true если onboarding пройден или пропущен.
 */
export function getOnboardingCompleted(): boolean {
  const ls = safeLocalStorage();
  if (!ls) return false;
  return ls.getItem(KEY_ONBOARDING) === "true";
}

/**
 * Устанавливает или сбрасывает флаг onboarding.
 * setOnboardingCompleted(true)  — помечает как пройденный
 * setOnboardingCompleted(false) — сбрасывает (только для тестов/dev-tools)
 */
export function setOnboardingCompleted(done: boolean): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  if (done) {
    ls.setItem(KEY_ONBOARDING, "true");
  } else {
    ls.removeItem(KEY_ONBOARDING);
  }
}
