import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Sparkline } from "../Sparkline";
import type { SparklinePoint } from "@/lib/types";

const points: SparklinePoint[] = [
  { label: "Янв", value: 100 },
  { label: "Фев", value: 150 },
  { label: "Мар", value: 120 },
];

describe("Sparkline", () => {
  it("returns null when < 2 points", () => {
    const { container } = render(<Sparkline points={[{ label: "Янв", value: 100 }]} />);
    expect(container.firstChild).toBeNull();
  });

  it("returns null for empty points array", () => {
    const { container } = render(<Sparkline points={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders polyline with correct number of points", () => {
    const { container } = render(<Sparkline points={points} />);
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
    // 3 точки → 3 координаты в polyline points
    const pts = polyline?.getAttribute("points")?.split(" ") ?? [];
    expect(pts.length).toBe(3);
  });

  it("aria-label includes point count and min/max", () => {
    const { container } = render(<Sparkline points={points} />);
    const svg = container.querySelector("svg");
    const label = svg?.getAttribute("aria-label") ?? "";
    expect(label).toContain("3");
    expect(label).toContain("мин");
    expect(label).toContain("макс");
  });

  it("handles flat line (all same values) without division by zero", () => {
    const flatPoints: SparklinePoint[] = [
      { label: "Янв", value: 500 },
      { label: "Фев", value: 500 },
      { label: "Мар", value: 500 },
    ];
    // Не должно бросать исключений
    expect(() => render(<Sparkline points={flatPoints} />)).not.toThrow();
    const { container } = render(<Sparkline points={flatPoints} />);
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
  });
});
