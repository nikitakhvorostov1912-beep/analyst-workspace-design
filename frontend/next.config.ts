import type { NextConfig } from "next";
import path from "path";

const isProd = process.env.NODE_ENV === "production";
const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8010";

// SEC-02: CSP headers только в production (dev HMR требует unsafe-eval)
const cspProd = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  `connect-src 'self' ${backendUrl}`,
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

const nextConfig: NextConfig = {
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
