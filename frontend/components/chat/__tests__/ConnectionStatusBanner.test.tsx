import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ConnectionStatusBanner } from "../ConnectionStatusBanner";

describe("ConnectionStatusBanner", () => {
  it("returns null when visible is false", () => {
    const { container } = render(
      <ConnectionStatusBanner
        visible={false}
        channelName="База РТ"
        onRetry={vi.fn()}
        retrying={false}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows connection lost text and retry button when visible", () => {
    render(
      <ConnectionStatusBanner
        visible={true}
        channelName="База РТ"
        onRetry={vi.fn()}
        retrying={false}
      />,
    );
    expect(screen.getByText(/База РТ/)).toBeInTheDocument();
    expect(screen.getByText(/Повторить/)).toBeInTheDocument();
  });

  it("shows generic message without channelName", () => {
    render(
      <ConnectionStatusBanner
        visible={true}
        onRetry={vi.fn()}
        retrying={false}
      />,
    );
    expect(screen.getByText(/Подключение к 1С потеряно/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Повторить/ })).toBeInTheDocument();
  });

  it("calls onRetry when retry button clicked", () => {
    const onRetry = vi.fn();
    render(
      <ConnectionStatusBanner
        visible={true}
        onRetry={onRetry}
        retrying={false}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Повторить/ }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("disables retry button while retrying", () => {
    render(
      <ConnectionStatusBanner
        visible={true}
        onRetry={vi.fn()}
        retrying={true}
      />,
    );
    // При retrying=true кнопка должна быть disabled
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
  });
});
