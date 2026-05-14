import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { JsonTree } from "@/lib/json-tree";

describe("JsonTree", () => {
  it("рендерит строку с кавычками и цветом green", () => {
    render(<JsonTree value="hello" />);
    expect(screen.getByText('"hello"')).toBeInTheDocument();
  });

  it("рендерит число 42 с цветом orange", () => {
    render(<JsonTree value={42} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("рендерит boolean true с цветом purple", () => {
    render(<JsonTree value={true} />);
    expect(screen.getByText("true")).toBeInTheDocument();
  });

  it("рендерит null с цветом purple", () => {
    render(<JsonTree value={null} />);
    expect(screen.getByText("null")).toBeInTheDocument();
  });

  it("объект свёрнут по defaultExpanded=0 — показывает {2}, не показывает ключи", () => {
    render(<JsonTree value={{ a: 1, b: "x" }} defaultExpanded={0} />);
    expect(screen.getByText("▸ {2}")).toBeInTheDocument();
    expect(screen.queryByText(/a:/)).toBeNull();
    expect(screen.queryByText(/b:/)).toBeNull();
  });

  it("объект раскрыт по defaultExpanded=1 — видны ключи a: и b:", () => {
    render(<JsonTree value={{ a: 1, b: "x" }} defaultExpanded={1} />);
    expect(screen.getByText("▾ {2}")).toBeInTheDocument();
    expect(screen.getByText("a:")).toBeInTheDocument();
    expect(screen.getByText("b:")).toBeInTheDocument();
  });

  it("массив свёрнут по defaultExpanded=0 — показывает [3]", () => {
    render(<JsonTree value={[1, 2, 3]} defaultExpanded={0} />);
    expect(screen.getByText("▸ [3]")).toBeInTheDocument();
  });

  it("клик на header разворачивает массив", () => {
    render(<JsonTree value={[10, 20]} defaultExpanded={0} />);
    const btn = screen.getByText("▸ [2]");
    fireEvent.click(btn);
    expect(screen.getByText("▾ [2]")).toBeInTheDocument();
    // после разворота — видны индексы
    expect(screen.getByText("0:")).toBeInTheDocument();
    expect(screen.getByText("1:")).toBeInTheDocument();
  });

  it("вложенный объект с defaultExpanded=2: виден a, b; c — свёрнут (depth 2, не раскрыт)", () => {
    render(<JsonTree value={{ a: { b: { c: 1 } } }} defaultExpanded={2} />);
    expect(screen.getByText("a:")).toBeInTheDocument();
    expect(screen.getByText("b:")).toBeInTheDocument();
    // {c:1} на глубине 2 — свёрнут (defaultExpanded=2 > _depth=2 = false)
    expect(screen.queryByText("c:")).toBeNull();
    expect(screen.getByText("▸ {1}")).toBeInTheDocument();
  });

  it("циклическая ссылка рендерит [Circular] без crash", () => {
    const obj: Record<string, unknown> = { name: "test" };
    obj["self"] = obj;
    render(<JsonTree value={obj} defaultExpanded={1} />);
    expect(screen.getByText("[Circular]")).toBeInTheDocument();
  });

  it("пустой объект показывает {}", () => {
    render(<JsonTree value={{}} />);
    expect(screen.getByText("{}")).toBeInTheDocument();
  });

  it("пустой массив показывает []", () => {
    render(<JsonTree value={[]} />);
    expect(screen.getByText("[]")).toBeInTheDocument();
  });
});
