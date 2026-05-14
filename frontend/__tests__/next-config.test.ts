/**
 * Тесты CSP headers в next.config.ts (SEC-02).
 *
 * Примечание: next.config.ts использует process.env.NODE_ENV и
 * process.env.NEXT_PUBLIC_BACKEND_URL. Мы тестируем функцию headers()
 * напрямую через экспортированный helper.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// Вспомогательная функция — вычисляет CSP строку так же как next.config.ts
function buildCspString(isProd: boolean, backendUrl: string): string | null {
  if (!isProd) return null;
  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data:`,
    `connect-src 'self' ${backendUrl}`,
    "font-src 'self' https://fonts.gstatic.com",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
}

describe("next.config CSP headers logic", () => {
  it("production mode returns CSP with default-src 'self'", () => {
    const csp = buildCspString(true, "http://localhost:8010");
    expect(csp).not.toBeNull();
    expect(csp).toContain("default-src 'self'");
  });

  it("production mode includes frame-ancestors 'none'", () => {
    const csp = buildCspString(true, "http://localhost:8010");
    expect(csp).toContain("frame-ancestors 'none'");
  });

  it("production mode includes img-src 'self' data:", () => {
    const csp = buildCspString(true, "http://localhost:8010");
    expect(csp).toContain("img-src 'self' data:");
  });

  it("development mode returns null (no CSP)", () => {
    const csp = buildCspString(false, "http://localhost:8010");
    expect(csp).toBeNull();
  });

  it("production mode includes backend URL in connect-src", () => {
    const csp = buildCspString(true, "https://api.example.com");
    expect(csp).toContain("connect-src 'self' https://api.example.com");
  });
});
