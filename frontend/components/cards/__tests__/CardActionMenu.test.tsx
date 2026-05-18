import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { Copy } from "lucide-react";
import { CardActionMenu } from "@/components/cards/CardActionMenu";

// Note: открытие dropdown через Radix Portal в jsdom нестабильно,
// поэтому тестируем только trigger + конфигурацию items.
// Открытие меню и клики по пунктам — проверяются Playwright (Phase 11.5).

describe("CardActionMenu", () => {
  it("renders trigger button with default aria-label", () => {
    render(<CardActionMenu items={[]} />);
    expect(screen.getByLabelText("Действия")).toBeInTheDocument();
    expect(screen.getByTestId("card-action-trigger")).toBeInTheDocument();
  });

  it("accepts custom triggerAriaLabel", () => {
    render(<CardActionMenu items={[]} triggerAriaLabel="Меню карточки" />);
    expect(screen.getByLabelText("Меню карточки")).toBeInTheDocument();
  });

  it("renders MoreHorizontal icon inside trigger", () => {
    render(<CardActionMenu items={[{ label: "Копировать", icon: Copy }]} />);
    const trigger = screen.getByTestId("card-action-trigger");
    expect(trigger.querySelector("svg")).toBeInTheDocument();
  });

  it("accepts mix of separator and items in props without crashing", () => {
    render(
      <CardActionMenu
        items={[
          { label: "Копировать", icon: Copy, kbd: "⌘C" },
          "separator",
          { label: "Скрыть", destructive: true },
        ]}
      />,
    );
    // Trigger всё ещё рендерится (контент в Portal до клика)
    expect(screen.getByTestId("card-action-trigger")).toBeInTheDocument();
  });
});
