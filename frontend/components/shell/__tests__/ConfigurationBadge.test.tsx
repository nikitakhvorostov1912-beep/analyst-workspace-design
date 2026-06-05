/**
 * Tests for ConfigurationBadge (Phase 6, Task 6.2).
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfigurationBadge } from "@/components/shell/ConfigurationBadge";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const base = { id: "c1", name: "B", endpoint: "http://x/mcp" } as any;

describe("ConfigurationBadge", () => {
  it("показывает detected-конфу с пометкой (авто)", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "КА 2.5", configuration_source: "auto" }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getByText(/КА 2\.5/)).toBeInTheDocument();
    expect(screen.getByText(/авто/i)).toBeInTheDocument();
  });

  it("ambiguous → знак вопроса / требует подтверждения", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "КА 2.5", configuration_source: "ambiguous" }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getByTestId("config-badge")).toHaveAttribute("data-state", "ambiguous");
  });

  it("failed → состояние повтора", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: null, configuration_source: "failed" }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getByTestId("config-badge")).toHaveAttribute("data-state", "failed");
  });

  it("custom → Самописная", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "Самописная", configuration_source: "custom" }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getByText(/Самописная/)).toBeInTheDocument();
  });

  it("none (нет конфы и источника) → data-state none", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: null, configuration_source: null }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getByTestId("config-badge")).toHaveAttribute("data-state", "none");
  });

  it("confirmed — data-state confirmed", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "УТ 11.5", configuration_source: "confirmed" }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getByTestId("config-badge")).toHaveAttribute("data-state", "confirmed");
    expect(screen.getByText(/УТ 11\.5/)).toBeInTheDocument();
  });
});
