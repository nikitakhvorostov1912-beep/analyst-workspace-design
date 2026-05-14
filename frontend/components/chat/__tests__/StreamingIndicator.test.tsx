import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { StreamingIndicator } from "../StreamingIndicator";

describe("StreamingIndicator", () => {
  it("renders 'Анализирую...' for thinking stage", () => {
    render(<StreamingIndicator stage="thinking" />);
    expect(screen.getByText(/Анализирую/)).toBeInTheDocument();
  });

  it("renders tool name for calling_tool stage", () => {
    render(<StreamingIndicator stage="calling_tool" toolName="execute_query" />);
    expect(screen.getByText(/Вызываю execute_query/)).toBeInTheDocument();
  });

  it("renders 'Формирую ответ...' for formatting stage", () => {
    render(<StreamingIndicator stage="formatting" />);
    expect(screen.getByText(/Формирую ответ/)).toBeInTheDocument();
  });

  it("renders fallback tool name when toolName not provided for calling_tool", () => {
    render(<StreamingIndicator stage="calling_tool" />);
    expect(screen.getByText(/Вызываю инструмент/)).toBeInTheDocument();
  });

  it("returns null when stage is null", () => {
    const { container } = render(<StreamingIndicator stage={null} />);
    expect(container.firstChild).toBeNull();
  });
});
