import { describe, it, expect } from "vitest";
import { buddyView } from "../StatusCapsule";
import type { BuddyHealth } from "@/lib/types";

function b(over: Partial<BuddyHealth>): BuddyHealth {
  return { enabled: true, status: "up", degraded: false, ...over } as BuddyHealth;
}

/**
 * Индикатор «ИТС · Напарник» в шапке: маппинг статуса из /health.buddy в строку.
 * Запрос пользователя: видеть на основной панели, работает Напарник или нет.
 */
describe("buddyView (индикатор Напарника)", () => {
  it("up → Работает / online", () => {
    const v = buddyView(b({ status: "up" }));
    expect(v.status).toBe("online");
    expect(v.value).toBe("Работает");
  });

  it("down → Недоступен / offline + подсказка запустить 1c-buddy", () => {
    const v = buddyView(b({ status: "down" }));
    expect(v.status).toBe("offline");
    expect(v.value).toBe("Недоступен");
    expect(v.sub).toContain("1c-buddy");
  });

  it("enabled=false → Выключен (ИТС-поиск отключён)", () => {
    const v = buddyView(b({ enabled: false, status: "down" }));
    expect(v.value).toBe("Выключен");
    expect(v.status).toBe("offline");
  });

  it("null (старый backend без поля buddy) → Выключен", () => {
    expect(buddyView(null).value).toBe("Выключен");
  });

  it("unknown → Проверка… / connecting", () => {
    const v = buddyView(b({ status: "unknown" }));
    expect(v.status).toBe("connecting");
  });
});
