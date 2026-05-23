import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { MemoryHint } from "../MemoryHint";

const TOAST_EVENT = "app:toast";

describe("MemoryHint", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("не показывает toast если sessionCount < threshold", () => {
    const handler = vi.fn();
    window.addEventListener(TOAST_EVENT, handler);
    render(<MemoryHint sessionCount={1} threshold={3} />);
    expect(handler).not.toHaveBeenCalled();
    window.removeEventListener(TOAST_EVENT, handler);
  });

  it("показывает toast при достижении threshold", () => {
    const handler = vi.fn();
    window.addEventListener(TOAST_EVENT, handler);
    render(<MemoryHint sessionCount={3} threshold={3} />);
    expect(handler).toHaveBeenCalledTimes(1);
    const firstCall = handler.mock.calls[0];
    expect(firstCall).toBeDefined();
    const evt = firstCall![0] as CustomEvent;
    expect(evt.detail.type).toBe("info");
    expect(evt.detail.message.toLowerCase()).toContain("сесси");
    window.removeEventListener(TOAST_EVENT, handler);
  });

  it("не показывает повторно — markHintSeen сохраняется в localStorage", () => {
    const handler = vi.fn();
    window.addEventListener(TOAST_EVENT, handler);
    const { rerender } = render(<MemoryHint sessionCount={3} threshold={3} />);
    rerender(<MemoryHint sessionCount={5} threshold={3} />);
    expect(handler).toHaveBeenCalledTimes(1); // только 1 раз
    window.removeEventListener(TOAST_EVENT, handler);
  });

  it("после ручного сброса localStorage показывается снова", () => {
    const handler = vi.fn();
    window.addEventListener(TOAST_EVENT, handler);
    const { unmount } = render(<MemoryHint sessionCount={3} threshold={3} />);
    unmount();
    expect(handler).toHaveBeenCalledTimes(1);

    localStorage.clear();
    render(<MemoryHint sessionCount={3} threshold={3} />);
    expect(handler).toHaveBeenCalledTimes(2);
    window.removeEventListener(TOAST_EVENT, handler);
  });
});
