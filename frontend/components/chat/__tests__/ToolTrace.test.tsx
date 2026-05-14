import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
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

describe("ToolTrace copy-curl", () => {
  let writeTextMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: writeTextMock },
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("test_tool_trace_renders_copy_curl_button: expanded mode показывает кнопку Скопировать как curl", () => {
    render(
      <ToolTrace
        toolCalls={[makeTC()]}
        mcpEndpoint="http://localhost:6010/mcp"
      />
    );
    // Открываем trace
    fireEvent.click(screen.getByTestId("trace-toggle"));
    expect(
      screen.getByRole("button", { name: /Скопировать как curl/i })
    ).toBeInTheDocument();
  });

  it("test_tool_trace_copy_curl_click_calls_clipboard_and_toast: click → clipboard.writeText вызван", async () => {
    // Мокаем publishToast
    const toastMock = vi.fn();
    vi.doMock("@/lib/toast", () => ({ publishToast: toastMock }));

    render(
      <ToolTrace
        toolCalls={[makeTC({ name: "execute_query", args: { q: "SELECT 1" } })]}
        mcpEndpoint="http://localhost:6010/mcp"
      />
    );
    fireEvent.click(screen.getByTestId("trace-toggle"));

    const btn = screen.getByRole("button", { name: /Скопировать как curl/i });
    await act(async () => {
      fireEvent.click(btn);
    });

    expect(writeTextMock).toHaveBeenCalledTimes(1);
    const curlCmd = writeTextMock.mock.calls[0][0] as string;
    expect(curlCmd).toContain("curl -X POST");
    expect(curlCmd).toContain("execute_query");
  });

  it("test_tool_trace_copy_curl_failure_shows_error_toast: writeText reject → publishToast error", async () => {
    writeTextMock.mockRejectedValue(new Error("NotAllowed"));

    const dispatchSpy = vi.spyOn(window, "dispatchEvent");

    render(
      <ToolTrace
        toolCalls={[makeTC()]}
        mcpEndpoint="http://localhost:6010/mcp"
      />
    );
    fireEvent.click(screen.getByTestId("trace-toggle"));

    const btn = screen.getByRole("button", { name: /Скопировать как curl/i });
    await act(async () => {
      fireEvent.click(btn);
    });

    // publishToast вызывается через window.dispatchEvent
    const toastEvents = dispatchSpy.mock.calls.filter(
      ([e]) => e instanceof CustomEvent && (e as CustomEvent).type === "app:toast"
    );
    expect(toastEvents.length).toBeGreaterThan(0);
    const lastEvent = toastEvents[toastEvents.length - 1]![0] as CustomEvent;
    expect(lastEvent.detail.type).toBe("error");
  });
});
