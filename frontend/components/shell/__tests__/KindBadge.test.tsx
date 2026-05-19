import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom";

import { KindBadge } from "../KindBadge";

describe("KindBadge", () => {
  it("не рендерится без kind (старый backend)", () => {
    const { container } = render(<KindBadge kind={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("показывает 'Локально' для embedded", () => {
    render(<KindBadge kind="embedded" />);
    expect(screen.getByText("Локально")).toBeInTheDocument();
    expect(screen.getByTestId("kind-badge-embedded")).toBeInTheDocument();
  });

  it("показывает 'Прокси' для proxy", () => {
    render(<KindBadge kind="proxy" />);
    expect(screen.getByText("Прокси")).toBeInTheDocument();
    expect(screen.getByTestId("kind-badge-proxy")).toBeInTheDocument();
  });

  it("title-тултип объясняет аналитику что значит embedded", () => {
    render(<KindBadge kind="embedded" />);
    const badge = screen.getByTestId("kind-badge-embedded");
    expect(badge).toHaveAttribute("title", expect.stringContaining("этом компьютере"));
  });

  it("title-тултип объясняет аналитику что значит proxy", () => {
    render(<KindBadge kind="proxy" />);
    const badge = screen.getByTestId("kind-badge-proxy");
    expect(badge).toHaveAttribute("title", expect.stringContaining("удалённом сервере"));
  });
});
