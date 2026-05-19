/**
 * SSR-safe localStorage helpers для api_key LLM.
 *
 * История решений:
 *  - Phase 5 (UX-04): хранили в sessionStorage — теряли ключ при закрытии вкладки.
 *    Аналитик постоянно вводил ключ заново — UX-катастрофа.
 *  - v1.2.2: миграция на localStorage. Проект распространяется только как Electron
 *    desktop installer (см. ROADMAP Phase 7), где нет third-party XSS векторов и
 *    нет shared browser context. Trade-off: на чистом веб-деплое ключ доступен из
 *    любого JS на origin — но web-деплой не поддерживается.
 *
 * При запуске приложения миграция переносит sessionStorage → localStorage если
 * там есть legacy ключ.
 */

const KEY_LLM_API_KEY = "analyst.llm_api_key";
// Старый ключ внутри JSON в localStorage (до Plan 5.4)
const KEY_LEGACY_LLM = "analyst.llm";

function safeLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

export function getLLMApiKey(): string | null {
  const ls = safeLocalStorage();
  if (!ls) return null;
  return ls.getItem(KEY_LLM_API_KEY);
}

export function setLLMApiKey(key: string): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  ls.setItem(KEY_LLM_API_KEY, key);
}

export function clearLLMApiKey(): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  ls.removeItem(KEY_LLM_API_KEY);
}

/**
 * One-time migration:
 *  - Если ключ уже в localStorage (новая схема) — выходим.
 *  - Если есть sessionStorage[analyst.llm_api_key] — переносим в localStorage.
 *  - Если есть legacy JSON localStorage[analyst.llm].api_key — переносим и удаляем.
 */
export function migrateLegacyApiKey(): void {
  if (typeof window === "undefined") return;

  const ls = window.localStorage;
  const ss = window.sessionStorage;

  // Уже в localStorage — миграция не нужна
  if (ls.getItem(KEY_LLM_API_KEY)) return;

  // Шаг 1: sessionStorage от Phase 5
  const fromSession = ss.getItem(KEY_LLM_API_KEY);
  if (fromSession) {
    ls.setItem(KEY_LLM_API_KEY, fromSession);
    ss.removeItem(KEY_LLM_API_KEY);
    return;
  }

  // Шаг 2: legacy JSON от версий до Plan 5.4
  const legacyRaw = ls.getItem(KEY_LEGACY_LLM);
  if (!legacyRaw) return;

  try {
    const parsed = JSON.parse(legacyRaw) as Record<string, unknown>;
    if (parsed && typeof parsed.api_key === "string" && parsed.api_key.length > 0) {
      ls.setItem(KEY_LLM_API_KEY, parsed.api_key);
      ls.removeItem(KEY_LEGACY_LLM);
    }
  } catch {
    // Не парсится — оставляем legacy как есть
  }
}
