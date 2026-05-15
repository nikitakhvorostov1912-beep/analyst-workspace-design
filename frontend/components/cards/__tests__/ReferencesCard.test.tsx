import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReferencesCard } from "../ReferencesCard";
import type { ReferencesCardPayload } from "@/lib/types";

function makePayload(overrides?: Partial<ReferencesCardPayload>): ReferencesCardPayload {
  return {
    groups: [
      {
        kind: "Реквизит",
        items: [
          { object_type: "Документ", name: "ОПП", full_path: "Документ.ОПП.Реквизит.ИНН" },
          { object_type: "Документ", name: "Заказ", full_path: "Документ.Заказ.Реквизит.Контрагент" },
        ],
      },
      {
        kind: "Подписка",
        items: [
          { object_type: "Регистр", name: "ОстаткиТоваров", full_path: "РегистрНакопления.ОстаткиТоваров.Подписка" },
        ],
      },
    ],
    total: 3,
    ...overrides,
  };
}

describe("ReferencesCard", () => {
  it("renders all groups", () => {
    render(<ReferencesCard payload={makePayload()} />);
    expect(screen.getByText("Реквизит")).toBeTruthy();
    expect(screen.getByText("Подписка")).toBeTruthy();
  });

  it("shows total count in header", () => {
    render(<ReferencesCard payload={makePayload()} />);
    expect(screen.getByText(/Используется в 3/)).toBeTruthy();
  });

  it("click on item → onLinkClick called with item", () => {
    const onLinkClick = vi.fn();
    render(<ReferencesCard payload={makePayload()} onLinkClick={onLinkClick} />);
    // Первая группа открыта по умолчанию
    const button = screen.getByText("Документ.ОПП.Реквизит.ИНН");
    fireEvent.click(button);
    expect(onLinkClick).toHaveBeenCalledWith(
      expect.objectContaining({ full_path: "Документ.ОПП.Реквизит.ИНН" }),
    );
  });

  it("filter input narrows items", () => {
    render(<ReferencesCard payload={makePayload()} />);
    const input = screen.getByPlaceholderText(/Фильтр/);
    fireEvent.change(input, { target: { value: "ОПП" } });
    // Только ОПП должен остаться в первой группе
    expect(screen.queryByText("Документ.ОПП.Реквизит.ИНН")).toBeTruthy();
    // Заказ не должен показываться
    expect(screen.queryByText("Документ.Заказ.Реквизит.Контрагент")).toBeNull();
  });

  it("empty group is hidden", () => {
    const payload = makePayload({
      groups: [
        { kind: "Реквизит", items: [] },
        { kind: "Шаблон", items: [{ object_type: "Документ", name: "X", full_path: "X.Y" }] },
      ],
      total: 1,
    });
    render(<ReferencesCard payload={payload} />);
    // Реквизит с 0 items → не рендерится
    expect(screen.queryByText("Реквизит")).toBeNull();
    expect(screen.getByText("Шаблон")).toBeTruthy();
  });

  it("groups order: Реквизит before Подписка", () => {
    const { container } = render(<ReferencesCard payload={makePayload()} />);
    const groupHeaders = container.querySelectorAll('[aria-expanded]');
    const texts = Array.from(groupHeaders).map((el) => el.textContent ?? "");
    const reqIdx = texts.findIndex((t) => t.includes("Реквизит"));
    const subIdx = texts.findIndex((t) => t.includes("Подписка"));
    expect(reqIdx).toBeLessThan(subIdx);
  });
});
