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
 * P2.1 (2026-05-23): backend-only API key storage.
 *
 * Сохраняет ключ через POST /user-secrets. Сервер шифрует AES-256 GCM и
 * хранит локально. Frontend больше не видит ключ обратно (защита от XSS).
 *
 * provider_id определяется UI из выбранного провайдера (cloud-ru-qwen3,
 * nvidia-nim, и т.д., см. lib/llm-providers.ts).
 */
export async function saveSecretToBackend(
  provider_id: string,
  api_key: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";
    const response = await fetch(`${backend}/user-secrets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider_id, api_key }),
    });
    if (response.status === 204) return { ok: true };
    const text = await response.text();
    return { ok: false, error: text || `HTTP ${response.status}` };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "network error" };
  }
}

/**
 * Возвращает список provider_id для которых на backend есть сохранённый ключ.
 * Значения ключей НЕ возвращаются — только список. Это by design (XSS защита).
 */
export async function fetchSecretStatus(): Promise<string[]> {
  try {
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";
    const response = await fetch(`${backend}/user-secrets/status`);
    if (!response.ok) return [];
    const data = (await response.json()) as { providers?: string[] };
    return Array.isArray(data.providers) ? data.providers : [];
  } catch {
    return [];
  }
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
