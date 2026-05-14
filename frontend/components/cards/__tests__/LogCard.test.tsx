import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LogCard } from "../LogCard";
import type { LogCardPayload } from "@/lib/types";

function makePayload(overrides?: Partial<LogCardPayload>): LogCardPayload {
  return {
    entries: [
      { time: "2026-05-14T10:00:00Z", level: "Info", event: "_$Session$_.Start", user: "admin" },
      { time: "2026-05-14T10:01:00Z", level: "Warning", event: "_$Data$_.Update", user: "user1" },
      { time: "2026-05-14T10:02:00Z", level: "Error", event: "_$Access$_.Denied", user: "user2", comment: "Отказ в доступе" },
    ],
    next_cursor: null,
    ...overrides,
  };
}

describe("LogCard", () => {
  it("рендерит 3 записи (3 badge-элемента с уровнями)", () => {
    render(<LogCard payload={makePayload()} />);
    expect(screen.getByText("Info")).toBeTruthy();
    expect(screen.getByText("Warning")).toBeTruthy();
    expect(screen.getByText("Error")).toBeTruthy();
  });

  it("Critical запись имеет класс font-semibold", () => {
    const payload = makePayload({
      entries: [
        {
          time: "2026-05-14T10:00:00Z",
          level: "Critical",
          event: "_$Access$_.Hack",
        },
      ],
    });
    render(<LogCard payload={payload} />);
    const badge = screen.getByText("Critical");
    // badge имеет font-semibold в LEVEL_CLASSES["Critical"]
    expect(badge.className).toContain("font-semibold");
  });

  it("отображает время в ru-RU локали (toLocaleString)", () => {
    render(<LogCard payload={makePayload()} />);
    // Ожидаем что метки времени отрендерились (не пустые)
    const timeCells = screen.getAllByText(/2026/);
    expect(timeCells.length).toBeGreaterThan(0);
  });

  it("кнопка 'Загрузить ещё' disabled если нет onLoadMore", () => {
    const payload = makePayload({ next_cursor: "cursor_abc" });
    render(<LogCard payload={payload} />);
    const btn = screen.getByText("Загрузить ещё").closest("button");
    expect(btn).toBeTruthy();
    expect(btn).toBeDisabled();
  });

  it("кнопка 'Загрузить ещё' вызывает onLoadMore если передан", () => {
    const onLoadMore = vi.fn();
    const payload = makePayload({ next_cursor: "cursor_xyz" });
    render(<LogCard payload={payload} onLoadMore={onLoadMore} />);
    const btn = screen.getByText("Загрузить ещё").closest("button");
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn!);
    expect(onLoadMore).toHaveBeenCalledWith("cursor_xyz");
  });

  it("без next_cursor не показывает кнопку загрузки", () => {
    render(<LogCard payload={makePayload({ next_cursor: null })} />);
    expect(screen.queryByText("Загрузить ещё")).toBeNull();
  });

  it("comment отображается в details", () => {
    render(<LogCard payload={makePayload()} />);
    expect(screen.getByText("Комментарий")).toBeTruthy();
    // comment есть в DOM
    expect(screen.getByText("Отказ в доступе")).toBeTruthy();
  });

  it("пустой список entries показывает сообщение", () => {
    render(<LogCard payload={makePayload({ entries: [] })} />);
    expect(screen.getByText("Записи отсутствуют")).toBeTruthy();
  });
});
