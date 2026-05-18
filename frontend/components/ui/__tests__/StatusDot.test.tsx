import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import "@testing-library/jest-dom";
import { StatusDot } from "@/components/ui/StatusDot";

describe("StatusDot", () => {
  it("renders with online status (pulsing success dot)", () => {
    const { container } = render(<StatusDot status="online" />);
    const dot = container.querySelector('[role="status"]');
    expect(dot).toBeInTheDocument();
    expect(dot).toHaveAttribute("data-status", "online");
    expect(dot).toHaveClass("animate-status-pulse");
  });

  it("renders with offline status (no animation)", () => {
    const { container } = render(<StatusDot status="offline" />);
    const dot = container.querySelector('[role="status"]');
    expect(dot).toHaveAttribute("data-status", "offline");
    expect(dot).not.toHaveClass("animate-status-pulse");
    expect(dot).not.toHaveClass("animate-blink");
  });

  it("renders with connecting status (blink animation)", () => {
    const { container } = render(<StatusDot status="connecting" />);
    const dot = container.querySelector('[role="status"]');
    expect(dot).toHaveAttribute("data-status", "connecting");
    expect(dot).toHaveClass("animate-blink");
  });

  it("respects size prop (sm vs md)", () => {
    const { container, rerender } = render(<StatusDot status="online" size="sm" />);
    let dot = container.querySelector('[role="status"]');
    expect(dot).toHaveAttribute("data-size", "sm");
    expect(dot).toHaveClass("h-1.5");
    expect(dot).toHaveClass("w-1.5");

    rerender(<StatusDot status="online" size="md" />);
    dot = container.querySelector('[role="status"]');
    expect(dot).toHaveAttribute("data-size", "md");
    expect(dot).toHaveClass("h-2");
    expect(dot).toHaveClass("w-2");
  });

  it("uses default aria-label based on status", () => {
    const { container } = render(<StatusDot status="online" />);
    expect(container.querySelector('[role="status"]')).toHaveAttribute(
      "aria-label",
      "Статус: Онлайн",
    );
  });

  it("accepts custom aria-label override", () => {
    const { container } = render(
      <StatusDot status="offline" aria-label="MCP-соединение разорвано" />,
    );
    expect(container.querySelector('[role="status"]')).toHaveAttribute(
      "aria-label",
      "MCP-соединение разорвано",
    );
  });
});
