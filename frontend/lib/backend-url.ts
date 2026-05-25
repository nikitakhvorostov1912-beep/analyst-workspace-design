/**
 * Backend URL resolution — единая точка для всех модулей frontend.
 *
 * Вынесено в отдельный файл 2026-05-25 после регрессии v1.4.6:
 * раньше getBackend() жил в api.ts и api-keys.ts импортировал его оттуда.
 * Параллельно api.ts импортировал getLLMApiKey из api-keys.ts —
 * получалась circular dependency. В dev/vitest всё работало (Vite
 * толерантен к циклам), но Next 15 production build с tree-shaking
 * оставлял один из re-exports undefined → TypeError на инициализации
 * client-bundle → blank screen в Electron-сборке.
 *
 * Правило: getBackend() — низкоуровневый primitive, ничего не должен
 * импортировать из api.ts / api-keys.ts. Эти два модуля могут
 * импортировать его — но не друг друга через него.
 *
 * Backend URL resolution priority:
 *   1. window.__BACKEND_URL__ — runtime-injected layout.tsx
 *      (Electron-сборка, где backend стартует на random порту).
 *   2. process.env.NEXT_PUBLIC_BACKEND_URL — server-side рендеринг.
 *   3. http://localhost:8010 — dev/docker fallback.
 *
 * Use getter (не const на module level), иначе значение зафиксируется
 * в client bundle на build-time и Electron-сборка получит null URL.
 */
export function getBackend(): string {
  if (typeof window !== "undefined") {
    const w = window as Window & { __BACKEND_URL__?: string };
    if (w.__BACKEND_URL__) return w.__BACKEND_URL__;
  }
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_BACKEND_URL) {
    return process.env.NEXT_PUBLIC_BACKEND_URL;
  }
  return "http://localhost:8010";
}
