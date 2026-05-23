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

  it("по дефолту свёрнут — видны preview-чипы с именами", () => {
    render(
      <ToolTrace
        toolCalls={[
          makeTC({ id: "1", name: "get_metadata" }),
          makeTC({ id: "2", name: "execute_query" }),
        ]}
      />
    );
    // Sprint 03: в свёрнутом режиме видны preview-чипы
    const names = screen.getAllByTestId("tool-name");
    expect(names).toHaveLength(2);
    expect(names[0]!.textContent).toBe("get_metadata");
    expect(names[1]!.textContent).toBe("execute_query");
  });

  it("клик на заголовок раскрывает trace в human-readable виде (TraceSummary)", () => {
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
    // Sprint 03 (handoff E): expanded режим — TraceSummary вместо чипов.
    // Видны step-блоки и human-readable заголовки.
    expect(screen.getByTestId("trace-step-0")).toBeInTheDocument();
    expect(screen.getByTestId("trace-step-1")).toBeInTheDocument();
    expect(screen.getByText(/Структура базы/)).toBeInTheDocument();
    expect(screen.getByText(/Запрос к 1С/)).toBeInTheDocument();
  });

  it("tool с ok=false показывает текст ошибки", () => {
    render(
      <ToolTrace
        toolCalls={[makeTC({ ok: false, error: "MCP timeout" })]}
      />
    );
    const btn = screen.getByTestId("trace-toggle");
    fireEvent.click(btn);
    expect(screen.getByTestId("tool-error-text")).toHaveTextContent("MCP timeout");
    // human-readable суффикс для ошибки
    expect(screen.getByText(/ошибка запроса/)).toBeInTheDocument();
  });

  it("tool с result показывает количество в summary", () => {
    render(
      <ToolTrace
        toolCalls={[makeTC({ result: { rows: [1, 2, 3] }, ok: true })]}
      />
    );
    const btn = screen.getByTestId("trace-toggle");
    fireEvent.click(btn);
    // Sprint 03: вместо raw details — human summary «3 записи»
    expect(screen.getByText(/3 записи/)).toBeInTheDocument();
  });

  it("клик «JSON» раскрывает raw view с параметрами и результатом", () => {
    render(
      <ToolTrace
        toolCalls={[makeTC({ result: { rows: [1, 2] }, ok: true })]}
      />
    );
    fireEvent.click(screen.getByTestId("trace-toggle"));
    fireEvent.click(screen.getByTestId("trace-toggle-json-0"));
    expect(screen.getByText("Параметры")).toBeInTheDocument();
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

  it("curl-кнопка доступна после раскрытия JSON view", () => {
    render(
      <ToolTrace
        toolCalls={[makeTC()]}
        mcpEndpoint="http://localhost:6010/mcp"
      />
    );
    // Sprint 03: curl теперь внутри JSON-блока TraceSummary (а не chip-ряда).
    fireEvent.click(screen.getByTestId("trace-toggle"));
    fireEvent.click(screen.getByTestId("trace-toggle-json-0"));
    expect(
      screen.getByRole("button", { name: /Скопировать как curl/i })
    ).toBeInTheDocument();
  });

  it("click на curl → clipboard.writeText вызван с командой", async () => {
    render(
      <ToolTrace
        toolCalls={[makeTC({ name: "execute_query", args: { q: "SELECT 1" } })]}
        mcpEndpoint="http://localhost:6010/mcp"
      />
    );
    fireEvent.click(screen.getByTestId("trace-toggle"));
    fireEvent.click(screen.getByTestId("trace-toggle-json-0"));

    const btn = screen.getByRole("button", { name: /Скопировать как curl/i });
    await act(async () => {
      fireEvent.click(btn);
    });

    expect(writeTextMock).toHaveBeenCalledTimes(1);
    const curlCmd = (writeTextMock.mock.calls[0] as unknown[])[0] as string;
    expect(curlCmd).toContain("curl -X POST");
    expect(curlCmd).toContain("execute_query");
  });

  it("clipboard reject → toast error event", async () => {
    writeTextMock.mockRejectedValue(new Error("NotAllowed"));

    const dispatchSpy = vi.spyOn(window, "dispatchEvent");

    render(
      <ToolTrace
        toolCalls={[makeTC()]}
        mcpEndpoint="http://localhost:6010/mcp"
      />
    );
    fireEvent.click(screen.getByTestId("trace-toggle"));
    fireEvent.click(screen.getByTestId("trace-toggle-json-0"));

    const btn = screen.getByRole("button", { name: /Скопировать как curl/i });
    await act(async () => {
      fireEvent.click(btn);
    });

    const toastEvents = dispatchSpy.mock.calls.filter(
      ([e]) => e instanceof CustomEvent && (e as CustomEvent).type === "app:toast"
    );
    expect(toastEvents.length).toBeGreaterThan(0);
    const lastToast = toastEvents[toastEvents.length - 1];
    expect(lastToast).toBeDefined();
    const lastEvent = lastToast![0] as CustomEvent;
    expect(lastEvent.detail.type).toBe("error");
  });
});
