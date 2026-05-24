import type { NextConfig } from "next";
import fs from "node:fs";
import path from "path";

const isProd = process.env.NODE_ENV === "production";
const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8010";

// REM-3 (2026-05-24): источник правды для UI-версии — `desktop/package.json`.
// Раньше в коде было три разных значения (Header lockup default, About page text,
// frontend/package.json). Теперь все читают через APP_VERSION → version из desktop.
let pkgVersion = "1.4.5";
try {
  const desktopPkg = JSON.parse(
    fs.readFileSync(path.join(process.cwd(), "..", "desktop", "package.json"), "utf-8"),
  );
  if (typeof desktopPkg.version === "string") pkgVersion = desktopPkg.version;
} catch {
  // Если читать не удалось (CI / odd cwd) — оставляем fallback 1.4.0
}

// SEC-02: CSP headers только в production (dev HMR требует unsafe-eval).
// connect-src включает http://127.0.0.1:* + http://localhost:* — в Electron-сборке
// backend стартует на random порту runtime, CSP не должна его блокировать.
// Безопасно для desktop: backend всегда локальный.
const cspProd = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  `connect-src 'self' ${backendUrl} http://127.0.0.1:* http://localhost:*`,
  "font-src 'self' https://fonts.gstatic.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const securityHeaders = isProd
  ? [
      { key: "Content-Security-Policy", value: cspProd },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    ]
  : [];

// output: "standalone" — включается через env NEXT_OUTPUT=standalone для Docker production и Electron.
// Windows caveat: pnpm использует symlinks в .pnpm; build-bundle.js устанавливает node-linker=hoisted
// перед вызовом pnpm build и восстанавливает после — это делает node_modules плоским (без symlinks).
const isStandalone = process.env.NEXT_OUTPUT === "standalone";
const nextConfig: NextConfig = {
  ...(isStandalone ? { output: "standalone" as const } : {}),
  // 2026-05-24 (FINDING-13): в dev React Strict Mode делает double-mount
  // useEffect — cleanup первого mount зовёт `abortRef.current?.abort()` в
  // useChatStream, пока send() ещё в полёте. Юзер видит "signal is aborted
  // without reason" сразу после Enter с главной. В production (Electron) StrictMode
  // неактивен по дизайну React — но локальный smoke в Chrome MCP попадает на
  // dev-сервер, и это даёт false-negative. Отключаем strict в dev чтобы
  // smoke совпадал с реальным prod-поведением.
  reactStrictMode: false,
  env: {
    NEXT_PUBLIC_APP_VERSION: pkgVersion,
  },
  experimental: {
    reactCompiler: false,
  },
  eslint: {
    ignoreDuringBuilds: false,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  // Явно указываем корень для output file tracing — убирает warning о множественных lockfile
  outputFileTracingRoot: path.join(process.cwd(), ".."),
  async headers() {
    // В dev-режиме headers === [] — Next.js 15 валидатор отвергает пустой headers.
    // Возвращаем пустой список правил, чтобы dev-сервер стартовал.
    if (!isProd) return [];
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
