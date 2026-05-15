import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CodeCard } from "../CodeCard";
import type { CodeCardPayload } from "@/lib/types";

function makePayload(overrides?: Partial<CodeCardPayload>): CodeCardPayload {
  return {
    language: "bsl",
    code: "Процедура Тест()\n  Возврат;\nКонецПроцедуры",
    executable: false,
    result: null,
    ...overrides,
  };
}

describe("CodeCard", () => {
  it("renders highlighted code with token spans", () => {
    const { container } = render(<CodeCard payload={makePayload()} />);
    // prismjs должен добавить span.token.keyword для Процедура
    const code = container.querySelector("code");
    expect(code?.innerHTML).toContain("token");
  });

  it("renders language badge", () => {
    render(<CodeCard payload={makePayload({ language: "bsl" })} />);
    expect(screen.getByText("BSL")).toBeTruthy();
  });

  it("renders SQL language badge", () => {
    render(<CodeCard payload={makePayload({ language: "sql", code: "SELECT 1" })} />);
    expect(screen.getByText("SQL")).toBeTruthy();
  });

  it("Copy button calls clipboard.writeText", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });

    render(<CodeCard payload={makePayload()} />);
    const copyButton = screen.getByTitle("Скопировать код");
    fireEvent.click(copyButton);

    expect(writeText).toHaveBeenCalledWith(makePayload().code);
    vi.unstubAllGlobals();
  });

  it("executable=true + result → «Результат» button visible", () => {
    const result = { output: "OK", exitCode: 0 };
    render(
      <CodeCard
        payload={makePayload({ executable: true, result })}
      />,
    );
    expect(screen.getByText("Результат")).toBeTruthy();
  });

  it("clicks toggle result visibility", () => {
    const result = { output: "OK" };
    render(
      <CodeCard
        payload={makePayload({ executable: true, result })}
      />,
    );
    const btn = screen.getByText("Результат");
    fireEvent.click(btn);
    // После клика результат должен быть виден
    expect(screen.getByText("Результат выполнения:")).toBeTruthy();
  });

  it("non-executable → no result button", () => {
    render(
      <CodeCard
        payload={makePayload({ executable: false, result: { x: 1 } })}
      />,
    );
    expect(screen.queryByText("Результат")).toBeNull();
  });
});
