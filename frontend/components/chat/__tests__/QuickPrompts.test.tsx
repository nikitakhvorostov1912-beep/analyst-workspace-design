import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QuickPrompts } from "../QuickPrompts";
import { DEFAULT_QUICK_PROMPTS } from "@/lib/quick-prompts";

describe("QuickPrompts", () => {
  it("renders 5 chips", () => {
    const onSelect = vi.fn();
    render(<QuickPrompts onSelect={onSelect} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(5);
  });

  it("click chip → onSelect called with full prompt text", () => {
    const onSelect = vi.fn();
    render(<QuickPrompts onSelect={onSelect} />);
    const buttons = screen.getAllByRole("button");
    const firstButton = buttons[0]!;
    fireEvent.click(firstButton);
    expect(onSelect).toHaveBeenCalledWith(DEFAULT_QUICK_PROMPTS[0]);
  });

  it("hidden prop → returns null", () => {
    const onSelect = vi.fn();
    const { container } = render(<QuickPrompts onSelect={onSelect} hidden />);
    expect(container.firstChild).toBeNull();
  });

  it("aria-labels are present on each chip", () => {
    const onSelect = vi.fn();
    render(<QuickPrompts onSelect={onSelect} />);
    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => {
      expect(btn).toHaveAttribute("aria-label");
      expect(btn.getAttribute("aria-label")).toContain("Быстрая подсказка");
    });
  });

  it("renders group with aria-label Быстрые подсказки", () => {
    const onSelect = vi.fn();
    render(<QuickPrompts onSelect={onSelect} />);
    const group = screen.getByRole("group", { name: /быстрые подсказки/i });
    expect(group).toBeInTheDocument();
  });
});
