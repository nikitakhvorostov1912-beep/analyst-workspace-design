import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { CardSkeleton } from "@/components/cards/CardSkeleton";

describe("CardSkeleton", () => {
  it("renders with default 3 body rows", () => {
    const { container } = render(<CardSkeleton />);
    const skeleton = screen.getByTestId("card-skeleton");
    expect(skeleton).toBeInTheDocument();
    // header has 2 placeholder lines, body has 3 rows by default => 5 .bg-[var(--bg-2)] divs total (excluding icon)
    // we count specifically the body rows by spacing wrapper
    const bodyRows = container.querySelectorAll(".space-y-2 > .h-3");
    expect(bodyRows.length).toBe(3);
  });

  it("respects custom rows count", () => {
    const { container } = render(<CardSkeleton rows={6} />);
    const bodyRows = container.querySelectorAll(".space-y-2 > .h-3");
    expect(bodyRows.length).toBe(6);
  });

  it("has correct ARIA loading attributes", () => {
    render(<CardSkeleton />);
    const skeleton = screen.getByRole("status");
    expect(skeleton).toHaveAttribute("aria-busy", "true");
    expect(skeleton).toHaveAttribute("aria-label", "Загрузка карточки");
  });

  it("accepts custom aria-label", () => {
    render(<CardSkeleton aria-label="Загружаю таблицу" />);
    expect(screen.getByRole("status")).toHaveAttribute(
      "aria-label",
      "Загружаю таблицу",
    );
  });

  it("applies animate-skeleton-pulse animation class", () => {
    render(<CardSkeleton />);
    expect(screen.getByTestId("card-skeleton")).toHaveClass(
      "animate-skeleton-pulse",
    );
  });

  it("merges custom className", () => {
    const { container } = render(<CardSkeleton className="mt-8 my-custom" />);
    const skeleton = container.querySelector('[data-testid="card-skeleton"]');
    expect(skeleton).toHaveClass("mt-8");
    expect(skeleton).toHaveClass("my-custom");
  });
});
