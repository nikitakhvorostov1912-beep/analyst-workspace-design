/**
 * SSR-safe sessionStorage helpers для api_key LLM.
 * Ключ выживает до закрытия вкладки (не localStorage — trade-off T-05-06).
 */

const KEY_LLM_API_KEY = "analyst.llm_api_key";

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
