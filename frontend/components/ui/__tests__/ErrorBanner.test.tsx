import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ErrorBanner } from "@/components/ui/ErrorBanner";

describe("ErrorBanner", () => {
  it("renders error severity by default", () => {
    const { container } = render(<ErrorBanner title="Ошибка соединения" />);
    const banner = container.querySelector('[role="alert"]');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveAttribute("data-severity", "error");
    expect(screen.getByText("Ошибка соединения")).toBeInTheDocument();
  });

  it("renders warning severity with description", () => {
    const { container } = render(
      <ErrorBanner
        severity="warning"
        title="Внимание"
        description="Сессия скоро истечёт"
      />,
    );
    const banner = container.querySelector('[role="alert"]');
    expect(banner).toHaveAttribute("data-severity", "warning");
    expect(screen.getByText("Внимание")).toBeInTheDocument();
    expect(screen.getByText("Сессия скоро истечёт")).toBeInTheDocument();
  });

  it("renders info severity", () => {
    const { container } = render(<ErrorBanner severity="info" title="Подсказка" />);
    expect(container.querySelector('[role="alert"]')).toHaveAttribute(
      "data-severity",
      "info",
    );
  });

  it("triggers onRetry when retry button clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorBanner title="Сбой" onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: /Повторить/ }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("triggers onDismiss when close button clicked", () => {
    const onDismiss = vi.fn();
    render(<ErrorBanner title="Закроется" onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole("button", { name: "Закрыть" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("renders both retry and dismiss together", () => {
    const onRetry = vi.fn();
    const onDismiss = vi.fn();
    render(
      <ErrorBanner title="Двойная" onRetry={onRetry} onDismiss={onDismiss} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Повторить/ }));
    fireEvent.click(screen.getByRole("button", { name: "Закрыть" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("omits retry/dismiss controls when callbacks not provided", () => {
    render(<ErrorBanner title="Только заголовок" />);
    expect(screen.queryByRole("button", { name: /Повторить/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Закрыть" })).not.toBeInTheDocument();
  });
});
