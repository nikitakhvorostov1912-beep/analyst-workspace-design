import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import "@testing-library/jest-dom";

// Мокаем subscribeToast/publishToast из lib/toast
vi.mock("@/lib/toast", () => {
  let listener: ((e: CustomEvent) => void) | null = null;

  return {
    publishToast: vi.fn((opts) => {
      if (listener) {
        listener(new CustomEvent("app:toast", { detail: opts }));
      }
    }),
    subscribeToast: vi.fn((cb: (opts: unknown) => void) => {
      listener = (e: CustomEvent) => cb(e.detail);
      return () => { listener = null; };
    }),
  };
});

import { Toaster } from "@/components/ui/toast";
import { publishToast } from "@/lib/toast";

describe("Toaster", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.runAllTimers();
    vi.useRealTimers();
  });

  it("renders toast message on publishToast", async () => {
    render(<Toaster />);

    act(() => {
      publishToast({ type: "error", message: "Тест ошибки" });
    });

    expect(screen.getByText("Тест ошибки")).toBeInTheDocument();
  });

  it("auto-dismisses after default 8s", async () => {
    render(<Toaster />);

    act(() => {
      publishToast({ type: "error", message: "Auto dismiss" });
    });

    expect(screen.getByText("Auto dismiss")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(8000);
    });

    expect(screen.queryByText("Auto dismiss")).not.toBeInTheDocument();
  });

  it("respects custom duration_ms", async () => {
    render(<Toaster />);

    act(() => {
      publishToast({ type: "error", message: "Short toast", duration_ms: 3000 });
    });

    expect(screen.getByText("Short toast")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2999);
    });
    expect(screen.getByText("Short toast")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByText("Short toast")).not.toBeInTheDocument();
  });

  it("shows countdown seconds when countdownSeconds provided", async () => {
    render(<Toaster />);

    act(() => {
      publishToast({ type: "warning", message: "Rate limit", countdownSeconds: 5 });
    });

    // Должна быть цифра 5
    expect(screen.getByText(/5/)).toBeInTheDocument();
    expect(screen.getByText("Rate limit")).toBeInTheDocument();
  });

  it("countdown decrements each second", async () => {
    render(<Toaster />);

    act(() => {
      publishToast({ type: "warning", message: "Retry in", countdownSeconds: 5 });
    });

    expect(screen.getByText(/5/)).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText(/4/)).toBeInTheDocument();
  });
});
