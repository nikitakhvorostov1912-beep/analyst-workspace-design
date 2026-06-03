import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import "@testing-library/jest-dom";

import { EnvBadge, ENV_LABEL } from "../EnvBadge";
import {
  getConnectionEnvironment,
  setConnectionEnvironment,
} from "@/lib/storage";

describe("EnvBadge", () => {
  it("не рендерится без окружения (null/undefined)", () => {
    const { container: c1 } = render(<EnvBadge env={null} />);
    expect(c1.firstChild).toBeNull();
    const { container: c2 } = render(<EnvBadge env={undefined} />);
    expect(c2.firstChild).toBeNull();
  });

  it("prod → «ПРОД» + warning-тон + aria боевая база", () => {
    render(<EnvBadge env="prod" />);
    const badge = screen.getByTestId("env-badge");
    expect(badge).toHaveTextContent("ПРОД");
    expect(badge).toHaveAttribute("data-env", "prod");
    expect(badge).toHaveAttribute("aria-label", "боевая база — осторожно");
    expect(badge.className).toContain("var(--warning)");
  });

  it("test → «ТЕСТ» нейтральный тон (без warning)", () => {
    render(<EnvBadge env="test" />);
    const badge = screen.getByTestId("env-badge");
    expect(badge).toHaveTextContent("ТЕСТ");
    expect(badge).toHaveAttribute("data-env", "test");
    expect(badge.className).not.toContain("var(--warning)");
  });

  it("demo → «ДЕМО» нейтральный тон", () => {
    render(<EnvBadge env="demo" />);
    expect(screen.getByTestId("env-badge")).toHaveTextContent("ДЕМО");
  });

  it("ENV_LABEL маппинг полный", () => {
    expect(ENV_LABEL).toEqual({ prod: "ПРОД", test: "ТЕСТ", demo: "ДЕМО" });
  });
});

describe("connection environment storage (Вариант B)", () => {
  beforeEach(() => localStorage.clear());

  it("не помечено → null", () => {
    expect(getConnectionEnvironment("conn-1")).toBeNull();
  });

  it("round-trip set → get", () => {
    setConnectionEnvironment("conn-1", "prod");
    setConnectionEnvironment("conn-2", "test");
    expect(getConnectionEnvironment("conn-1")).toBe("prod");
    expect(getConnectionEnvironment("conn-2")).toBe("test");
  });

  it("снятие метки (null) удаляет окружение", () => {
    setConnectionEnvironment("conn-1", "demo");
    expect(getConnectionEnvironment("conn-1")).toBe("demo");
    setConnectionEnvironment("conn-1", null);
    expect(getConnectionEnvironment("conn-1")).toBeNull();
  });
});
