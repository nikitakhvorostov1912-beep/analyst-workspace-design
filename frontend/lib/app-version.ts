/**
 * Source-of-truth для отображаемой версии приложения.
 *
 * REM-3 (2026-05-24): раньше версия была захардкожена в 3 местах:
 *   - StencilLockup.tsx (`version = "1.2.2"`)
 *   - about/page.tsx (`Версия 1.2.1`)
 *   - frontend/package.json (`"version": "0.1.0"`)
 * Все три расходились.
 *
 * Теперь — единый импорт `APP_VERSION` из этого модуля. Значение прокидывается
 * через `next.config.ts → env.NEXT_PUBLIC_APP_VERSION`, который читает
 * `desktop/package.json` (там реальная семантическая версия v1.4.0).
 *
 * Если env не доступен (например, в jest без mock'а) — fallback на "1.4.0".
 */
export const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "1.4.5";
