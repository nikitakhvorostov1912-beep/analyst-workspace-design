/**
 * SSR-safe sessionStorage helpers для api_key LLM.
 * Ключ выживает до закрытия вкладки (не localStorage — trade-off T-05-06).
 */

const KEY_LLM_API_KEY = "analyst.llm_api_key";
// Старый ключ в localStorage (до Plan 5.4) — для one-time migration T-05-13
const KEY_LEGACY_LLM = "analyst.llm";

function safeSessionStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage;
}

export function getLLMApiKey(): string | null {
  const ss = safeSessionStorage();
  if (!ss) return null;
  return ss.getItem(KEY_LLM_API_KEY);
}

export function setLLMApiKey(key: string): void {
  const ss = safeSessionStorage();
  if (!ss) return;
  ss.setItem(KEY_LLM_API_KEY, key);
}

export function clearLLMApiKey(): void {
  const ss = safeSessionStorage();
  if (!ss) return;
  ss.removeItem(KEY_LLM_API_KEY);
}

/**
 * One-time migration T-05-13: если sessionStorage пуст но в localStorage есть
 * старый LLM api_key (от версий до Plan 5.4) — переносим в sessionStorage и
 * очищаем localStorage. Запускается один раз при старте приложения.
 */
export function migrateLegacyApiKey(): void {
  if (typeof window === "undefined") return;

  const ss = window.sessionStorage;
  const ls = window.localStorage;

  // Если ключ уже в sessionStorage — миграция не нужна
  if (ss.getItem(KEY_LLM_API_KEY)) return;

  // Читаем старый ключ из localStorage
  const legacyRaw = ls.getItem(KEY_LEGACY_LLM);
  if (!legacyRaw) return;

  try {
    const parsed = JSON.parse(legacyRaw) as Record<string, unknown>;
    if (parsed && typeof parsed.api_key === "string" && parsed.api_key.length > 0) {
      ss.setItem(KEY_LLM_API_KEY, parsed.api_key);
      // Очищаем устаревший localStorage ключ
      ls.removeItem(KEY_LEGACY_LLM);
    }
  } catch {
    // Если legacy значение не парсится — оставляем как есть
  }
}
