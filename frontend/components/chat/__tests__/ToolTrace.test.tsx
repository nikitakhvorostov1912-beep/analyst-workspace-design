import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ToolTrace } from "@/components/chat/ToolTrace";
import type { ToolCallRecord } from "@/lib/types";

const makeTC = (overrides: Partial<ToolCallRecord> = {}): ToolCallRecord => ({
  id: "tc1",
  name: "execute_query",
  args: { query: "ВЫБРАТЬ * ИЗ ..." },
  ...overrides,
});

describe("ToolTrace", () => {
  it("возвращает null при пустом массиве tool_calls", () => {
    const { container } = render(<ToolTrace toolCalls={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("показывает заголовок с числом инструментов при наличии tool_calls", () => {
    render(
      <ToolTrace
        toolCalls={[makeTC({ id: "1", name: "get_metadata" }), makeTC({ id: "2", name: "execute_query" })]}
        totalDurationMs={500}
      />
    );
    expect(screen.getByText(/2 инструмента/)).toBeInTheDocument();
    expect(screen.getByText(/500 мс/)).toBeInTheDocument();
  });

  it("клик на заголовок раскрывает список tool calls", () => {
    render(
      <ToolTrace
        toolCalls={[
          makeTC({ id: "1", name: "get_metadata" }),
          makeTC({ id: "2", name: "execute_query" }),
        ]}
      />
    );
    const btn = screen.getByTestId("trace-toggle");
    fireEvent.click(btn);
    // список раскрыт — видны имена инструментов
    const names = screen.getAllByTestId("tool-name");
    expect(names).toHaveLength(2);
    expect(names[0]!.textContent).toBe("get_metadata");
    expect(names[1]!.textContent).toBe("execute_query");
  });

  it("tool с ok=false показывает badge ошибки", () => {
    render(
      <ToolTrace
        toolCalls={[makeTC({ ok: false, error: "MCP timeout" })]}
      />
    );
    const btn = screen.getByTestId("trace-toggle");
    fireEvent.click(btn);
    expect(screen.getByTestId("tool-error-badge")).toBeInTheDocument();
    expect(screen.getByTestId("tool-error-text")).toHaveTextContent("MCP timeout");
  });

  it("tool с result показывает секцию Результат", () => {
    render(
      <ToolTrace
        toolCalls={[makeTC({ result: { rows: [1, 2, 3] }, ok: true })]}
      />
    );
    const btn = screen.getByTestId("trace-toggle");
    fireEvent.click(btn);
    expect(screen.getByTestId("result-details")).toBeInTheDocument();
    expect(screen.getByText("Результат")).toBeInTheDocument();
  });

  it("один инструмент — правильная форма слова 'инструмент'", () => {
    render(<ToolTrace toolCalls={[makeTC()]} />);
    expect(screen.getByText(/1 инструмент/)).toBeInTheDocument();
  });

  it("5 инструментов — правильная форма слова 'инструментов'", () => {
    const tcs = Array.from({ length: 5 }, (_, i) =>
      makeTC({ id: String(i), name: `tool_${i}` })
    );
    render(<ToolTrace toolCalls={tcs} />);
    expect(screen.getByText(/5 инструментов/)).toBeInTheDocument();
  });
});
