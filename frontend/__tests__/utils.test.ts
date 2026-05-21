import { describe, expect, it } from "vitest";
import { cn, parseBackendDate } from "@/lib/utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("handles falsy values", () => {
    expect(cn("a", false, undefined, "b")).toBe("a b");
  });
});

describe("parseBackendDate", () => {
  // Regression: до v1.2.14 frontend парсил "2026-05-21T12:25:50" (без TZ)
  // как локальное время. У пользователя в Москве (+3) свежесозданная сессия
  // отображалась как «3 часа назад» вместо «только что».

  it("парсит timezone-naive строку как UTC", () => {
    // 2026-05-21T12:25:50 (без TZ) — должен быть распознан как UTC
    const d = parseBackendDate("2026-05-21T12:25:50");
    expect(d.toISOString()).toBe("2026-05-21T12:25:50.000Z");
  });

  it("уважает таймзону когда она есть (Z)", () => {
    const d = parseBackendDate("2026-05-21T12:25:50Z");
    expect(d.toISOString()).toBe("2026-05-21T12:25:50.000Z");
  });

  it("уважает таймзону когда она есть (+offset)", () => {
    const d = parseBackendDate("2026-05-21T15:25:50+03:00");
    expect(d.toISOString()).toBe("2026-05-21T12:25:50.000Z");
  });

  it("уважает таймзону без двоеточия (+HHMM)", () => {
    const d = parseBackendDate("2026-05-21T15:25:50+0300");
    expect(d.toISOString()).toBe("2026-05-21T12:25:50.000Z");
  });

  it("свежая UTC-метка интерпретируется как «только что» относительно now()", () => {
    const nowUtc = new Date().toISOString().slice(0, 19); // "YYYY-MM-DDTHH:MM:SS" без Z
    const parsed = parseBackendDate(nowUtc);
    const diffMs = Math.abs(Date.now() - parsed.getTime());
    // Допустимый разрыв — пара секунд между формированием nowUtc и Date.now
    expect(diffMs).toBeLessThan(5000);
  });
});
