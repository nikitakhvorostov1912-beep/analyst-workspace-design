import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { CardHeader } from "@/components/cards/CardHeader";

describe("CardHeader", () => {
  it("renders title for type=table", () => {
    const { container } = render(<CardHeader type="table" title="Заказы" />);
    expect(screen.getByText("Заказы")).toBeInTheDocument();
    expect(
      container.querySelector('[data-card-type="table"]'),
    ).toBeInTheDocument();
  });

  it("renders type=log with warning accent", () => {
    const { container } = render(<CardHeader type="log" title="События" />);
    expect(
      container.querySelector('[data-card-type="log"]'),
    ).toBeInTheDocument();
  });

  it("renders meta and toolName chip", () => {
    render(
      <CardHeader
        type="object"
        title="Контрагент"
        meta="ID 4711"
        toolName="get_object_by_link"
      />,
    );
    expect(screen.getByText("get_object_by_link")).toBeInTheDocument();
    expect(screen.getByText("ID 4711")).toBeInTheDocument();
  });

  it("renders anon toggle as ON (Lock + 'Маскировано')", () => {
    const { container } = render(
      <CardHeader type="log" title="Журнал" anonymizable anonOn />,
    );
    expect(screen.getByText("Маскировано")).toBeInTheDocument();
    const btn = container.querySelector('[data-anon="on"]');
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-pressed", "true");
  });

  it("renders anon toggle as OFF and fires onAnonToggle", () => {
    const onAnonToggle = vi.fn();
    render(
      <CardHeader
        type="references"
        title="Связи"
        anonymizable
        anonOn={false}
        onAnonToggle={onAnonToggle}
      />,
    );
    const btn = screen.getByText("Раскрыто");
    fireEvent.click(btn);
    expect(onAnonToggle).toHaveBeenCalledTimes(1);
  });

  it("renders action menu trigger when actions provided", () => {
    render(
      <CardHeader
        type="metric"
        title="MRR"
        actions={[{ label: "Копировать" }]}
      />,
    );
    expect(screen.getByLabelText("Действия")).toBeInTheDocument();
  });

  it("does not render anon controls when anonymizable=false", () => {
    render(<CardHeader type="code" title="BSL" />);
    expect(screen.queryByText("Маскировано")).not.toBeInTheDocument();
    expect(screen.queryByText("Раскрыто")).not.toBeInTheDocument();
  });
});
