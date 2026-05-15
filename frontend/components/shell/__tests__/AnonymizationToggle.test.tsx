/**
 * Тесты AnonymizationToggle компонента.
 * Plan 04-01.
 */

import { fireEvent, render, screen, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnonymizationToggle } from "../AnonymizationToggle";

// --- localStorage mock ---

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

beforeEach(() => {
  localStorageMock.clear();
  vi.clearAllMocks();
});

afterEach(() => {
  localStorageMock.clear();
});

// ---------------------------------------------------------------------------

describe("AnonymizationToggle", () => {
  it("рендерится в состоянии ВЫКЛ по умолчанию", async () => {
    render(<AnonymizationToggle />);
    // Ждём useEffect (чтение localStorage on mount)
    await act(async () => {});

    const btn = screen.getByRole("button", { name: /переключатель анонимизации/i });
    expect(btn).toBeTruthy();
    expect(btn.getAttribute("aria-pressed")).toBe("false");
  });

  it("клик → ON, localStorage записан true", async () => {
    render(<AnonymizationToggle />);
    await act(async () => {});

    const btn = screen.getByRole("button", { name: /переключатель анонимизации/i });
    await act(async () => { fireEvent.click(btn); });

    expect(btn.getAttribute("aria-pressed")).toBe("true");
    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      "analyst.anon_enabled",
      "true",
    );
  });

  it("двойной клик → OFF, localStorage 'false'", async () => {
    render(<AnonymizationToggle />);
    await act(async () => {});

    const btn = screen.getByRole("button", { name: /переключатель анонимизации/i });
    await act(async () => { fireEvent.click(btn); }); // → ON
    await act(async () => { fireEvent.click(btn); }); // → OFF

    expect(btn.getAttribute("aria-pressed")).toBe("false");
    expect(localStorageMock.setItem).toHaveBeenLastCalledWith(
      "analyst.anon_enabled",
      "false",
    );
  });

  it("читает начальное состояние из localStorage on mount", async () => {
    // Устанавливаем значение ДО рендера
    localStorageMock.getItem.mockReturnValueOnce("true");

    render(<AnonymizationToggle />);
    await act(async () => {});

    const btn = screen.getByRole("button", { name: /переключатель анонимизации/i });
    expect(btn.getAttribute("aria-pressed")).toBe("true");
  });

  it("диспатчит CustomEvent anon-toggle при клике", async () => {
    const events: Event[] = [];
    window.addEventListener("anon-toggle", (e) => events.push(e));

    render(<AnonymizationToggle />);
    await act(async () => {});

    const btn = screen.getByRole("button", { name: /переключатель анонимизации/i });
    await act(async () => { fireEvent.click(btn); });

    expect(events).toHaveLength(1);
    const evt = events[0] as CustomEvent;
    expect(evt.detail.enabled).toBe(true);

    window.removeEventListener("anon-toggle", (e) => events.push(e));
  });
});
