import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TableCard } from "../TableCard";
import type { TableCardPayload } from "@/lib/types";

// Мок для URL.createObjectURL + revokeObjectURL
const mockCreateObjectURL = vi.fn(() => "blob:mock-url");
const mockRevokeObjectURL = vi.fn();

beforeAll(() => {
  vi.stubGlobal("URL", {
    createObjectURL: mockCreateObjectURL,
    revokeObjectURL: mockRevokeObjectURL,
  });
});

afterAll(() => {
  vi.unstubAllGlobals();
});

function makePayload(overrides?: Partial<TableCardPayload>): TableCardPayload {
  return {
    columns: [
      { name: "Код", type: "String" },
      { name: "Сумма", type: "Number" },
    ],
    rows: [
      ["А001", 100],
      ["А002", 200],
    ],
    total: 2,
    meta: { query: "SELECT 1", duration_ms: 50 },
    ...overrides,
  };
}

describe("TableCard", () => {
  it("рендерит заголовки 2 колонок", () => {
    render(<TableCard payload={makePayload()} />);
    expect(screen.getByText("Код")).toBeTruthy();
    expect(screen.getByText("Сумма")).toBeTruthy();
  });

  it("показывает строки из rows", () => {
    render(<TableCard payload={makePayload()} />);
    expect(screen.getByText("А001")).toBeTruthy();
    expect(screen.getByText("А002")).toBeTruthy();
  });

  it("пагинация: 60 строк — стр. 1 из 2 видна", () => {
    const rows = Array.from({ length: 60 }, (_, i) => [`Строка-${i}`, i]);
    const payload = makePayload({ rows, total: 60 });
    render(<TableCard payload={payload} />);
    expect(screen.getByText(/Стр\. 1 из 2/)).toBeTruthy();
    // 50-я строка (index 50) не видна на первой странице
    expect(screen.queryByText("Строка-59")).toBeNull();
  });

  it("пагинация: клик на следующую страницу показывает строку 50", () => {
    const rows = Array.from({ length: 60 }, (_, i) => [`Строка-${i}`, i]);
    render(<TableCard payload={makePayload({ rows, total: 60 })} />);
    fireEvent.click(screen.getByLabelText("Следующая страница"));
    expect(screen.getByText(/Стр\. 2 из 2/)).toBeTruthy();
    expect(screen.getByText("Строка-50")).toBeTruthy();
  });

  it("сортировка по первой колонке — А оказывается первой после сортировки ASC", () => {
    const rows: unknown[][] = [["Б", 200], ["А", 100], ["В", 300]];
    render(<TableCard payload={makePayload({ rows, total: 3 })} />);
    const codeHeader = screen.getByText("Код").closest("th")!;
    fireEvent.click(codeHeader);
    // Первая ячейка данных в первом ряду должна содержать "А"
    const dataCells = screen.getAllByRole("cell");
    const firstCell = dataCells[0];
    expect(firstCell?.textContent).toBe("А");
  });

  it("кнопка CSV вызывает URL.createObjectURL", () => {
    mockCreateObjectURL.mockClear();
    render(<TableCard payload={makePayload()} />);
    fireEvent.click(screen.getByTitle("Скачать CSV"));
    expect(mockCreateObjectURL).toHaveBeenCalledOnce();
  });

  it("null-ячейка рендерится как —", () => {
    render(<TableCard payload={makePayload({ rows: [[null, 0]], total: 1 })} />);
    expect(screen.getByText("—")).toBeTruthy();
  });

  it("boolean true рендерится как ✓", () => {
    render(
      <TableCard
        payload={makePayload({
          columns: [{ name: "Активен", type: "Boolean" }],
          rows: [[true]],
          total: 1,
        })}
      />,
    );
    expect(screen.getByText("✓")).toBeTruthy();
  });
});
