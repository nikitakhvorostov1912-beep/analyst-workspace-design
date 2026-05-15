import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "../MetricCard";
import type { MetricCardPayload, SparklinePoint } from "@/lib/types";

function makePayload(overrides?: Partial<MetricCardPayload>): MetricCardPayload {
  return {
    value: 1234567,
    label: "Сумма продаж",
    unit: null,
    sparkline: null,
    delta: null,
    ...overrides,
  };
}

describe("MetricCard", () => {
  it("renders value with ru-RU number format (1234567 → contains space)", () => {
    render(<MetricCard payload={makePayload({ value: 1234567 })} />);
    // ru-RU форматирование использует неразрывный пробел или обычный как разделитель тысяч
    const text = screen.getByText(/1[\s  ]234[\s  ]567/);
    expect(text).toBeTruthy();
  });

  it("renders label", () => {
    render(<MetricCard payload={makePayload({ label: "Выручка" })} />);
    expect(screen.getByText("Выручка")).toBeTruthy();
  });

  it("renders unit when provided", () => {
    render(<MetricCard payload={makePayload({ unit: "₽" })} />);
    expect(screen.getByText("₽")).toBeTruthy();
  });

  it("renders ArrowUp for delta direction up", () => {
    const { container } = render(
      <MetricCard
        payload={makePayload({
          delta: { value: 50, direction: "up", percent: false, percent_value: 10 },
        })}
      />,
    );
    // ArrowUp иконка: lucide рендерит SVG
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
    // delta значение должно присутствовать
    expect(container.textContent).toContain("+10");
  });

  it("renders ArrowDown for delta direction down", () => {
    const { container } = render(
      <MetricCard
        payload={makePayload({
          delta: { value: -30, direction: "down", percent: false, percent_value: -5 },
        })}
      />,
    );
    expect(container.textContent).toContain("-5");
  });

  it("no delta → no delta section rendered", () => {
    const { container } = render(
      <MetricCard payload={makePayload({ delta: null })} />,
    );
    // Нет текста с + или arrow
    expect(container.textContent).not.toMatch(/\+\d/);
  });

  it("renders Sparkline when payload.sparkline provided", () => {
    const sparkline: SparklinePoint[] = [
      { label: "Янв", value: 100 },
      { label: "Фев", value: 150 },
    ];
    const { container } = render(
      <MetricCard payload={makePayload({ sparkline })} />,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
  });

  it("no sparkline → no SVG polyline rendered", () => {
    const { container } = render(
      <MetricCard payload={makePayload({ sparkline: null })} />,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).toBeNull();
  });
});
